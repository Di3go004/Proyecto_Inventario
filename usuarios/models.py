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
        # Carga el catálogo y nada más: ni movimientos, ni reportes, ni
        # valorización. Existe porque los practicantes se encargan de dejar
        # los productos bien capturados, uno por uno.
        PRACTICANTE = 'practicante', 'Practicante'

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
    def es_practicante(self):
        return self.rol == self.Rol.PRACTICANTE

    @property
    def puede_registrar_boletas(self):
        """
        Quién registra el talonario de Bodega 1 y 2: entradas (FO-SE-013),
        salidas (FO-SE-012) y la devolución de lo que salió a préstamo o demo.

        La devolución va junto con la salida y no aparte: quien puede sacar un
        equipo a demo tiene que poder registrar que volvió. Separarlas dejaría
        préstamos abiertos que su propio autor no puede cerrar.
        """
        return self.rol in (
            self.Rol.ADMINISTRADOR, self.Rol.OPERADOR, self.Rol.PRACTICANTE,
        )

    @property
    def puede_mover_tecnica(self):
        """
        Quién mueve la herramienta de uso interno: préstamos (FO-SE-066) y
        bajas de existencia.

        Va aparte de las boletas de Bodega 1 y 2 porque son dos trabajos
        distintos. Cuando el practicante pasó a registrar entradas y salidas,
        un solo permiso de "mover inventario" le habría abierto también la
        herramienta, que no es lo suyo.
        """
        return self.rol in (self.Rol.ADMINISTRADOR, self.Rol.OPERADOR)

    @property
    def puede_editar_catalogo(self):
        """Quién puede crear, editar y eliminar productos del catálogo."""
        return self.rol in (self.Rol.ADMINISTRADOR, self.Rol.PRACTICANTE)

    @property
    def puede_ver_reportes(self):
        """
        Quién ve los reportes y, con ellos, cuánto vale el inventario.

        El operador mueve bodega —registra entradas, salidas y préstamos—
        pero no necesita la valorización para eso, y es información de la
        empresa que no le toca. Para contabilidad, en cambio, es la razón de
        ser de su acceso: consulta e imprime, no modifica (RF-04).

        Manda también sobre las tarjetas de valorización del Resumen: es el
        mismo dato, y no tendría sentido cerrarle el reporte y enseñárselo en
        la portada.
        """
        return self.rol in (self.Rol.ADMINISTRADOR, self.Rol.CONTABILIDAD)

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
