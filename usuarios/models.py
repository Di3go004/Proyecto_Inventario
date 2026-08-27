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

    def save(self, *args, **kwargs):
        """
        El rol de la aplicación manda sobre el permiso de Django: solo el
        administrador entra al panel /admin/. Así los dos no se pueden
        contradecir — que alguien quede con rol de operador pero con acceso
        al panel, o al revés, según por dónde se le haya editado.

        A los superusuarios no se les toca: si se les quitara is_staff se
        perdería la única puerta de entrada al panel cuando algo falle.
        """
        if not self.is_superuser:
            self.is_staff = self.rol == self.Rol.ADMINISTRADOR
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"
