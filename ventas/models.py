import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.models import Bodega, Categoria, Proveedor


class Articulo(models.Model):
    """
    Catálogo de Bodega 1 y 2 (venta). El stock_actual se recalcula solo
    desde MovimientoVenta.save() (RF-08) — nunca se edita a mano.

    codigo_interno se estandariza como "SE-MODELO-CAPACIDAD" y se genera
    solo si se deja en blanco (al crear a mano, al importar desde Excel más
    adelante, o desde el admin) — el administrador siempre puede
    sobreescribirlo si un producto necesita algo distinto. No aplica igual
    en Bodega Técnica: ahí el código lo asigna la empresa a mano, no
    depende de modelo/capacidad.
    """

    codigo_interno = models.CharField(max_length=50, unique=True, blank=True)
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
    # Dos formas de poner una foto: subiéndola desde el equipo (la que se
    # usa primero si existe) o pegando un link externo como alternativa
    # rápida cuando no se tiene el archivo a la mano.
    imagen = models.ImageField(upload_to='articulos/', blank=True, null=True)
    imagen_url = models.CharField(max_length=300, blank=True, verbose_name='URL de imagen (alternativa)')

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

    @staticmethod
    def _slug(valor, forzar_mayusculas=True):
        """Sin espacios ni símbolos raros, unidos por guiones (el punto
        decimal sí se conserva, ej. "4.2V").

        El modelo se fuerza a mayúsculas (es un código de fábrica, estilo
        SKU). La capacidad se deja tal cual se escribió: el Sistema
        Internacional de Unidades es sensible a mayúsculas/minúsculas —
        "kg", "g", "t" van en minúscula, pero "V" (voltios), "A" (amperios),
        "W" (vatios) van en mayúscula. Forzar un solo caso rompería esa
        notación (un adaptador de "9V" no es lo mismo que "9v").
        """
        limpio = re.sub(r'[^A-Za-z0-9.]+', '-', (valor or '').strip()).strip('-.')
        return limpio.upper() if forzar_mayusculas else limpio

    def generar_codigo_interno(self):
        """SE-MODELO-capacidad (la capacidad respeta su escritura original, ver _slug)."""
        partes = ['SE'] + [p for p in (self._slug(self.modelo), self._slug(self.capacidad, forzar_mayusculas=False)) if p]
        return '-'.join(partes)

    def save(self, *args, **kwargs):
        if not self.codigo_interno:
            base = self.generar_codigo_interno()
            codigo = base
            sufijo = 2
            # Si ya existe (otro producto con el mismo modelo+capacidad),
            # se agrega -2, -3... en vez de fallar por duplicado.
            while Articulo.objects.filter(codigo_interno=codigo).exclude(pk=self.pk).exists():
                codigo = f"{base}-{sufijo}"
                sufijo += 1
            self.codigo_interno = codigo
        super().save(*args, **kwargs)

    @property
    def foto(self):
        """La imagen a mostrar: la subida tiene prioridad sobre la URL externa."""
        if self.imagen:
            return self.imagen.url
        return self.imagen_url or None

    def calcular_stock_desde_movimientos(self):
        """
        Fuente de verdad del stock (RF-08): se deriva SIEMPRE de los
        movimientos, nunca de sumas/restas acumuladas. Así, si un movimiento
        se edita o se borra (cosa posible desde el panel de administración),
        el stock vuelve a cuadrar solo en vez de quedar desincronizado.

          ingresos - salidas + salidas de préstamo/demo ya devueltas
        """
        from django.db.models import Case, IntegerField, Sum, When

        resultado = self.movimientos.aggregate(
            total=Sum(
                Case(
                    When(tipo_documento=MovimientoVenta.TipoDocumento.INGRESO, then=models.F('cantidad')),
                    # Un préstamo/demo ya devuelto salió y volvió: neto cero.
                    When(
                        tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
                        tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
                        fecha_devolucion__isnull=False,
                        then=0,
                    ),
                    When(tipo_documento=MovimientoVenta.TipoDocumento.SALIDA, then=-models.F('cantidad')),
                    default=0,
                    output_field=IntegerField(),
                )
            )
        )
        return resultado['total'] or 0

    def recalcular_stock(self):
        """Recalcula y guarda stock_actual. Devuelve el nuevo valor."""
        total = self.calcular_stock_desde_movimientos()
        Articulo.objects.filter(pk=self.pk).update(stock_actual=total)
        self.stock_actual = total
        return total

    @property
    def valor_en_bodega(self):
        """Lo que vale lo que hay de este artículo: precio × existencia (RF-14)."""
        return self.precio * self.stock_actual

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
        # Saldo inicial al crear un artículo nuevo por carga masiva desde
        # Excel (RF-09) — no es una compra real, es "así arrancó el conteo".
        AJUSTE_INICIAL = 'ajuste_inicial', 'Ajuste / Saldo inicial'

    # Un mismo folio agrupa todas las líneas de un documento: una boleta
    # FO-SE-013/012 lleva varios productos en la misma hoja. Por eso no es
    # único — se indexa para recuperar el documento completo de un jalón.
    folio = models.CharField(max_length=30, blank=True, db_index=True)
    tipo_documento = models.CharField(max_length=10, choices=TipoDocumento.choices)
    tipo_transaccion = models.CharField(max_length=20, choices=TipoTransaccion.choices)

    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name='movimientos')
    cantidad = models.PositiveIntegerField()

    # Editable a propósito (no auto_now_add): las boletas de papel traen su
    # propia fecha y muchas veces se digitan al día siguiente, así que el
    # operador tiene que poder registrar cuándo ocurrió de verdad.
    fecha = models.DateTimeField(default=timezone.now)
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

    @classmethod
    def siguiente_folio(cls, tipo_documento):
        """
        Correlativo por tipo de documento, imitando la numeración que hoy
        viene preimpresa en los formatos de papel: ING-00001 para FO-SE-013
        (ingreso) y SAL-00001 para FO-SE-012 (salida).

        Se ordena por el folio como texto — funciona porque el número va
        rellenado con ceros a un ancho fijo. Si alguien escribió un folio a
        mano con otro formato, se ignora en vez de reventar.
        """
        prefijo = 'ING' if tipo_documento == cls.TipoDocumento.INGRESO else 'SAL'
        ultimo = (
            cls.objects.filter(folio__startswith=f'{prefijo}-')
            .order_by('-folio')
            .values_list('folio', flat=True)
            .first()
        )
        numero = 1
        if ultimo:
            try:
                numero = int(ultimo.rsplit('-', 1)[-1]) + 1
            except ValueError:
                numero = cls.objects.filter(folio__startswith=f'{prefijo}-').count() + 1
        return f'{prefijo}-{numero:05d}'

    @property
    def esta_afuera(self):
        """Préstamo/demo que ya salió y todavía no regresa (RF-06)."""
        return (
            self.tipo_documento == self.TipoDocumento.SALIDA
            and self.tipo_transaccion == self.TipoTransaccion.PRESTAMO_DEMO
            and self.fecha_devolucion is None
        )

    @property
    def signo(self):
        """+1 si suma al stock, -1 si resta, 0 si es un préstamo ya devuelto.

        Es la misma regla que aplica calcular_stock_desde_movimientos, pero
        en Python, para pintar el kardex sin volver a consultar la base.
        """
        if self.tipo_documento == self.TipoDocumento.INGRESO:
            return 1
        if self.tipo_transaccion == self.TipoTransaccion.PRESTAMO_DEMO and self.fecha_devolucion:
            return 0
        return -1

    def clean(self):
        if self.tipo_transaccion != self.TipoTransaccion.PRESTAMO_DEMO and (self.fecha_devolucion or self.devuelto_por):
            raise ValidationError('Solo un movimiento de tipo "Préstamo / Demo" puede tener datos de devolución.')

    def save(self, *args, **kwargs):
        """
        RF-08: después de guardar, el stock del artículo se recalcula desde
        CERO a partir de todos sus movimientos (ver
        Articulo.calcular_stock_desde_movimientos). Antes esto sumaba/restaba
        un delta solo al crear, y por eso editar o borrar un movimiento
        dejaba el stock desincronizado sin avisar.

        Si el resultado quedara negativo (una salida mayor a lo que hay),
        se cancela todo con un error claro en vez de reventar con el error
        técnico de la restricción de la base de datos.
        """
        with transaction.atomic():
            super().save(*args, **kwargs)

            articulo = Articulo.objects.select_for_update().get(pk=self.articulo_id)
            total = articulo.calcular_stock_desde_movimientos()
            if total < 0:
                raise ValidationError(
                    f'No hay suficiente stock de "{articulo.nombre_producto}": '
                    f'quedan {articulo.stock_actual} y se intentan sacar {self.cantidad}.'
                )
            articulo.recalcular_stock()


@receiver(post_delete, sender=MovimientoVenta)
def _recuadrar_stock_al_borrar(sender, instance, **kwargs):
    """
    Al borrar un movimiento el stock del artículo tiene que volver a cuadrar.

    Va como señal y no como MovimientoVenta.delete(): Django NO llama al
    delete() del modelo cuando se borra en bloque
    (MovimientoVenta.objects.filter(...).delete(), que es lo que usa el
    borrado múltiple del panel de administración y cualquier limpieza por
    consola). Con el override, ese camino dejaba stock_actual desfasado sin
    avisar; la señal sí se dispara en los dos casos.

    Si el artículo se está borrando también —cascada— ya no hay nada que
    recalcular, de ahí el filter().first().
    """
    articulo = Articulo.objects.filter(pk=instance.articulo_id).first()
    if articulo:
        articulo.recalcular_stock()
