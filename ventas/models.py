from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import Bodega, Categoria, Proveedor


class Articulo(models.Model):
    """
    Catálogo de Bodega 1 y 2 (venta). El stock_actual se recalcula solo
    desde MovimientoVenta.save() (RF-08) — nunca se edita a mano.
    """

    codigo_interno = models.CharField(max_length=50, unique=True)
    numero_serie = models.CharField(max_length=100, unique=True, null=True, blank=True)
    nombre_producto = models.CharField(max_length=200)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    capacidad = models.CharField(max_length=50, blank=True)

    bodega = models.ForeignKey(
        Bodega, on_delete=models.PROTECT, related_name='articulos',
        limit_choices_to={'tipo': Bodega.Tipo.VENTA},
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'modulo': Categoria.Modulo.VENTAS},
    )
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    imagen_url = models.CharField(max_length=300, blank=True)

    stock_actual = models.PositiveIntegerField(default=0)
    # Umbrales pedidos por el usuario para Bodega 1: óptimo 20 / alerta 5 / crítico 2 (RF-11).
    stock_optimo = models.PositiveIntegerField(default=20)
    stock_alerta = models.PositiveIntegerField(default=5)
    stock_critico = models.PositiveIntegerField(default=2)

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Artículo'
        verbose_name_plural = 'Artículos'
        ordering = ['nombre_producto']
        constraints = [
            models.CheckConstraint(check=models.Q(stock_critico__lte=models.F('stock_alerta')), name='chk_critico_lte_alerta'),
            models.CheckConstraint(check=models.Q(stock_alerta__lte=models.F('stock_optimo')), name='chk_alerta_lte_optimo'),
        ]

    def __str__(self):
        return f"{self.codigo_interno} — {self.nombre_producto}"

    @property
    def nivel_alerta(self):
        """Para pintar el chip de RF-11 (óptimo/alerta/crítico) en catálogo y reportes."""
        if self.stock_actual <= self.stock_critico:
            return 'critico'
        if self.stock_actual <= self.stock_alerta:
            return 'alerta'
        if self.stock_actual >= self.stock_optimo:
            return 'optimo'
        return 'normal'


class MovimientoVenta(models.Model):
    """
    Reemplaza FO-SE-013 (ingreso) y FO-SE-012 (salida) en una sola tabla.
    Una salida de tipo préstamo/demo se "cierra" completando
    fecha_devolucion/devuelto_por en la misma fila (RF-06), igual que el
    patrón de una sola fila que ya usan en FO-SE-066.
    """

    class TipoDocumento(models.TextChoices):
        INGRESO = 'ingreso', 'Ingreso'
        SALIDA = 'salida', 'Salida'

    class TipoTransaccion(models.TextChoices):
        VENTA = 'venta', 'Venta'
        PRESTAMO_DEMO = 'prestamo_demo', 'Préstamo / Demo'
        REPUESTOS = 'repuestos', 'Repuestos'
        MATERIALES_OTRO = 'materiales_otro', 'Materiales / Otro'

    folio = models.CharField(max_length=30, blank=True)
    tipo_documento = models.CharField(max_length=10, choices=TipoDocumento.choices)
    tipo_transaccion = models.CharField(max_length=20, choices=TipoTransaccion.choices)

    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name='movimientos')
    cantidad = models.PositiveIntegerField()

    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='movimientos_venta',
    )

    solicitado_por = models.CharField(max_length=150, blank=True)
    entregado_por = models.CharField(max_length=150, blank=True)
    cliente_nombre = models.CharField(max_length=150, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    no_factura = models.CharField(max_length=50, blank=True)
    no_boleta = models.CharField(max_length=50, blank=True)
    envio_recibo = models.CharField(max_length=100, blank=True)
    observacion = models.TextField(blank=True)

    # Cierre de préstamo/demo (equivalente a "DEVUELTO POR" en FO-SE-012):
    fecha_devolucion = models.DateTimeField(null=True, blank=True)
    devuelto_por = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = 'Movimiento de venta'
        verbose_name_plural = 'Movimientos de venta'
        ordering = ['-fecha']
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name='chk_mov_venta_cantidad_positiva'),
        ]
        indexes = [
            models.Index(fields=['articulo', 'fecha']),
        ]

    def __str__(self):
        return f"{self.get_tipo_documento_display()} · {self.articulo.codigo_interno} · {self.cantidad}"

    def clean(self):
        if self.tipo_transaccion != self.TipoTransaccion.PRESTAMO_DEMO and (self.fecha_devolucion or self.devuelto_por):
            raise ValidationError('Solo un movimiento de tipo "Préstamo / Demo" puede tener datos de devolución.')

    def save(self, *args, **kwargs):
        """
        RF-08: recalcula stock_actual solo, en vez de que cada pantalla lo
        haga a mano. RF-06: cuando un préstamo/demo se cierra (se le pone
        fecha_devolucion), el equipo regresa físicamente a la bodega.
        Es la misma lógica descrita como triggers en BASE_DATOS.sql,
        trasladada aquí porque es donde vive en la implementación real.
        """
        es_nuevo = self._state.adding
        cerrando_prestamo = False

        if not es_nuevo:
            anterior = MovimientoVenta.objects.get(pk=self.pk)
            if (anterior.fecha_devolucion is None and self.fecha_devolucion is not None
                    and self.tipo_transaccion == self.TipoTransaccion.PRESTAMO_DEMO):
                cerrando_prestamo = True

        super().save(*args, **kwargs)

        if es_nuevo:
            delta = self.cantidad if self.tipo_documento == self.TipoDocumento.INGRESO else -self.cantidad
            Articulo.objects.filter(pk=self.articulo_id).update(stock_actual=models.F('stock_actual') + delta)
        elif cerrando_prestamo:
            Articulo.objects.filter(pk=self.articulo_id).update(stock_actual=models.F('stock_actual') + self.cantidad)
