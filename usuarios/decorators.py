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


def rol_excluido(*roles_bloqueados):
    """
    Cierra una vista a ciertos roles, dejándola abierta al resto. Ejemplo:

        @rol_excluido(Usuario.Rol.PRACTICANTE)
        def reporte_existencias(request): ...

    Es el complemento de rol_requerido, para las pantallas que hasta ahora
    solo pedían sesión iniciada. Se usa así, y no listando los tres roles que
    sí pasan, porque son una docena de vistas y la lista se desactualizaría
    sola en cuanto aparezca otro rol.

    Ojo: al ser una lista de bloqueados, un rol nuevo entra por defecto. Por
    eso hay una prueba que recorre TODAS las urls y comprueba, una por una,
    a cuáles llega el practicante — es ahí donde se caza el decorador que
    alguien olvidó poner.
    """

    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.user.rol in roles_bloqueados:
                raise PermissionDenied('No tienes permiso para ver esta pantalla.')
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
