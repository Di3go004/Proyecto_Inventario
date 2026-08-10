from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Bodega
from usuarios.decorators import rol_requerido
from usuarios.models import Usuario

from .forms import ActivoForm
from .models import Activo


@login_required
def catalogo_activos(request):
    """RF-02/RF-03: catálogo de Bodega Técnica. Los 3 roles pueden verlo;
    crear/editar/eliminar es solo admin."""
    activos = Activo.objects.select_related('bodega', 'categoria').prefetch_related('prestamos').order_by('nombre_producto')

    q = request.GET.get('q', '').strip()
    if q:
        activos = activos.filter(Q(codigo_interno__icontains=q) | Q(nombre_producto__icontains=q))

    estado = request.GET.get('estado', '').strip()
    if estado:
        activos = activos.filter(estado=estado)

    return render(request, 'tecnica/catalogo.html', {
        'activos': activos,
        'q': q,
        'estado': estado,
        'estados': Activo.Estado.choices,
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
