"""
Pantalla de usuarios (RF-01). Solo para el rol administrador.

Reemplaza el uso del panel /admin/ de Django para esta tarea: ahí se ven
grupos, permisos y banderas internas que este sistema no usa, y que un
administrador no técnico podría cambiar sin querer y quedarse fuera.
"""

from django.contrib import messages
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.paginacion import paginar

from .decorators import rol_requerido
from .forms import RestablecerClaveForm, UsuarioForm, UsuarioNuevoForm
from .models import Usuario


def _con_actividad(consulta):
    """Cuántos registros lleva hecho cada quien: es lo que decide si su
    usuario se puede borrar o solo desactivar."""
    return consulta.annotate(
        movimientos=Count('movimientos_venta', distinct=True),
        prestamos=Count('prestamos_registrados', distinct=True),
    )


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def lista_usuarios(request):
    usuarios = _con_actividad(Usuario.objects.all()).order_by('is_active', 'username')

    q = request.GET.get('q', '').strip()
    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    rol = request.GET.get('rol', '').strip()
    if rol in Usuario.Rol.values:
        usuarios = usuarios.filter(rol=rol)
    else:
        rol = ''

    activo = request.GET.get('activo', '').strip()
    if activo == 'si':
        usuarios = usuarios.filter(is_active=True)
    elif activo == 'no':
        usuarios = usuarios.filter(is_active=False)

    pagina = paginar(request, usuarios)

    return render(request, 'usuarios/lista.html', {
        'usuarios': pagina,
        'pagina': pagina,
        'filtros_activos': len([f for f in (rol, activo) if f]),
        'roles': Usuario.Rol.choices,
        'q': q, 'rol': rol, 'activo': activo,
    })


def _avisar_clave(request, usuario, clave, generada):
    if generada:
        messages.warning(
            request,
            f'Contraseña de "{usuario.username}": {clave} — anótala ahora y '
            'entrégasela en persona; no se vuelve a mostrar.',
        )


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def usuario_nuevo(request):
    if request.method == 'POST':
        form = UsuarioNuevoForm(request.POST, editor=request.user)
        if form.is_valid():
            usuario = form.save()
            messages.success(
                request,
                f'Usuario "{usuario.username}" creado con rol {usuario.get_rol_display()}.',
            )
            _avisar_clave(request, usuario, form.cleaned_data['clave'], form.cleaned_data['generar'])
            return redirect('lista_usuarios')
    else:
        form = UsuarioNuevoForm(editor=request.user)

    return render(request, 'usuarios/form.html', {'form': form, 'modo': 'nuevo'})


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario, editor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario "{usuario.username}" actualizado.')
            return redirect('lista_usuarios')
    else:
        form = UsuarioForm(instance=usuario, editor=request.user)

    return render(request, 'usuarios/form.html', {
        'form': form, 'modo': 'editar', 'usuario_editado': usuario,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def usuario_clave(request, pk):
    """Restablecer la contraseña de alguien que la olvidó."""
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == 'POST':
        form = RestablecerClaveForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contraseña de "{usuario.username}" restablecida.')
            _avisar_clave(request, usuario, form.cleaned_data['clave'], form.cleaned_data['generar'])
            return redirect('lista_usuarios')
    else:
        form = RestablecerClaveForm(instance=usuario)

    return render(request, 'usuarios/clave_form.html', {
        'form': form, 'usuario_editado': usuario,
    })


@rol_requerido(Usuario.Rol.ADMINISTRADOR)
def usuario_eliminar(request, pk):
    """
    Borrar de verdad solo se puede si la persona nunca registró nada. En
    cuanto tiene movimientos o préstamos a su nombre, su usuario queda
    protegido: borrarlo dejaría el historial sin saber quién lo hizo. Para
    esos casos lo correcto es desactivarlo — no puede entrar más, pero su
    rastro se conserva.
    """
    usuario = get_object_or_404(_con_actividad(Usuario.objects.all()), pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('lista_usuarios')

    if request.method == 'POST':
        if request.POST.get('accion') == 'desactivar':
            usuario.is_active = False
            usuario.save()
            messages.success(
                request,
                f'Usuario "{usuario.username}" desactivado: ya no puede entrar, '
                'pero su historial se conserva.',
            )
            return redirect('lista_usuarios')

        try:
            nombre = usuario.username
            usuario.delete()
            messages.success(request, f'Usuario "{nombre}" eliminado.')
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar: tiene registros a su nombre. '
                'Desactívalo para quitarle el acceso sin perder el historial.',
            )
        return redirect('lista_usuarios')

    return render(request, 'usuarios/confirmar_eliminar.html', {'usuario_editado': usuario})
