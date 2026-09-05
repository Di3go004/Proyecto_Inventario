from django.db import models

# Lo dicen la restricción de la base y el formulario, en las dos bodegas:
# un solo texto para que el operador lea siempre lo mismo. Vive acá y no
# en ventas porque Bodega Técnica también lleva umbrales.
UMBRALES_EN_ORDEN = 'Los umbrales deben cumplir: crítico ≤ alerta ≤ óptimo.'


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

    class Origen(models.TextChoices):
        LOCAL = 'local', 'Local'
        EXTRANJERO = 'extranjero', 'Extranjero'

    nombre = models.CharField(max_length=150, unique=True)

    # Vacío = todavía nadie lo clasificó. Se deja así a propósito en vez de
    # asumir "local": los proveedores que entran por la carga masiva o al
    # escribirlos en el formulario de un producto no pasan por nadie que lo
    # sepa, y guardar una suposición como si fuera un dato es peor que
    # admitir que falta. La lista los muestra aparte para poder repasarlos.
    origen = models.CharField(
        max_length=12, choices=Origen.choices, blank=True, verbose_name='Origen',
    )

    contacto = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def es_extranjero(self):
        """
        Importar tarda semanas o meses. Sirve para saber, al ver qué reponer,
        qué hay que pedir con mucha más anticipación.
        """
        return self.origen == self.Origen.EXTRANJERO

    @property
    def sin_clasificar(self):
        return not self.origen
