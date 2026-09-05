from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.models import UMBRALES_EN_ORDEN, Bodega, Categoria, Proveedor


class Activo(models.Model):
    """
    Catálogo de Bodega Técnica (FO-SE-065).

    Igual que Articulo lleva existencia por cantidad: el FO-SE-065 real trae
    columna de existencia y 150 de sus 249 productos vienen con más de una
    unidad (hay 94 de uno y 62 de otro). Antes se modelaba como una unidad
    física por registro y por eso la valorización salía mal.

    Lo que sí lo diferencia de Bodega 1 y 2 es el flujo: acá **solo entran**
    cosas. La existencia baja únicamente cuando algo se da de baja —se
    descarta porque ya no sirve—, y los préstamos no la mueven: la
    herramienta sale y vuelve, sigue siendo de la bodega.
    """

    class Estado(models.TextChoices):
        # Van en orden de desgaste, no alfabético: así se leen como una escala
        # en el desplegable y en los reportes.
        #
        # "Próximo a reemplazo" es el aviso: la herramienta todavía sirve y se
        # sigue prestando, pero hay que ir comprando la de repuesto. Antes solo
        # había bueno y malo, y no había dónde anotar eso: quedaba en la cabeza
        # de quien la usó.
        BUEN_ESTADO = 'buen_estado', 'Buen estado'
        PROXIMO_A_REEMPLAZO = 'proximo_a_reemplazo', 'Próximo a reemplazo'
        MAL_ESTADO = 'mal_estado', 'Mal estado'

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

    # Se guarda calculado desde los movimientos, igual que Articulo.stock_actual:
    # se deriva siempre, nunca se suma/resta a mano (ver recalcular_existencia).
    existencia = models.PositiveIntegerField(default=0, editable=False)

    # Bombillos, flejes, pintura: cosas que se gastan. Para estas la baja no
    # amerita el trámite de registrar un descarte uno por uno, así que la
    # cantidad se corrige escribiéndola en el catálogo (queda como un ajuste
    # en el historial). En la herramienta y el equipo, en cambio, la
    # existencia solo se mueve con un ingreso o una baja.
    es_consumible = models.BooleanField(
        default=False, verbose_name='Es consumible',
        help_text='Cosas que se gastan (bombillos, flejes, pintura). Permite '
                  'corregir la existencia escribiéndola aquí, sin registrar una baja.',
    )
    # Igual que en Articulo: se puede subir el archivo o pegar un link externo.
    imagen = models.ImageField(upload_to='activos/', blank=True, null=True)
    imagen_url = models.CharField(max_length=300, blank=True, verbose_name='URL de imagen (alternativa)')
    # Mismos umbrales y mismos valores por defecto que Bodega 1 y 2 (RF-11).
    # Se comparan contra la existencia y no contra lo disponible: la
    # herramienta prestada sigue siendo de la bodega y va a volver, así que
    # prestarla no significa que haya que comprar más. Es la misma regla por
    # la que un préstamo no mueve la existencia.
    stock_optimo = models.PositiveIntegerField(default=20)
    stock_alerta = models.PositiveIntegerField(default=5)
    stock_critico = models.PositiveIntegerField(default=2)

    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.BUEN_ESTADO)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Activo'
        verbose_name_plural = 'Activos'
        ordering = ['nombre_producto']
        # Iguales a las de Articulo: el orden lo garantiza la base, no solo
        # el formulario, para que no entre por otra puerta (admin, consola,
        # carga masiva) una combinación que no tiene sentido.
        constraints = [
            models.CheckConstraint(
                check=models.Q(stock_critico__lte=models.F('stock_alerta')),
                name='chk_activo_critico_lte_alerta',
                violation_error_message=UMBRALES_EN_ORDEN,
            ),
            models.CheckConstraint(
                check=models.Q(stock_alerta__lte=models.F('stock_optimo')),
                name='chk_activo_alerta_lte_optimo',
                violation_error_message=UMBRALES_EN_ORDEN,
            ),
        ]

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

    @property
    def cantidad_afuera(self):
        """Cuántas unidades están prestadas ahora mismo.

        Recorre en Python por lo mismo que esta_prestado: la vista ya trae
        los préstamos con prefetch_related.
        """
        return sum(p.cantidad for p in self.prestamos.all() if p.fecha_regreso is None)

    @property
    def disponibles(self):
        """Lo que se puede prestar hoy: lo que hay menos lo que está afuera."""
        return self.existencia - self.cantidad_afuera

    @property
    def agotado(self):
        """Se dio de baja todo. Reemplaza al estado "De baja" que había antes,
        cuando cada registro era una sola unidad física."""
        return self.existencia == 0

    @property
    def nivel_alerta(self):
        """
        Para pintar el chip de reposición, igual que en Bodega 1 y 2 (RF-11).

        Mira la **existencia**, no lo disponible: si tres de cuatro taladros
        están prestados no hay que comprar taladros, van a volver. La alerta
        solo debe sonar cuando de verdad se está acabando.
        """
        if self.existencia <= self.stock_critico:
            return 'critico'
        if self.existencia <= self.stock_alerta:
            return 'alerta'
        if self.existencia >= self.stock_optimo:
            return 'optimo'
        return 'normal'

    @property
    def valor_en_bodega(self):
        """Lo que vale lo que hay: precio × existencia.

        Antes era solo el precio, porque se asumía una unidad por registro, y
        la valorización de la bodega salía corta.
        """
        return self.precio * self.existencia

    def calcular_existencia_desde_movimientos(self):
        """
        Fuente de verdad de la existencia: ingresos menos bajas (los ajustes
        entran con su propio signo). Los préstamos NO cuentan — la
        herramienta prestada sigue siendo de la bodega.
        """
        from django.db.models import Case, IntegerField, Sum, When

        resultado = self.movimientos.aggregate(
            total=Sum(
                Case(
                    When(tipo=MovimientoActivo.Tipo.BAJA, then=-models.F('cantidad')),
                    default=models.F('cantidad'),
                    output_field=IntegerField(),
                )
            )
        )
        return resultado['total'] or 0

    def recalcular_existencia(self):
        """Recalcula y guarda la existencia. Devuelve el nuevo valor."""
        total = self.calcular_existencia_desde_movimientos()
        Activo.objects.filter(pk=self.pk).update(existencia=max(total, 0))
        self.existencia = max(total, 0)
        return self.existencia


