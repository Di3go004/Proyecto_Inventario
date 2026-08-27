"""
Autenticación que no distingue mayúsculas en el nombre de usuario.

Django compara el usuario exacto, así que quien se llamara "Karla" no podía
entrar escribiendo "karla". El sistema se usa desde tablets y teléfonos,
donde el teclado pone mayúscula a la primera letra solo: la mitad de la
gente iba a escribirlo con mayúscula y la otra mitad sin ella.

La contraseña sí sigue distinguiendo mayúsculas, como debe ser.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class AutenticacionSinMayusculas(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        Usuario = get_user_model()

        if username is None:
            username = kwargs.get(Usuario.USERNAME_FIELD)
        if username is None or password is None:
            return None

        try:
            usuario = Usuario.objects.get(username__iexact=username)
        except Usuario.DoesNotExist:
            # Se calcula un hash igual aunque el usuario no exista: si no, el
            # tiempo de respuesta delataría cuáles nombres son reales.
            Usuario().set_password(password)
            return None
        except Usuario.MultipleObjectsReturned:
            # Solo puede pasar con usuarios creados antes de normalizar a
            # minúsculas (p. ej. "karla" y "Karla" a la vez). En ese caso se
            # exige el nombre exacto en vez de elegir uno al azar.
            usuario = Usuario.objects.filter(username=username).first()
            if usuario is None:
                return None

        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
