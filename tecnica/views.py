import os
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from core.models import Bodega, Proveedor
from core.paginacion import paginar
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario

from . import boletas, importador
from .forms import ActivoForm, PrestamoForm, RegresoForm
from .models import Activo, PrestamoActivo

CARPETA_TEMP_IMPORTACIONES = os.path.join(settings.MEDIA_ROOT, 'tmp_importaciones')


@login_required
def catalogo_activos(request):
    """RF-02/RF-03: catálogo de Bodega Técnica. Los 3 roles pueden verlo;
    crear/editar/eliminar es solo admin.

    Filtros combinables (texto + estado + proveedor + precio a la vez),
    igual que en el catálogo de Ventas.
    """
    activos = Activo.objects.select_related('bodega', 'categoria', 'proveedor').prefetch_related('prestamos').order_by('nombre_producto')

    q = request.GET.get('q', '').strip()
    if q:
        activos = activos.filter(Q(codigo_interno__icontains=q) | Q(nombre_producto__icontains=q))

    estado = request.GET.get('estado', '').strip()
    if estado:
        activos = activos.filter(estado=estado)

    proveedor_id = request.GET.get('proveedor', '').strip()
    if proveedor_id:
        activos = activos.filter(proveedor_id=proveedor_id)

    precio_min = request.GET.get('precio_min', '').strip()
    if precio_min:
        try:
            activos = activos.filter(precio__gte=Decimal(precio_min))
        except InvalidOperation:
            precio_min = ''

    precio_max = request.GET.get('precio_max', '').strip()
    if precio_max:
        try:
            activos = activos.filter(precio__lte=Decimal(precio_max))
        except InvalidOperation:
            precio_max = ''

    pagina = paginar(request, activos)

    filtros_activos = len([f for f in (estado, proveedor_id, precio_min, precio_max) if f])

    return render(request, 'tecnica/catalogo.html', {
        'filtros_activos': filtros_activos,
        'activos': pagina,
        'pagina': pagina,
        'proveedores': Proveedor.objects.order_by('nombre'),
        'q': q,
        'estado': estado,
        'estados': Activo.Estado.choices,
        'proveedor_id': proveedor_id,
        'precio_min': precio_min,
        'precio_max': precio_max,
    })


