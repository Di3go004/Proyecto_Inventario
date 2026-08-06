from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Usuario del sistema con un rol fijo (RF-01):
      - administrador: catálogo, usuarios, carga masiva, reportes (RF-02).
      - operador: registra movimientos/préstamos, no toca el catálogo (RF-03).
      - contabilidad: solo lectura a todo el sistema (RF-04).

    El rol vive aquí (no como Grupos/Permissions de Django) porque con solo
    3 roles fijos y reglas claras, una comprobación simple (`request.user.rol`)
    es más fácil de mantener que armar permisos view_*/add_*/change_* modelo
    por modelo — ver nota en BASE_DATOS.sql sobre cómo se mapea esto.
    """

    class Rol(models.TextChoices):
        ADMINISTRADOR = 'administrador', 'Administrador'
        OPERADOR = 'operador', 'Operador de bodega'
        CONTABILIDAD = 'contabilidad', 'Contabilidad'

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.OPERADOR)

    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    @property
    def es_operador(self):
        return self.rol == self.Rol.OPERADOR

    @property
    def es_contabilidad(self):
        return self.rol == self.Rol.CONTABILIDAD

    @property
    def puede_editar(self):
        """Contabilidad nunca puede crear/editar/eliminar (RF-04)."""
        return self.rol != self.Rol.CONTABILIDAD

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"
