from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import Bodega, Categoria, Proveedor


class Activo(models.Model):
    """
    Catálogo de Bodega Técnica (FO-SE-065). A diferencia de Articulo, cada
    activo es una unidad física que se identifica y se presta — no se
    "cuenta" como stock de un mismo modelo.
    """

    class Estado(models.TextChoices):
        BUEN_ESTADO = 'buen_estado', 'Buen estado'
        MAL_ESTADO = 'mal_estado', 'Mal estado'
        DE_BAJA = 'de_baja', 'De baja'

    codigo_interno = models.CharField(max_length=50, unique=True)
    nombre_producto = models.CharField(max_length=200)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)

    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'modulo': Categoria.Modulo.TECNICA},
    )
    bodega = models.ForeignKey(
        Bodega, on_delete=models.PROTECT, related_name='activos',
        limit_choices_to={'tipo': Bodega.Tipo.TECNICA},
    )
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Igual que en Articulo: se puede subir el archivo o pegar un link externo.
    imagen = models.ImageField(upload_to='activos/', blank=True, null=True)
    imagen_url = models.CharField(max_length=300, blank=True, verbose_name='URL de imagen (alternativa)')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BUEN_ESTADO)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Activo'
        verbose_name_plural = 'Activos'
        ordering = ['nombre_producto']

    def __str__(self):
        return f"{self.codigo_interno} — {self.nombre_producto}"

    @property
    def foto(self):
        """La imagen a mostrar: la subida tiene prioridad sobre la URL externa."""
        if self.imagen:
            return self.imagen.url
        return self.imagen_url or None

    @property
    def esta_prestado(self):
        """Recorre en Python en vez de hacer .filter(): así aprovecha el
        prefetch_related('prestamos') de la vista y el catálogo se resuelve
        en 2 consultas en total, no en una por cada activo (N+1)."""
        return any(p.fecha_regreso is None for p in self.prestamos.all())


class PrestamoActivo(models.Model):
    """
    Reemplaza FO-SE-066: una fila = un ciclo de préstamo. Sale y, cuando
    regresa, se completan las columnas de regreso en la misma fila.
    """

    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name='prestamos')
    cantidad = models.PositiveIntegerField(default=1)

    solicitante = models.CharField(max_length=150)
    fecha_salida = models.DateTimeField(auto_now_add=True)
    entregado_por = models.CharField(max_length=150, blank=True)
    estado_al_salir = models.CharField(
        max_length=20,
        choices=[(Activo.Estado.BUEN_ESTADO, 'Buen estado'), (Activo.Estado.MAL_ESTADO, 'Mal estado')],
    )

    fecha_regreso = models.DateTimeField(null=True, blank=True)
    recibido_por = models.CharField(max_length=150, blank=True)
    estado_al_regresar = models.CharField(max_length=20, choices=Activo.Estado.choices, blank=True)

    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='prestamos_registrados',
    )

    class Meta:
        verbose_name = 'Préstamo de activo'
        verbose_name_plural = 'Préstamos de activos'
        ordering = ['-fecha_salida']
        constraints = [
            # RF-07: un mismo activo no puede tener dos préstamos abiertos a la vez.
            models.UniqueConstraint(
                fields=['activo'], condition=models.Q(fecha_regreso__isnull=True),
                name='ux_prestamo_abierto_por_activo',
            ),
        ]

    def __str__(self):
        estado = 'afuera' if self.fecha_regreso is None else 'devuelto'
        return f"{self.activo.codigo_interno} · {self.solicitante} ({estado})"

    def clean(self):
        if self.activo_id and not self.pk and self.activo.estado == Activo.Estado.DE_BAJA:
            raise ValidationError('El activo está dado de baja y no se puede prestar.')
