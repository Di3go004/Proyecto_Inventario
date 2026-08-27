"""
Datos de los reportes (RF-14).

Cada función devuelve la información ya calculada, sin saber si va a
terminar en una pantalla HTML o en un archivo de Excel. Es lo que evita el
problema clásico de los reportes: que lo exportado no cuadre con lo que se
estaba viendo, porque cada camino hace su propia consulta.

El nivel de alerta (óptimo/alerta/crítico) es una propiedad calculada en
Python, no una columna, así que los conteos por nivel se hacen recorriendo
los artículos en memoria. Con 200-300 artículos eso es una sola consulta y
unos milisegundos; y mantiene la regla de RF-11 en un único lugar, el
modelo, en vez de duplicarla en SQL.
"""

from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from tecnica.models import Activo, PrestamoActivo
from ventas.models import Articulo, MovimientoVenta


def _vacio_por_nivel():
    return {'critico': 0, 'alerta': 0, 'normal': 0, 'optimo': 0}


def existencias(solo_activos=True, bodega_id=None):
    """
    Existencias y valorización de Bodega 1 y 2, agrupadas por bodega
    (RF-14). La valorización es precio × existencia de cada artículo.
    """
    articulos = Articulo.objects.select_related('bodega', 'proveedor').order_by(
        'bodega__nombre', 'nombre_producto',
    )
    if solo_activos:
        articulos = articulos.filter(activo=True)
    if bodega_id:
        articulos = articulos.filter(bodega_id=bodega_id)

    detalle = list(articulos)

    por_bodega = {}
    for articulo in detalle:
        fila = por_bodega.setdefault(articulo.bodega.nombre, {
            'bodega': articulo.bodega.nombre,
            'articulos': 0, 'unidades': 0, 'valor': Decimal('0'),
            'niveles': _vacio_por_nivel(),
        })
        fila['articulos'] += 1
        fila['unidades'] += articulo.stock_actual
        fila['valor'] += articulo.precio * articulo.stock_actual
        fila['niveles'][articulo.nivel_alerta] += 1

    filas = sorted(por_bodega.values(), key=lambda f: f['bodega'])
    totales = {
        'articulos': sum(f['articulos'] for f in filas),
        'unidades': sum(f['unidades'] for f in filas),
        'valor': sum((f['valor'] for f in filas), Decimal('0')),
    }
    return filas, detalle, totales


def valorizacion_tecnica():
    """
    Valorización de Bodega Técnica: precio × existencia, igual que en Bodega
    1 y 2 (RF-12).

    Antes sumaba solo los precios, porque se modelaba una unidad física por
    registro. El FO-SE-065 real trae cantidad y 150 de sus 249 productos
    vienen con más de una, así que la bodega salía valorizada muy por debajo.

    Lo que se dio de baja queda en existencia 0 y por eso no aporta valor,
    sin necesidad de excluirlo aparte: ya no es patrimonio utilizable.
    """
    activos = Activo.objects.all()
    resumen = activos.aggregate(
        cuantos=Count('id'),
        unidades=Sum('existencia'),
        valor=Sum(F('precio') * F('existencia')),
    )
    con_existencia = activos.filter(existencia__gt=0)
    por_estado = dict(
        con_existencia.values_list('estado').annotate(n=Count('id')).values_list('estado', 'n')
    )
    return {
        'cuantos': resumen['cuantos'] or 0,
        'unidades': resumen['unidades'] or 0,
        'valor': resumen['valor'] or Decimal('0'),
        'buen_estado': por_estado.get(Activo.Estado.BUEN_ESTADO, 0),
        'mal_estado': por_estado.get(Activo.Estado.MAL_ESTADO, 0),
        'agotados': activos.filter(existencia=0).count(),
    }


def inventario_tecnica(estado=None, solo_con_existencia=True):
    """
    Listado de Bodega Técnica con su existencia y su valor (RF-12/RF-14).

    Es el equivalente de `existencias()` para la otra bodega. No existía: los
    únicos reportes que la tocaban eran el resumen de valorización —cuatro
    números— y los préstamos abiertos, así que no había forma de sacar el
    listado completo ni de exportarlo a Excel.

    Devuelve (detalle, totales).
    """
    activos = (
        Activo.objects
        .select_related('bodega', 'categoria', 'proveedor')
        .prefetch_related('prestamos')
        .order_by('categoria__nombre', 'nombre_producto')
    )
    if solo_con_existencia:
        activos = activos.filter(existencia__gt=0)
    if estado:
        activos = activos.filter(estado=estado)

    detalle = list(activos)
    totales = {
        'productos': len(detalle),
        'unidades': sum(a.existencia for a in detalle),
        'afuera': sum(a.cantidad_afuera for a in detalle),
        'valor': sum((a.valor_en_bodega for a in detalle), Decimal('0')),
    }
    return detalle, totales


