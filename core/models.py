from django.db import models


class Bodega(models.Model):
    """
    Bodega 1 y Bodega 2 (venta) + Bodega Técnica (tecnica). Es tabla, no
    texto fijo, para poder agregar más bodegas sin rediseñar (RNF-09).
    """

    class Tipo(models.TextChoices):
        VENTA = 'venta', 'Venta'
        TECNICA = 'tecnica', 'Técnica'

    nombre = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Bodega'
        verbose_name_plural = 'Bodegas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    """Agrupa artículos/activos dentro de cada módulo (RF-02/RF-03)."""

    class Modulo(models.TextChoices):
        VENTAS = 'ventas', 'Ventas'
        TECNICA = 'tecnica', 'Técnica'

    nombre = models.CharField(max_length=100)
    modulo = models.CharField(max_length=10, choices=Modulo.choices)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        constraints = [
            models.UniqueConstraint(fields=['nombre', 'modulo'], name='uq_categoria_nombre_modulo'),
        ]
        ordering = ['modulo', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_modulo_display()})"


class Proveedor(models.Model):
    """
    Normalizado en su propia tabla porque el mismo proveedor se repite en
    muchas filas de los Excel actuales (KEERDA, BRECKNELL, LOCOSC...).
    """

    nombre = models.CharField(max_length=150, unique=True)
    contacto = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