@login_required
def activo_detalle(request, pk):
    """Ficha completa del activo, con su historial de préstamos — los 3
    roles pueden verla (RF-04)."""
    activo = get_object_or_404(
        Activo.objects.select_related('bodega', 'categoria', 'proveedor').prefetch_related('prestamos'), pk=pk,
    )
    prestamos = activo.prestamos.order_by('-fecha_salida')[:10]
    prestamo_abierto = activo.prestamos.filter(fecha_regreso__isnull=True).first()
    return render(request, 'tecnica/activo_detalle.html', {
        'activo': activo, 'prestamos': prestamos, 'prestamo_abierto': prestamo_abierto,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def activo_nuevo(request):
    if request.method == 'POST':
        form = ActivoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Activo creado.')
            return redirect('catalogo_activos')
    else:
        form = ActivoForm(initial={'bodega': Bodega.objects.filter(tipo=Bodega.Tipo.TECNICA).first()})
    return render(request, 'tecnica/activo_form.html', {'form': form, 'modo': 'nuevo'})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def activo_editar(request, pk):
    activo = get_object_or_404(Activo, pk=pk)
    if request.method == 'POST':
        form = ActivoForm(request.POST, request.FILES, instance=activo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Activo actualizado.')
            return redirect('catalogo_activos')
    else:
        form = ActivoForm(instance=activo)
    return render(request, 'tecnica/activo_form.html', {'form': form, 'modo': 'editar', 'activo': activo})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def activo_eliminar(request, pk):
    """
    Igual que en el catálogo de ventas: una herramienta con préstamos a su
    nombre no se borra, porque dejaría el registro sin saber qué se prestó.
    A diferencia de los artículos, acá la carga masiva no crea ningún
    préstamo, así que lo único que puede bloquear son préstamos de verdad.
    """
    activo = get_object_or_404(Activo, pk=pk)
    cuantos_prestamos = activo.prestamos.count()

    if request.method == 'POST':
        if cuantos_prestamos:
            messages.error(
                request,
                f'No se puede eliminar "{activo.nombre_producto}": tiene '
                f'{cuantos_prestamos} préstamo(s) registrados. Para retirarlo de '
                'circulación, cámbialo a "De baja" desde Editar (RF-12).',
            )
            return redirect('catalogo_activos')

        nombre = activo.nombre_producto
        activo.delete()
        messages.success(request, f'Activo "{nombre}" eliminado.')
        return redirect('catalogo_activos')

    return render(request, 'tecnica/activo_confirmar_eliminar.html', {
        'activo': activo, 'prestamos': cuantos_prestamos,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_subir(request):
    """Paso 1 de RF-09: subir el .xlsx y elegir la hoja a importar."""
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        if not archivo.name.lower().endswith('.xlsx'):
            messages.error(request, 'El archivo debe ser .xlsx (el mismo formato de FO-SE-065).')
            return render(request, 'tecnica/carga_masiva_subir.html')

        ruta_anterior = request.session.get('carga_masiva_tecnica_ruta')
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
            return render(request, 'tecnica/carga_masiva_subir.html')

        request.session['carga_masiva_tecnica_ruta'] = ruta
        request.session['carga_masiva_tecnica_nombre'] = archivo.name
        return render(request, 'tecnica/carga_masiva_subir.html', {
            'hojas': hojas, 'nombre_archivo': archivo.name,
        })

    return render(request, 'tecnica/carga_masiva_subir.html')


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_mapear(request):
    """
    Paso 2 de RF-09: se llega aquí solo por POST desde el paso 1 (con
    `hoja` elegida). La misma vista sirve dos veces: primero muestra el
    mapeo sugerido + previsualización, y cuando el admin le da "Confirmar
    e importar" (botón `confirmar`), ejecuta la carga.
    """
    ruta = request.session.get('carga_masiva_tecnica_ruta')
    if not ruta or not os.path.exists(ruta):
        messages.error(request, 'Primero sube un archivo.')
        return redirect('carga_masiva_subir_tecnica')

    hoja = request.POST.get('hoja')
    if not hoja:
        messages.error(request, 'Elige una hoja del archivo.')
        return redirect('carga_masiva_subir_tecnica')

    fila_encabezado, columnas = importador.detectar_encabezados(ruta, hoja)

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
            del request.session['carga_masiva_tecnica_ruta']

            resumen = f"Carga completa: {resultado['creados']} creados, {resultado['actualizados']} actualizados"
            if resultado['omitidos']:
                resumen += f", {resultado['omitidos']} omitidos"
            messages.success(request, resumen + '.')
            for error in resultado['errores'][:10]:
                messages.warning(request, error)
            return redirect('catalogo_activos')

    preview = list(importador.leer_filas(ruta, hoja, fila_encabezado, mapeo))[:importador.MAX_FILAS_PREVIEW]

    return render(request, 'tecnica/carga_masiva_mapear.html', {
        'hoja': hoja,
        'columnas': columnas,
        'campos': importador.CAMPOS_IMPORTABLES,
        'mapeo_sugerido': mapeo,
        'preview': preview,
        'nombre_archivo': request.session.get('carga_masiva_tecnica_nombre'),
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def carga_masiva_cancelar(request):
    ruta = request.session.pop('carga_masiva_tecnica_ruta', None)
    request.session.pop('carga_masiva_tecnica_nombre', None)
    if ruta and os.path.exists(ruta):
        os.remove(ruta)
    return redirect('catalogo_activos')


# ---------------------------------------------------------------------------
# Fase 3 — Préstamos de Bodega Técnica (RF-07, RF-12, RF-13)
# ---------------------------------------------------------------------------

@login_required
def api_buscar_activos(request):
    """
    RF-13: sugerencias del buscador de activos. Marca los que ya están
    afuera para que el operador lo vea antes de intentar prestarlos, y deja
    fuera los dados de baja (RF-12).
    """
    consulta = request.GET.get('q', '').strip()
    if len(consulta) < 2:
        return JsonResponse({'resultados': []})

    encontrados = (
        Activo.objects.exclude(estado=Activo.Estado.DE_BAJA)
        .filter(Q(codigo_interno__icontains=consulta) | Q(nombre_producto__icontains=consulta))
        .prefetch_related('prestamos')
        .order_by('nombre_producto')[:10]
    )

    return JsonResponse({'resultados': [
        {
            'id': activo.pk,
            'codigo': activo.codigo_interno,
            'nombre': activo.nombre_producto,
            'detalle': ' '.join(p for p in (activo.marca, activo.modelo) if p),
            'bodega': activo.get_estado_display(),
            'stock': 0 if activo.esta_prestado else 1,
            'nivel': 'critico' if activo.esta_prestado else 'optimo',
            'prestado': activo.esta_prestado,
        }
        for activo in encontrados
    ]})


def _prestamos_filtrados(request):
    """
    Aplica los filtros de la pantalla de préstamos. Vive aparte porque la
    impresión en PDF (RF-10) tiene que dar exactamente el mismo resultado que
    se está viendo en la lista; si el filtrado estuviera copiado en dos
    lugares, tarde o temprano dejarían de coincidir.

    Devuelve (queryset, valores_de_los_filtros).
    """
    prestamos = (
        PrestamoActivo.objects
        .select_related('activo', 'activo__bodega', 'usuario')
        .order_by('-fecha_salida', '-id')
    )

    q = request.GET.get('q', '').strip()
    if q:
        prestamos = prestamos.filter(
            Q(activo__codigo_interno__icontains=q)
            | Q(activo__nombre_producto__icontains=q)
            | Q(solicitante__icontains=q)
            | Q(entregado_por__icontains=q)
            | Q(recibido_por__icontains=q)
        )

    # Sin parámetro se asume "afuera": es la vista útil del día a día.
    estado = request.GET.get('estado', 'afuera').strip()
    if estado == 'afuera':
        prestamos = prestamos.filter(fecha_regreso__isnull=True)
    elif estado == 'devueltos':
        prestamos = prestamos.filter(fecha_regreso__isnull=False)
    else:
        estado = 'todos'

    desde = request.GET.get('desde', '').strip()
    if desde and parse_date(desde):
        prestamos = prestamos.filter(fecha_salida__date__gte=parse_date(desde))
    else:
        desde = ''

    hasta = request.GET.get('hasta', '').strip()
    if hasta and parse_date(hasta):
        prestamos = prestamos.filter(fecha_salida__date__lte=parse_date(hasta))
    else:
        hasta = ''

    return prestamos, {'q': q, 'estado': estado, 'desde': desde, 'hasta': hasta}


@login_required
def prestamos_tecnica(request):
    """
    Historial de préstamos de herramienta (RF-07). Por defecto muestra los
    que están afuera, que es la pregunta que hoy el Excel no puede
    responder: ¿quién tiene qué en este momento?
    """
    prestamos, filtros = _prestamos_filtrados(request)
    pagina = paginar(request, prestamos)
    filtros_activos = (
        len([f for f in (filtros['desde'], filtros['hasta']) if f])
        + (1 if filtros['estado'] != 'afuera' else 0)
    )

    return render(request, 'tecnica/prestamos.html', {
        'prestamos': pagina,
        'pagina': pagina,
        'filtros_activos': filtros_activos,
        **filtros,
    })


# Imprimir 20 páginas por accidente no le sirve a nadie; si el filtro trae
# más que esto, se pide acotarlo en vez de generar el PDF igual.
MAX_PRESTAMOS_PDF = 300


@login_required
def prestamos_pdf(request):
    """RF-10: la hoja FO-SE-066 con los préstamos que se están viendo."""
    prestamos, _filtros = _prestamos_filtrados(request)

    cuantos = prestamos.count()
    if cuantos > MAX_PRESTAMOS_PDF:
        messages.error(
            request,
            f'Son {cuantos} préstamos y la hoja admite hasta {MAX_PRESTAMOS_PDF}. '
            'Acota el rango de fechas o la búsqueda antes de imprimir.',
        )
        return redirect(f"{reverse('prestamos_tecnica')}?{request.GET.urlencode()}")

    respuesta = HttpResponse(boletas.hoja_prestamos(prestamos), content_type='application/pdf')
    respuesta['Content-Disposition'] = 'inline; filename="prestamos-herramienta.pdf"'
    return respuesta


@rol_requerido(Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)
def prestamo_nuevo(request):
    """RF-07: registra la salida de una herramienta (FO-SE-066, lado izquierdo)."""
    activo_inicial = None
    if request.method == 'POST':
        form = PrestamoForm(request.POST)
        if form.is_valid():
            prestamo = form.save(commit=False)
            prestamo.usuario = request.user
            prestamo.save()
            messages.success(
                request,
                f'Préstamo registrado: "{prestamo.activo.nombre_producto}" salió con {prestamo.solicitante}.',
            )
            return redirect('prestamos_tecnica')
        activo_inicial = form.data.get('activo_texto', '')
    else:
        inicial = {}
        # Se puede llegar desde la ficha del activo con el producto ya elegido.
        pk_activo = request.GET.get('activo')
        if pk_activo and pk_activo.isdigit():
            activo = Activo.objects.filter(pk=int(pk_activo)).first()
            if activo:
                inicial['activo'] = activo.pk
                inicial['estado_al_salir'] = activo.estado
                activo_inicial = f'{activo.codigo_interno} — {activo.nombre_producto}'
        form = PrestamoForm(initial=inicial)

    return render(request, 'tecnica/prestamo_form.html', {
        'form': form, 'activo_inicial': activo_inicial,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)
def prestamo_regreso(request, pk):
    """RF-07: cierra el préstamo (FO-SE-066, lado derecho)."""
    prestamo = get_object_or_404(PrestamoActivo.objects.select_related('activo'), pk=pk)
    if prestamo.fecha_regreso:
        messages.error(request, 'Ese préstamo ya fue cerrado.')
        return redirect('prestamos_tecnica')

    if request.method == 'POST':
        form = RegresoForm(request.POST, instance=prestamo)
        if form.is_valid():
            form.save()
            aviso = f'Regreso registrado: "{prestamo.activo.nombre_producto}" volvió a bodega'
            if prestamo.estado_al_regresar != prestamo.estado_al_salir:
                aviso += f' y cambió a "{prestamo.get_estado_al_regresar_display()}"'
            messages.success(request, aviso + '.')
            return redirect('prestamos_tecnica')
    else:
        form = RegresoForm(instance=prestamo)

    return render(request, 'tecnica/regreso_form.html', {'form': form, 'prestamo': prestamo})