def alertas_de_stock(bodega_id=None, incluir_normales=False):
    """
    RF-11: qué hay que reponer. Ordenado por urgencia — primero lo que está
    en cero, después lo crítico, después lo de alerta.
    """
    articulos = Articulo.objects.filter(activo=True).select_related('bodega', 'proveedor')
    if bodega_id:
        articulos = articulos.filter(bodega_id=bodega_id)

    interesan = ('critico', 'alerta') if not incluir_normales else ('critico', 'alerta', 'normal')
    urgencia = {'critico': 0, 'alerta': 1, 'normal': 2, 'optimo': 3}

    encontrados = [a for a in articulos if a.nivel_alerta in interesan]
    encontrados.sort(key=lambda a: (urgencia[a.nivel_alerta], a.stock_actual, a.nombre_producto))
    return encontrados


def movimientos_del_periodo(desde=None, hasta=None, bodega_id=None):
    """
    RF-05/RF-14: qué entró y qué salió en un rango de fechas, con el total
    por tipo de movimiento. Devuelve (resumen, detalle).
    """
    movimientos = (
        MovimientoVenta.objects
        .select_related('articulo', 'articulo__bodega', 'usuario')
        .order_by('-fecha', '-id')
    )
    if desde:
        movimientos = movimientos.filter(fecha__date__gte=desde)
    if hasta:
        movimientos = movimientos.filter(fecha__date__lte=hasta)
    if bodega_id:
        movimientos = movimientos.filter(articulo__bodega_id=bodega_id)

    por_tipo = []
    etiquetas = dict(MovimientoVenta.TipoTransaccion.choices)
    agrupado = (
        movimientos
        .values('tipo_documento', 'tipo_transaccion')
        .annotate(cuantos=Count('id'), unidades=Sum('cantidad'))
        .order_by('tipo_documento', 'tipo_transaccion')
    )
    for fila in agrupado:
        por_tipo.append({
            'documento': 'Ingreso' if fila['tipo_documento'] == 'ingreso' else 'Salida',
            'tipo': etiquetas.get(fila['tipo_transaccion'], fila['tipo_transaccion']),
            'cuantos': fila['cuantos'],
            'unidades': fila['unidades'] or 0,
        })

    totales = movimientos.aggregate(
        ingresos=Sum('cantidad', filter=Q(tipo_documento='ingreso')),
        salidas=Sum('cantidad', filter=Q(tipo_documento='salida')),
        documentos=Count('folio', distinct=True, filter=~Q(folio='')),
    )
    resumen = {
        'por_tipo': por_tipo,
        'ingresos': totales['ingresos'] or 0,
        'salidas': totales['salidas'] or 0,
        'documentos': totales['documentos'] or 0,
        'movimientos': movimientos.count(),
    }
    return resumen, movimientos


def _dias_afuera(desde):
    return (timezone.now() - desde).days


def prestamos_abiertos():
    """
    RF-06/RF-07/RF-14: todo lo que está fuera de bodega ahora mismo, de los
    dos módulos junto, y desde hace cuántos días. Es la pregunta que hoy el
    Excel no puede responder.
    """
    demos = (
        MovimientoVenta.objects
        .filter(
            tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
            fecha_devolucion__isnull=True,
        )
        .select_related('articulo', 'articulo__bodega')
        .order_by('fecha')
    )
    herramienta = (
        PrestamoActivo.objects
        .filter(fecha_regreso__isnull=True)
        .select_related('activo')
        .order_by('fecha_salida')
    )

    filas = []
    for demo in demos:
        filas.append({
            'origen': 'Bodega 1 y 2',
            'codigo': demo.articulo.codigo_interno,
            'que': demo.articulo.nombre_producto,
            'cantidad': demo.cantidad,
            'quien': demo.cliente_nombre or demo.solicitado_por or '—',
            'desde': demo.fecha,
            'dias': _dias_afuera(demo.fecha),
            'referencia': demo.folio or '—',
            'url': f'/movimientos/ventas/{demo.pk}/devolucion/',
        })
    for prestamo in herramienta:
        filas.append({
            'origen': 'Bodega Técnica',
            'codigo': prestamo.activo.codigo_interno,
            'que': prestamo.activo.nombre_producto,
            'cantidad': prestamo.cantidad,
            'quien': prestamo.solicitante,
            'desde': prestamo.fecha_salida,
            'dias': _dias_afuera(prestamo.fecha_salida),
            'referencia': prestamo.get_estado_al_salir_display(),
            'url': f'/movimientos/tecnica/{prestamo.pk}/regreso/',
        })

    # Lo que lleva más tiempo afuera primero: es lo que hay que ir a buscar.
    filas.sort(key=lambda f: f['dias'], reverse=True)
    return filas
