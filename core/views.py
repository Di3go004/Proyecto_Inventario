from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core import exportar, reportes
from core.forms import CategoriaForm
from core.models import Bodega, Categoria
from core.paginacion import paginar
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta
from tecnica.models import Activo, PrestamoActivo


@login_required
def resumen(request):
    """
    Primera pantalla tras el login (RF-15 la ven los 3 roles). Sirve
    también para comprobar de un vistazo que los modelos y sus reglas
    (stock, alertas, préstamos abiertos) están funcionando de verdad.
    """
    articulos = Articulo.objects.filter(activo=True)
    alertas = [a for a in articulos if a.nivel_alerta in ('alerta', 'critico')]

    valorizacion_ventas = articulos.aggregate(
        total=Sum(F('precio') * F('stock_actual'))
    )['total'] or 0

    valorizacion_tecnica = Activo.objects.exclude(estado=Activo.Estado.DE_BAJA).aggregate(
        total=Sum('precio')
    )['total'] or 0

    prestamos_demo_abiertos = MovimientoVenta.objects.filter(
        tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        fecha_devolucion__isnull=True,
    ).count()

    activos_prestados = PrestamoActivo.objects.filter(fecha_regreso__isnull=True).select_related('activo')

    contexto = {
        'total_articulos': articulos.count(),
        'alertas': alertas,
        'valorizacion_ventas': valorizacion_ventas,
        'valorizacion_tecnica': valorizacion_tecnica,
        'prestamos_demo_abiertos': prestamos_demo_abiertos,
        'activos_prestados': activos_prestados,
    }
    return render(request, 'core/resumen.html', contexto)


# ---------------------------------------------------------------------------
# Fase 5 — Reportes (RF-14)
#
# Los ven los 3 roles. Para contabilidad son la razón de ser de su acceso:
# consulta e imprime, no modifica (RF-04).
# ---------------------------------------------------------------------------

def _excel(nombre, titulo, encabezados, filas, subtitulo='', formatos=None):
    """Empaqueta un reporte como descarga de Excel."""
    contenido = exportar.libro(titulo, encabezados, filas, subtitulo, formatos)
    respuesta = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    respuesta['Content-Disposition'] = (
        f'attachment; filename="{exportar.nombre_de_archivo(nombre)}"'
    )
    return respuesta


def _bodegas_de_venta():
    return Bodega.objects.filter(tipo=Bodega.Tipo.VENTA)


@login_required
def indice_reportes(request):
    """Portada de reportes, con un dato de cada uno para saber si vale la pena abrirlo."""
    _filas, _detalle, totales = reportes.existencias()
    tecnica = reportes.valorizacion_tecnica()

    # Del mes en curso, para que la tarjeta adelante un dato útil en vez de
    # un guion — es el rango que se consulta casi siempre.
    inicio_de_mes = timezone.localtime().replace(day=1).date()
    del_mes, _detalle_mes = reportes.movimientos_del_periodo(desde=inicio_de_mes)

    return render(request, 'core/reportes/indice.html', {
        'valor_ventas': totales['valor'],
        'valor_tecnica': tecnica['valor'],
        'cuantas_alertas': len(reportes.alertas_de_stock()),
        'cuantos_afuera': len(reportes.prestamos_abiertos()),
        'movimientos_del_mes': del_mes['movimientos'],
        'inicio_de_mes': inicio_de_mes,
    })


