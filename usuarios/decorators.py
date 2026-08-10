from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def rol_requerido(*roles_permitidos):
    """
    Restringe una vista a ciertos roles (RF-02/RF-03/RF-04). Ejemplo:

        @rol_requerido(Usuario.Rol.ADMINISTRADOR)
        def articulo_nuevo(request): ...

    Siempre exige sesión iniciada primero (login_required); si el usuario ya
    autenticado no tiene el rol correcto, responde 403 en vez de 404/500.
    """

    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.user.rol not in roles_permitidos:
                raise PermissionDenied('No tienes permiso para realizar esta acción.')
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
