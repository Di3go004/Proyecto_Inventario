import os
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, ProtectedError, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from core.models import Bodega, Proveedor
from core.paginacion import paginar
from tecnica.models import Activo, MovimientoActivo
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario

from . import boletas, documentos, importador
from .forms import (
    ArticuloForm, DevolucionDemoForm, DocumentoMovimientoForm, identificador_de, leer_lineas,
)
from .models import Articulo, MovimientoVenta

CARPETA_TEMP_IMPORTACIONES = os.path.join(settings.MEDIA_ROOT, 'tmp_importaciones')


@login_required
def catalogo_articulos(request):
    """RF-02: listado de Bodega 1 y 2. Los 3 roles pueden verlo (RF-04
    contabilidad en solo lectura); crear/editar/eliminar es solo admin.

    Los filtros son combinables (bodega + proveedor + nivel + precio + texto
    a la vez, no uno reemplaza al otro): cada uno se aplica sobre lo que
    dejó el anterior, como pidió el usuario.
    """
    articulos = Articulo.objects.select_related('bodega', 'categoria', 'proveedor').order_by('nombre_producto')

    q = request.GET.get('q', '').strip()
    if q:
        articulos = articulos.filter(Q(codigo_interno__icontains=q) | Q(nombre_producto__icontains=q))

    bodega_id = request.GET.get('bodega', '').strip()
    if bodega_id:
        articulos = articulos.filter(bodega_id=bodega_id)

    proveedor_id = request.GET.get('proveedor', '').strip()
    if proveedor_id:
        articulos = articulos.filter(proveedor_id=proveedor_id)

    precio_min = request.GET.get('precio_min', '').strip()
    if precio_min:
        try:
            articulos = articulos.filter(precio__gte=Decimal(precio_min))
        except InvalidOperation:
            precio_min = ''

    precio_max = request.GET.get('precio_max', '').strip()
    if precio_max:
        try:
            articulos = articulos.filter(precio__lte=Decimal(precio_max))
        except InvalidOperation:
            precio_max = ''

    activo = request.GET.get('activo', '').strip()
    if activo == 'si':
        articulos = articulos.filter(activo=True)
    elif activo == 'no':
        articulos = articulos.filter(activo=False)

    # nivel_alerta es una propiedad calculada en Python (RF-11), no una
    # columna — no se puede filtrar en la base de datos, así que se aplica
    # al final sobre la lista ya recortada por los demás filtros.
    nivel = request.GET.get('nivel', '').strip()
    if nivel:
        articulos = [a for a in articulos if a.nivel_alerta == nivel]

    pagina = paginar(request, articulos)

    # Cuántos filtros hay puestos (sin contar la búsqueda por texto, que
    # siempre está a la vista): se muestra junto al botón "Filtros" para
    # que se note que hay filtros aplicados aunque el panel esté cerrado.
    filtros_activos = len([f for f in (bodega_id, proveedor_id, nivel, precio_min, precio_max, activo) if f])

    return render(request, 'ventas/catalogo.html', {
        'filtros_activos': filtros_activos,
        'articulos': pagina,
        'pagina': pagina,
        'bodegas': Bodega.objects.filter(tipo=Bodega.Tipo.VENTA),
        'proveedores': Proveedor.objects.order_by('nombre'),
        'q': q,
        'bodega_id': bodega_id,
        'proveedor_id': proveedor_id,
        'nivel': nivel,
        'precio_min': precio_min,
        'precio_max': precio_max,
        'activo': activo,
    })