class MovimientoActivo(models.Model):
    """
    Lo que hace subir y bajar la existencia de Bodega Técnica.

    A esta bodega **solo entran** cosas: el ingreso se registra con el mismo
    FO-SE-013 que Bodega 1 y 2 —es el único formato que usan— y por eso
    comparte con MovimientoVenta la numeración de folio (un solo talonario,
    una sola serie).

    Lo único que baja la existencia es dar de baja: descartar algo que ya no
    sirve. La baja NO lleva boleta; solo queda el registro de qué se descartó
    y cuánto.

    Los préstamos viven aparte, en PrestamoActivo, y no tocan esta tabla: la
    herramienta prestada sigue siendo de la bodega.
    """

    class Tipo(models.TextChoices):
        INGRESO = 'ingreso', 'Ingreso'
        BAJA = 'baja', 'Baja'
        # Saldo con el que arrancó el conteo (carga masiva del FO-SE-065) y
        # correcciones de cantidad en los consumibles.
        AJUSTE = 'ajuste', 'Ajuste de existencia'

    class Motivo(models.TextChoices):
        DANADO = 'danado', 'Dañado / ya no sirve'
        EXTRAVIADO = 'extraviado', 'Extraviado'
        CONSUMIDO = 'consumido', 'Consumido / gastado'
        OTRO = 'otro', 'Otro'

    # Comparte serie con MovimientoVenta: es el mismo talonario FO-SE-013.
    # Vacío en las bajas y los ajustes, que no llevan boleta.
    folio = models.CharField(max_length=30, blank=True, db_index=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)

    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name='movimientos')
    cantidad = models.PositiveIntegerField()

    # Editable igual que en MovimientoVenta: la boleta de papel trae su
    # propia fecha y se digita después.
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='movimientos_tecnica',
    )

    # Del FO-SE-013, solo en los ingresos:
    solicitado_por = models.CharField(max_length=150, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    no_factura = models.CharField(max_length=50, blank=True)
    no_boleta = models.CharField(max_length=50, blank=True)

    # Solo en las bajas:
    motivo = models.CharField(max_length=20, choices=Motivo.choices, blank=True)

    observacion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Movimiento de Bodega Técnica'
        verbose_name_plural = 'Movimientos de Bodega Técnica'
        ordering = ['-fecha']
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name='chk_mov_activo_cantidad_positiva'),
        ]
        indexes = [
            models.Index(fields=['activo', 'fecha']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.activo.codigo_interno} · {self.cantidad}"

    @classmethod
    def siguiente_folio(cls):
        """
        El correlativo lo lleva MovimientoVenta, que mira las dos tablas: el
        FO-SE-013 es un solo talonario para las tres bodegas. Acá solo se
        delega para no tener dos implementaciones que se puedan desfasar.
        """
        from ventas.models import MovimientoVenta
        return MovimientoVenta.siguiente_folio(MovimientoVenta.TipoDocumento.INGRESO)

    @property
    def signo(self):
        """+1 si suma a la existencia, -1 si resta."""
        return -1 if self.tipo == self.Tipo.BAJA else 1

    def save(self, *args, **kwargs):
        """
        La existencia se recalcula desde cero después de guardar, igual que
        en Bodega 1 y 2: si un movimiento se edita o se borra, vuelve a
        cuadrar sola en vez de quedar desincronizada.
        """
        with transaction.atomic():
            super().save(*args, **kwargs)
            activo = Activo.objects.select_for_update().get(pk=self.activo_id)
            total = activo.calcular_existencia_desde_movimientos()
            if total < 0:
                raise ValidationError(
                    f'No se puede dar de baja esa cantidad de "{activo.nombre_producto}": '
                    f'hay {activo.existencia} y se intentan descartar {self.cantidad}.'
                )
            activo.recalcular_existencia()


@receiver(post_delete, sender=MovimientoActivo)
def _recuadrar_existencia_al_borrar(sender, instance, **kwargs):
    """
    Va como señal y no como delete() del modelo por lo mismo que en
    ventas.models: Django no llama al delete() del modelo cuando se borra en
    bloque, que es el camino del borrado múltiple del panel de
    administración y de cualquier limpieza por consola.
    """
    activo = Activo.objects.filter(pk=instance.activo_id).first()
    if activo:
        activo.recalcular_existencia()

class PrestamoActivo(models.Model):
    """
    Reemplaza FO-SE-066: una fila = un ciclo de préstamo. Sale y, cuando
    regresa, se completan las columnas de regreso en la misma fila.
    """

    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name='prestamos')
    cantidad = models.PositiveIntegerField(default=1)

    solicitante = models.CharField(max_length=150)
    # Editable igual que en MovimientoVenta: FO-SE-066 se llena a mano y se
    # digita después, así que la fecha real de salida la pone el operador.
    fecha_salida = models.DateTimeField(default=timezone.now)
    entregado_por = models.CharField(max_length=150, blank=True)
    # Los choices salen de Activo.Estado en vez de repetirse aquí: escritos a
    # mano, agregar un estado nuevo se olvidaba de este campo y la herramienta
    # no podía salir con él. La opción vacía la quita el formulario, que
    # propone "Buen estado" (ver tecnica/forms.py).
    estado_al_salir = models.CharField(max_length=30, choices=Activo.Estado.choices)

    fecha_regreso = models.DateTimeField(null=True, blank=True)
    recibido_por = models.CharField(max_length=150, blank=True)
    estado_al_regresar = models.CharField(max_length=30, choices=Activo.Estado.choices, blank=True)

    observacion = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='prestamos_registrados',
    )

    class Meta:
        verbose_name = 'Préstamo de activo'
        verbose_name_plural = 'Préstamos de activos'
        ordering = ['-fecha_salida']
        constraints = [
            models.CheckConstraint(
                check=models.Q(cantidad__gt=0), name='chk_prestamo_cantidad_positiva',
            ),
        ]
        # Antes había una restricción de "un solo préstamo abierto por
        # activo". Se quitó al pasar la bodega a existencia por cantidad:
        # con 10 bombillos, dos personas pueden tener unidades afuera a la
        # vez. Lo que se valida ahora es que no salga más de lo disponible,
        # en clean().

    def __str__(self):
        estado = 'afuera' if self.fecha_regreso is None else 'devuelto'
        return f"{self.activo.codigo_interno} · {self.solicitante} ({estado})"

    @property
    def esta_afuera(self):
        return self.fecha_regreso is None

    def clean(self):
        """
        No se puede prestar más de lo que hay disponible: lo que existe menos
        lo que ya está afuera en otros préstamos. Se cuenta consultando la
        base y no con la propiedad del activo, porque acá interesa el estado
        real en este instante, no el que trajo el prefetch de una vista.
        """
        if not self.activo_id:
            return

        if self.activo.agotado:
            raise ValidationError(
                f'"{self.activo.nombre_producto}" no tiene existencia: se dio de baja todo.'
            )

        if self.fecha_regreso:
            return

        afuera = (
            PrestamoActivo.objects
            .filter(activo_id=self.activo_id, fecha_regreso__isnull=True)
            .exclude(pk=self.pk)
            .aggregate(total=models.Sum('cantidad'))['total'] or 0
        )
        disponibles = self.activo.existencia - afuera
        if self.cantidad > disponibles:
            raise ValidationError(
                f'Solo hay {disponibles} disponible(s) de "{self.activo.nombre_producto}": '
                f'existen {self.activo.existencia} y {afuera} ya están afuera.'
            )

    def save(self, *args, **kwargs):
        """
        RF-07: al cerrar el préstamo, el estado con el que regresó la
        herramienta pasa a ser el estado actual del activo. Es justo lo que
        hoy no queda registrado en el Excel — si un taladro sale bueno y
        vuelve dañado, el catálogo tiene que enterarse solo, sin depender de
        que alguien se acuerde de editarlo aparte.

        Si vuelve inservible, quien lo recibe registra la baja aparte: el
        estado dice en qué condición está, la baja lo saca de la existencia.
        """
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.fecha_regreso and self.estado_al_regresar:
                Activo.objects.filter(pk=self.activo_id).update(estado=self.estado_al_regresar)
