import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Bodega
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario

from . import importador
from .forms import ArticuloForm
from .models import Articulo

CARPETA_TEMP_IMPORTACIONES = os.path.join(settings.MEDIA_ROOT, 'tmp_importaciones')


@login_required
def catalogo_articulos(request):
    """RF-02: listado de Bodega 1 y 2. Los 3 roles pueden verlo (RF-04
    contabilidad en solo lectura); crear/editar/eliminar es solo admin."""
    articulos = Articulo.objects.select_related('bodega', 'categoria').order_by('nombre_producto')

    q = request.GET.get('q', '').strip()
    if q:
        articulos = articulos.filter(Q(codigo_interno__icontains=q) | Q(nombre_producto__icontains=q))

    bodega_id = request.GET.get('bodega', '').strip()
    if bodega_id:
        articulos = articulos.filter(bodega_id=bodega_id)

    return render(request, 'ventas/catalogo.html', {
        'articulos': articulos,
        'bodegas': Bodega.objects.filter(tipo=Bodega.Tipo.VENTA),
        'q': q,
        'bodega_id': bodega_id,
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
    articulo = get_object_or_404(Articulo, pk=pk)
    if request.method == 'POST':
        try:
            articulo.delete()
            messages.success(request, 'Artículo eliminado.')
        except ProtectedError:
            # Tiene movimientos asociados (protegidos a propósito, ver BASE_DATOS.sql).
            messages.error(
                request,
                'No se puede eliminar: ya tiene movimientos registrados. '
                'Desmárcalo como "activo" para descontinuarlo sin perder su historial.',
            )
        return redirect('catalogo_articulos')
    return render(request, 'ventas/articulo_confirmar_eliminar.html', {'articulo': articulo})


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