@login_required
def articulo_detalle(request, pk):
    """Ficha completa del artículo — los 3 roles pueden verla (RF-04)."""
    articulo = get_object_or_404(
        Articulo.objects.select_related('bodega', 'categoria', 'proveedor'), pk=pk,
    )
    # Los últimos movimientos, para no tener que ir al kardex completo solo
    # para ver qué pasó hace poco con este producto.
    movimientos = articulo.movimientos.select_related('usuario').order_by('-fecha', '-id')[:8]
    return render(request, 'ventas/articulo_detalle.html', {
        'articulo': articulo, 'movimientos': movimientos,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def articulo_nuevo(request):
    if request.method == 'POST':
        form = ArticuloForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Artículo creado. El stock inicial se registra desde Movimientos (Fase 3).')
            return redirect('catalogo_articulos')
    else:
        form = ArticuloForm()
    return render(request, 'ventas/articulo_form.html', {'form': form, 'modo': 'nuevo'})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def articulo_editar(request, pk):
    articulo = get_object_or_404(Articulo, pk=pk)
    if request.method == 'POST':
        form = ArticuloForm(request.POST, request.FILES, instance=articulo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Artículo actualizado.')
            return redirect('catalogo_articulos')
    else:
        form = ArticuloForm(instance=articulo)
    return render(request, 'ventas/articulo_form.html', {'form': form, 'modo': 'editar', 'articulo': articulo})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def articulo_eliminar(request, pk):
    """
    Un artículo con historial real no se borra: quedarían movimientos sin
    saber a qué producto pertenecían.

    Pero el "ajuste / saldo inicial" que crea la carga masiva (RF-09) no es
    historial — es solo el conteo con el que arrancó el artículo. Si es lo
    único que tiene, se borra junto con él. Sin esta distinción, importar el
    Excel dejaba los 216 artículos imposibles de borrar para siempre, incluso
    los que se hubieran importado por error, y el aviso además daba a entender
    que desactivarlos servía de algo — no servía.
    """
    articulo = get_object_or_404(Articulo, pk=pk)
    movimientos_reales = articulo.movimientos.exclude(
        tipo_transaccion=MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL,
    )
    cuantos_reales = movimientos_reales.count()

    if request.method == 'POST':
        if cuantos_reales:
            messages.error(
                request,
                f'No se puede eliminar "{articulo.nombre_producto}": tiene '
                f'{cuantos_reales} movimiento(s) registrados. Desactivarlo tampoco '
                'lo habilita — el historial se protege siempre. Para sacarlo del '
                'catálogo, desmárcalo como activo desde Editar.',
            )
            return redirect('catalogo_articulos')

        nombre = articulo.nombre_producto
        with transaction.atomic():
            # A esta altura lo único que puede quedar es el ajuste inicial.
            articulo.movimientos.all().delete()
            articulo.delete()
        messages.success(request, f'Artículo "{nombre}" eliminado.')
        return redirect('catalogo_articulos')

    return render(request, 'ventas/articulo_confirmar_eliminar.html', {
        'articulo': articulo,
        'movimientos_reales': cuantos_reales,
        'ajustes_iniciales': articulo.movimientos.count() - cuantos_reales,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_subir(request):
    """Paso 1 de RF-09: subir el .xlsx y elegir la hoja a importar."""
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        if not archivo.name.lower().endswith('.xlsx'):
            messages.error(request, 'El archivo debe ser .xlsx (el mismo formato de FO-SE-053).')
            return render(request, 'ventas/carga_masiva_subir.html')

        # Si ya había un archivo subido sin confirmar (abandonado, o se subió
        # otro encima), se limpia antes de guardar el nuevo.
        ruta_anterior = request.session.get('carga_masiva_ventas_ruta')
        if ruta_anterior and os.path.exists(ruta_anterior):
            os.remove(ruta_anterior)

        os.makedirs(CARPETA_TEMP_IMPORTACIONES, exist_ok=True)
        ruta = os.path.join(CARPETA_TEMP_IMPORTACIONES, f"{uuid.uuid4().hex}.xlsx")
        with open(ruta, 'wb') as destino:
            for trozo in archivo.chunks():
                destino.write(trozo)

        try:
            hojas = importador.listar_hojas(ruta)
        except Exception:
            messages.error(request, 'No se pudo leer el archivo. ¿Es un .xlsx válido y no está dañado?')
            os.remove(ruta)
            return render(request, 'ventas/carga_masiva_subir.html')

        request.session['carga_masiva_ventas_ruta'] = ruta
        request.session['carga_masiva_ventas_nombre'] = archivo.name
        return render(request, 'ventas/carga_masiva_subir.html', {
            'hojas': hojas, 'nombre_archivo': archivo.name,
        })

    return render(request, 'ventas/carga_masiva_subir.html')


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_mapear(request):
    """
    Paso 2 de RF-09: se llega aquí solo por POST desde el paso 1 (con
    `hoja` elegida). La misma vista sirve dos veces: primero muestra el
    mapeo sugerido + previsualización, y cuando el admin le da "Confirmar
    e importar" (botón `confirmar`), ejecuta la carga.
    """
    ruta = request.session.get('carga_masiva_ventas_ruta')
    if not ruta or not os.path.exists(ruta):
        messages.error(request, 'Primero sube un archivo.')
        return redirect('carga_masiva_subir')

    hoja = request.POST.get('hoja')
    if not hoja:
        messages.error(request, 'Elige una hoja del archivo.')
        return redirect('carga_masiva_subir')

    fila_encabezado, columnas = importador.detectar_encabezados(ruta, hoja)

    # Si el admin ya movió algún <select> del mapeo (para confirmar o solo
    # para refrescar la vista previa), se respeta lo que eligió; si no, se
    # parte del mapeo autodetectado por nombre de columna.
    mapeo_en_post = {
        clave: request.POST.get(f'col__{clave}', '').strip()
        for clave, _et, _ob, _pal in importador.CAMPOS_IMPORTABLES
    }
    if any(mapeo_en_post.values()):
        mapeo = {clave: letra for clave, letra in mapeo_en_post.items() if letra}
    else:
        mapeo = importador.autodetectar_mapeo(columnas)

    if request.POST.get('confirmar'):
        faltantes = [et for clave, et, ob, _p in importador.CAMPOS_IMPORTABLES if ob and clave not in mapeo]
        if faltantes:
            messages.error(request, f"Falta mapear: {', '.join(faltantes)}.")
        else:
            resultado = importador.ejecutar_importacion(ruta, hoja, fila_encabezado, mapeo, request.user)
            os.remove(ruta)
            del request.session['carga_masiva_ventas_ruta']

            resumen = f"Carga completa: {resultado['creados']} creados, {resultado['actualizados']} actualizados"
            if resultado['omitidos']:
                resumen += f", {resultado['omitidos']} omitidos"
            messages.success(request, resumen + '.')
            for error in resultado['errores'][:10]:
                messages.warning(request, error)
            return redirect('catalogo_articulos')

    preview = list(importador.leer_filas(ruta, hoja, fila_encabezado, mapeo))[:importador.MAX_FILAS_PREVIEW]
    for fila in preview:
        # Vista previa de lo que se va a guardar, sin tocar la base de datos.
        fila['codigo_interno_preview'] = Articulo(modelo=fila['modelo'], capacidad=fila['capacidad']).generar_codigo_interno()
        fila['bodega_reconocida'] = bool(fila['bodega_num'] in (1, 2))

    return render(request, 'ventas/carga_masiva_mapear.html', {
        'hoja': hoja,
        'columnas': columnas,
        'campos': importador.CAMPOS_IMPORTABLES,
        'mapeo_sugerido': mapeo,
        'preview': preview,
        'nombre_archivo': request.session.get('carga_masiva_ventas_nombre'),
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_cancelar(request):
    ruta = request.session.pop('carga_masiva_ventas_ruta', None)
    request.session.pop('carga_masiva_ventas_nombre', None)
    if ruta and os.path.exists(ruta):
        os.remove(ruta)
    return redirect('catalogo_articulos')


# ---------------------------------------------------------------------------
# Fase 3 — Movimientos de Bodega 1 y 2 (RF-05, RF-06, RF-08, RF-13)
# ---------------------------------------------------------------------------

@login_required
def api_buscar_articulos(request):
    """
    RF-13: sugerencias mientras se escribe, para capturar sin lector de
    código de barras. Busca por código interno, nombre o número de serial y
    devuelve lo mínimo para que el operador reconozca el producto sin
    abrirlo (bodega y stock incluidos).
    """
    consulta = request.GET.get('q', '').strip()
    if len(consulta) < 2:
        return JsonResponse({'resultados': []})

    encontrados = (
        Articulo.objects.filter(activo=True)
        .filter(
            Q(codigo_interno__icontains=consulta)
            | Q(nombre_producto__icontains=consulta)
            | Q(numero_serie__icontains=consulta)
        )
        .select_related('bodega', 'proveedor')
        .order_by('nombre_producto')[:10]
    )

    resultados = [
        {
            'id': identificador_de(articulo, es_tecnica=False),
            'codigo': articulo.codigo_interno,
            'nombre': articulo.nombre_producto,
            'detalle': ' '.join(p for p in (articulo.marca, articulo.modelo, articulo.capacidad) if p),
            'bodega': articulo.bodega.nombre,
            # El proveedor viaja para poder enseñarlo al elegir el producto:
            # en el ingreso ya no se escribe a mano, se hereda del catálogo, y
            # sin verlo en pantalla parece que el sistema no lo está tomando.
            'proveedor': articulo.proveedor.nombre if articulo.proveedor else '',
            'stock': articulo.stock_actual,
            'nivel': articulo.nivel_alerta,
        }
        for articulo in encontrados
    ]

    # El FO-SE-013 es el mismo formato para las tres bodegas, así que el
    # ingreso ofrece también los activos. La salida no: a Bodega Técnica solo
    # entran cosas — lo que la baja es dar de baja, que se registra aparte.
    if request.GET.get('incluir') == 'tecnica':
        activos = (
            Activo.objects.filter(
                Q(codigo_interno__icontains=consulta) | Q(nombre_producto__icontains=consulta)
            )
            .select_related('bodega', 'proveedor')
            .order_by('nombre_producto')[:10]
        )
        resultados += [
            {
                'id': identificador_de(activo, es_tecnica=True),
                'codigo': activo.codigo_interno,
                'nombre': activo.nombre_producto,
                'detalle': ' '.join(p for p in (activo.marca, activo.modelo) if p),
                'bodega': activo.bodega.nombre,
                'proveedor': activo.proveedor.nombre if activo.proveedor else '',
                'stock': activo.existencia,
                'nivel': 'neutral',
            }
            for activo in activos
        ]

    return JsonResponse({'resultados': resultados})


# Campos de la cabecera del FO-SE-013 que Bodega Técnica también guarda. El
# resto (tipo de transacción, cliente, envío) es de la boleta de venta.
CABECERA_TECNICA = ('fecha', 'solicitado_por', 'no_factura', 'no_boleta', 'observacion')


def _guardar_documento(cabecera, tipo_transaccion, folio, lineas, tipo_documento, usuario):
    """
    Crea las líneas del documento. Va siempre dentro de una transacción del
    llamador: si una línea falla (por ejemplo, no hay stock suficiente), no
    queda guardada ninguna. Es lo que se espera de una boleta — o entra
    completa o no entra, nunca a medias.

    Un mismo folio puede llevar líneas de las dos bodegas: el FO-SE-013 es un
    solo talonario, así que una boleta real puede traer productos de venta y
    herramienta juntos. Cada línea se guarda en la tabla que le toca.
    """
    for linea in lineas:
        if linea['es_tecnica']:
            MovimientoActivo.objects.create(
                folio=folio,
                tipo=MovimientoActivo.Tipo.INGRESO,
                activo=linea['articulo'],
                cantidad=linea['cantidad'],
                usuario=usuario,
                **{campo: cabecera[campo] for campo in CABECERA_TECNICA if campo in cabecera},
            )
        else:
            MovimientoVenta.objects.create(
                folio=folio,
                tipo_documento=tipo_documento,
                tipo_transaccion=tipo_transaccion,
                articulo=linea['articulo'],
                cantidad=linea['cantidad'],
                usuario=usuario,
                **cabecera,
            )


def _registrar_documento(request, tipo_documento):
    """Pantalla compartida de ingreso (FO-SE-013) y salida (FO-SE-012)."""
    es_ingreso = tipo_documento == MovimientoVenta.TipoDocumento.INGRESO
    lineas = []
    # El folio lo escribe quien registra: viene impreso en el talonario. Se
    # propone el siguiente de la serie para no teclearlo cuando van en orden.
    folio_siguiente = MovimientoVenta.siguiente_folio(tipo_documento)

    if request.method == 'POST':
        form = DocumentoMovimientoForm(request.POST, tipo_documento=tipo_documento)
        lineas = leer_lineas(request.POST, incluir_tecnica=es_ingreso)
        formulario_valido = form.is_valid()

        lineas_con_error = [linea for linea in lineas if linea['error']]

        if not lineas:
            messages.error(request, 'Agrega al menos un producto al documento.')
        elif lineas_con_error:
            messages.error(
                request,
                f"Revisa {len(lineas_con_error)} línea(s) del detalle: el documento no se guardó.",
            )
        elif formulario_valido:
            cabecera = form.datos_para_movimiento()
            # El folio se calcula dentro de la transacción para que dos
            # personas registrando a la vez no se lo peleen.
            folio = (form.cleaned_data.get('folio') or '').strip()
            try:
                with transaction.atomic():
                    if not folio:
                        folio = MovimientoVenta.siguiente_folio(tipo_documento)
                    _guardar_documento(
                        cabecera, form.cleaned_data['tipo_transaccion'], folio,
                        lineas, tipo_documento, request.user,
                    )
            except ValidationError as error:
                # Viene de MovimientoVenta.save() cuando la salida deja el
                # stock en negativo: no se guardó nada.
                messages.error(request, error.messages[0])
            else:
                messages.success(
                    request,
                    f"{'Ingreso' if es_ingreso else 'Salida'} registrado con folio {folio} "
                    f"({len(lineas)} {'línea' if len(lineas) == 1 else 'líneas'}).",
                )
                return redirect('documento_detalle', folio=folio)
    else:
        form = DocumentoMovimientoForm(
            tipo_documento=tipo_documento, folio_sugerido=folio_siguiente,
        )

    return render(request, 'ventas/movimiento_form.html', {
        'form': form,
        'lineas': lineas,
        'es_ingreso': es_ingreso,
        'folio_siguiente': folio_siguiente,
        'tipo_documento': tipo_documento,
        'incluir_tecnica': es_ingreso,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)
def movimiento_ingreso(request):
    """RF-05: reemplaza el formato de papel FO-SE-013."""
    return _registrar_documento(request, MovimientoVenta.TipoDocumento.INGRESO)


@rol_requerido(Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)
def movimiento_salida(request):
    """RF-05: reemplaza el formato de papel FO-SE-012."""
    return _registrar_documento(request, MovimientoVenta.TipoDocumento.SALIDA)


@login_required
def movimientos_ventas(request):
    """
    Historial de entradas y salidas (RF-05). Lo ven los 3 roles: es la
    vista que hoy no existe en el Excel, donde se puede rastrear qué pasó
    con cada producto sin abrir hoja por hoja.

    Incluye las tres bodegas. El FO-SE-013 es un solo talonario, así que
    partir el historial por bodega obligaría a buscar el mismo folio en dos
    pantallas distintas.
    """
    q = request.GET.get('q', '').strip()

    tipo = request.GET.get('tipo', '').strip()
    if tipo not in list(MovimientoVenta.TipoDocumento.values) + ['baja']:
        tipo = ''

    transaccion = request.GET.get('transaccion', '').strip()
    if transaccion not in MovimientoVenta.TipoTransaccion.values:
        transaccion = ''

    bodega_id = request.GET.get('bodega', '').strip()

    desde = request.GET.get('desde', '').strip()
    desde = desde if desde and parse_date(desde) else ''
    hasta = request.GET.get('hasta', '').strip()
    hasta = hasta if hasta and parse_date(hasta) else ''

    afuera = request.GET.get('afuera', '').strip()

    filas = documentos.filas_de_historial(
        q=q, tipo=tipo, transaccion=transaccion, bodega_id=bodega_id,
        desde=parse_date(desde) if desde else None,
        hasta=parse_date(hasta) if hasta else None,
        afuera=afuera,
    )

    pagina = paginar(request, filas)
    filtros_activos = len([f for f in (tipo, transaccion, bodega_id, desde, hasta, afuera) if f])

    return render(request, 'ventas/movimientos.html', {
        'movimientos': pagina,
        'pagina': pagina,
        'filtros_activos': filtros_activos,
        'bodegas': Bodega.objects.all(),
        'transacciones': MovimientoVenta.TipoTransaccion.choices,
        'q': q, 'tipo': tipo, 'transaccion': transaccion,
        'bodega_id': bodega_id, 'desde': desde, 'hasta': hasta, 'afuera': afuera,
    })


@login_required
def documento_detalle(request, folio):
    """
    Todas las líneas de un mismo folio, como se ve la boleta en papel.
    En la Fase 4 esta misma vista es la que se imprime en PDF (RF-10).
    """
    lineas = documentos.lineas_del_documento(folio)
    if not lineas:
        messages.error(request, f'No existe ningún documento con folio {folio}.')
        return redirect('movimientos_ventas')

    total_unidades, total_quetzales = documentos.totales(lineas)

    return render(request, 'ventas/documento_detalle.html', {
        'folio': folio,
        'es_ingreso': documentos.es_ingreso(lineas),
        # La cabecera sale del primer movimiento: los datos del encabezado
        # (fecha, solicitado por, factura) se repiten en todas las líneas.
        'cabecera': lineas[0].movimiento,
        'lineas': lineas,
        'total_unidades': total_unidades,
        'total_quetzales': total_quetzales,
        'lleva_tecnica': any(linea.es_tecnica for linea in lineas),
    })


@login_required
def documento_pdf(request, folio):
    """
    RF-10: la boleta lista para imprimir y firmar a mano, con el mismo
    formato del talonario (FO-SE-013 / FO-SE-012).

    La ven los 3 roles: imprimir es consultar, no modificar (RF-04).
    """
    try:
        contenido = boletas.boleta_documento(folio)
    except MovimientoVenta.DoesNotExist:
        raise Http404(f'No existe ningún documento con folio {folio}.')

    respuesta = HttpResponse(contenido, content_type='application/pdf')
    # "inline" abre el visor del navegador, que es desde donde se manda a
    # imprimir; el nombre solo se usa si deciden guardar el archivo.
    respuesta['Content-Disposition'] = f'inline; filename="{folio}.pdf"'
    # La boleta se arma en el momento y puede cambiar (se corrigió un dato del
    # artículo, cambió el formato). Sin esto el navegador guarda la primera
    # que descargó y sigue mostrándola, que es difícil de diagnosticar porque
    # el archivo del servidor sí cambió.
    respuesta['Cache-Control'] = 'no-store, must-revalidate'
    return respuesta


@login_required
def kardex_articulo(request, pk):
    """
    RF-08/RF-14: historial de un artículo con el saldo después de cada
    movimiento. El saldo se acumula en Python sobre la lista completa
    ordenada de la más vieja a la más nueva, y recién después se invierte
    para mostrarla, porque el saldo de una fila depende de todas las
    anteriores.
    """
    articulo = get_object_or_404(Articulo.objects.select_related('bodega'), pk=pk)

    movimientos = list(
        articulo.movimientos.select_related('usuario').order_by('fecha', 'id')
    )
    saldo = 0
    for movimiento in movimientos:
        saldo += movimiento.signo * movimiento.cantidad
        movimiento.saldo = saldo

    movimientos.reverse()
    pagina = paginar(request, movimientos)

    return render(request, 'ventas/kardex.html', {
        'articulo': articulo,
        'movimientos': pagina,
        'pagina': pagina,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)
def devolucion_demo(request, pk):
    """RF-06: cierra un préstamo/demo y devuelve el equipo al stock."""
    movimiento = get_object_or_404(
        MovimientoVenta.objects.select_related('articulo'), pk=pk,
    )
    if not movimiento.esta_afuera:
        messages.error(request, 'Ese movimiento no es un préstamo/demo pendiente de regreso.')
        return redirect('movimientos_ventas')

    if request.method == 'POST':
        form = DevolucionDemoForm(request.POST, movimiento=movimiento)
        if form.is_valid():
            movimiento.fecha_devolucion = form.cleaned_data['fecha_devolucion']
            movimiento.devuelto_por = form.cleaned_data['devuelto_por']
            observacion = form.cleaned_data['observacion']
            if observacion:
                movimiento.observacion = f"{movimiento.observacion}\n{observacion}".strip()
            movimiento.save()
            messages.success(
                request,
                f'Devolución registrada: "{movimiento.articulo.nombre_producto}" '
                f'vuelve al stock ({movimiento.cantidad} unidad(es)).',
            )
            return redirect('movimientos_ventas')
    else:
        form = DevolucionDemoForm(movimiento=movimiento)

    return render(request, 'ventas/devolucion_form.html', {
        'form': form, 'movimiento': movimiento,
    })