@login_required
def reporte_existencias(request):
    """RF-14: existencias y valorización por bodega."""
    bodega_id = request.GET.get('bodega', '').strip()
    solo_activos = request.GET.get('activos', 'si') != 'no'

    filas, detalle, totales = reportes.existencias(solo_activos, bodega_id or None)
    tecnica = reportes.valorizacion_tecnica()

    if request.GET.get('formato') == 'excel':
        return _excel(
            'existencias',
            'Existencias y valorizacion - Bodega 1 y 2',
            ['Código', 'Producto', 'Bodega', 'Marca / Modelo', 'Existencia',
             'Precio unitario', 'Valor total', 'Nivel', 'Proveedor'],
            [
                [a.codigo_interno, a.nombre_producto, a.bodega.nombre,
                 f'{a.marca} {a.modelo}'.strip(), a.stock_actual, a.precio,
                 a.precio * a.stock_actual, a.nivel_alerta.capitalize(),
                 str(a.proveedor or '')]
                for a in detalle
            ],
            subtitulo='Solo artículos activos' if solo_activos else 'Activos e inactivos',
            formatos={5: exportar.FORMATO_MONEDA, 6: exportar.FORMATO_MONEDA},
        )

    return render(request, 'core/reportes/existencias.html', {
        'filas': filas,
        'totales': totales,
        'tecnica': tecnica,
        'pagina': paginar(request, detalle),
        'bodegas': _bodegas_de_venta(),
        'bodega_id': bodega_id,
        'solo_activos': solo_activos,
    })


@login_required
def reporte_alertas(request):
    """RF-11/RF-14: qué hay que reponer, lo más urgente primero."""
    bodega_id = request.GET.get('bodega', '').strip()
    articulos = reportes.alertas_de_stock(bodega_id or None)

    if request.GET.get('formato') == 'excel':
        return _excel(
            'alertas-de-stock',
            'Alertas de stock - que reponer',
            ['Nivel', 'Código', 'Producto', 'Bodega', 'Existencia',
             'Crítico', 'Alerta', 'Óptimo', 'Proveedor'],
            [
                [a.nivel_alerta.capitalize(), a.codigo_interno, a.nombre_producto,
                 a.bodega.nombre, a.stock_actual, a.stock_critico, a.stock_alerta,
                 a.stock_optimo, str(a.proveedor or '')]
                for a in articulos
            ],
            subtitulo=f'{len(articulos)} artículo(s) en alerta o crítico',
        )

    return render(request, 'core/reportes/alertas.html', {
        'pagina': paginar(request, articulos),
        'cuantos': len(articulos),
        'criticos': len([a for a in articulos if a.nivel_alerta == 'critico']),
        'bodegas': _bodegas_de_venta(),
        'bodega_id': bodega_id,
    })


@login_required
def reporte_movimientos(request):
    """RF-05/RF-14: qué entró y qué salió en un período."""
    desde = parse_date(request.GET.get('desde', '') or '')
    hasta = parse_date(request.GET.get('hasta', '') or '')
    bodega_id = request.GET.get('bodega', '').strip()

    resumen_periodo, detalle = reportes.movimientos_del_periodo(desde, hasta, bodega_id or None)

    if request.GET.get('formato') == 'excel':
        rango = ' a '.join(f'{f:%d/%m/%Y}' for f in (desde, hasta) if f) or 'todo el historial'
        return _excel(
            'movimientos',
            'Movimientos de Bodega 1 y 2',
            ['Fecha', 'Folio', 'Dirección', 'Tipo', 'Código', 'Producto',
             'Bodega', 'Cantidad', 'Solicitado por', 'Cliente / Proveedor',
             'No. factura', 'Registrado por'],
            [
                [exportar.valor_para_excel(m.fecha), m.folio,
                 m.get_tipo_documento_display(), m.get_tipo_transaccion_display(),
                 m.articulo.codigo_interno, m.articulo.nombre_producto,
                 m.articulo.bodega.nombre, m.cantidad, m.solicitado_por,
                 m.cliente_nombre or str(m.proveedor or ''), m.no_factura,
                 m.usuario.get_full_name() or m.usuario.username]
                for m in detalle
            ],
            subtitulo=f'Período: {rango}',
            formatos={0: exportar.FORMATO_FECHA},
        )

    return render(request, 'core/reportes/movimientos.html', {
        'resumen': resumen_periodo,
        'pagina': paginar(request, detalle),
        'bodegas': _bodegas_de_venta(),
        'desde': request.GET.get('desde', ''),
        'hasta': request.GET.get('hasta', ''),
        'bodega_id': bodega_id,
    })


