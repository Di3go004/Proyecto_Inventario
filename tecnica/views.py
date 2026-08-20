import os
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Bodega, Proveedor
from core.paginacion import paginar
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario

from . import importador
from .forms import ActivoForm
from .models import Activo

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
    return render(request, 'tecnica/activo_detalle.html', {'activo': activo, 'prestamos': prestamos})


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
    activo = get_object_or_404(Activo, pk=pk)
    if request.method == 'POST':
        try:
            activo.delete()
            messages.success(request, 'Activo eliminado.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar: ya tiene préstamos registrados. '
                'Cambia su estado a "De baja" desde Editar en su lugar.',
            )
        return redirect('catalogo_activos')
    return render(request, 'tecnica/activo_confirmar_eliminar.html', {'activo': activo})


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