@login_required
def reporte_prestamos(request):
    """RF-06/RF-07/RF-14: todo lo que está fuera de bodega ahora mismo."""
    filas = reportes.prestamos_abiertos()

    if request.GET.get('formato') == 'excel':
        return _excel(
            'prestamos-abiertos',
            'Equipo y herramienta fuera de bodega',
            ['Origen', 'Código', 'Qué', 'Cantidad', 'Quién lo tiene',
             'Salió el', 'Días afuera', 'Referencia'],
            [
                [f['origen'], f['codigo'], f['que'], f['cantidad'], f['quien'],
                 exportar.valor_para_excel(f['desde']), f['dias'], f['referencia']]
                for f in filas
            ],
            subtitulo=f'{len(filas)} pendiente(s) de regreso',
            formatos={5: exportar.FORMATO_FECHA},
        )

    return render(request, 'core/reportes/prestamos.html', {
        'filas': filas,
        'cuantos': len(filas),
        'mas_de_una_semana': len([f for f in filas if f['dias'] >= 7]),
    })


# ---------------------------------------------------------------------------
# Categorías del catálogo (RF-02/RF-03). Solo el administrador.
#
# Antes solo se podían tocar desde el panel /admin/ de Django, que se quitó
# de la navegación por la misma razón que la gestión de usuarios: ahí se ven
# tablas y banderas internas que este sistema no usa.
# ---------------------------------------------------------------------------

def _con_uso(consulta):
    """Cuántos registros cuelgan de cada categoría: decide si se puede borrar."""
    return consulta.annotate(
        articulos=Count('articulo', distinct=True),
        activos=Count('activo', distinct=True),
    )


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def lista_categorias(request):
    categorias = _con_uso(Categoria.objects.all()).order_by('modulo', 'nombre')

    q = request.GET.get('q', '').strip()
    if q:
        categorias = categorias.filter(nombre__icontains=q)

    modulo = request.GET.get('modulo', '').strip()
    if modulo in Categoria.Modulo.values:
        categorias = categorias.filter(modulo=modulo)
    else:
        modulo = ''

    pagina = paginar(request, categorias)

    return render(request, 'core/categorias/lista.html', {
        'categorias': pagina,
        'pagina': pagina,
        'modulos': Categoria.Modulo.choices,
        'filtros_activos': 1 if modulo else 0,
        'q': q, 'modulo': modulo,
        'sin_clasificar_ventas': Articulo.objects.filter(categoria__isnull=True).count(),
        'sin_clasificar_tecnica': Activo.objects.filter(categoria__isnull=True).count(),
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def categoria_nueva(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" creada.')
            return redirect('lista_categorias')
    else:
        # Si se entra desde el filtro de una bodega, se propone esa.
        inicial = {}
        if request.GET.get('modulo') in Categoria.Modulo.values:
            inicial['modulo'] = request.GET['modulo']
        form = CategoriaForm(initial=inicial)

    return render(request, 'core/categorias/form.html', {'form': form, 'modo': 'nueva'})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" actualizada.')
            return redirect('lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, 'core/categorias/form.html', {
        'form': form, 'modo': 'editar', 'categoria': categoria,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def categoria_eliminar(request, pk):
    """
    Borrar una categoría en uso NO borra sus artículos: el campo queda en
    blanco (SET_NULL) y quedan sin clasificar. Como eso no se puede deshacer
    yendo uno por uno, la pantalla dice cuántos son antes de confirmar.
    """
    categoria = get_object_or_404(_con_uso(Categoria.objects.all()), pk=pk)

    if request.method == 'POST':
        cuantos = categoria.articulos + categoria.activos
        nombre = categoria.nombre
        categoria.delete()
        if cuantos:
            messages.warning(
                request,
                f'Categoría "{nombre}" eliminada. {cuantos} registro(s) quedaron '
                'sin categoría; asígnales otra desde el catálogo.',
            )
        else:
            messages.success(request, f'Categoría "{nombre}" eliminada.')
        return redirect('lista_categorias')

    return render(request, 'core/categorias/confirmar_eliminar.html', {'categoria': categoria})
