import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import functions  # noqa: F401  (models.functions.Upper)
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core import fechas
from core.models import UMBRALES_EN_ORDEN, Bodega, Categoria, Proveedor

# Cómo se escribe "no tiene número de serie". Es la abreviatura que ya usan
# en la empresa, así que se pone tal cual en pantalla y en los reportes en
# vez de una raya. Vive en una constante para que diga lo mismo en todos
# lados: se muestra en el catálogo, en la ficha, en la vista previa de la
# carga masiva y en el Excel de existencias.
SIN_SERIAL = 'S/S'

# Lo que, escrito en el campo, quiere decir "no tiene serial". Se compara sin
# espacios y en mayúsculas, así que "s/s" y "S / S" también caen aquí.
_ESCRITURAS_DE_SIN_SERIAL = {'S/S', 'SINSERIE', 'SINSERIAL'}


def limpiar_serial(texto):
    """
    Deja el serial como se guarda: sin espacios de sobra, y vacío (NULL) si
    lo que vino en realidad significa "no tiene".

    Hace falta porque "S/S" está a la vista en todas las pantallas y en el
    manual, así que tarde o temprano alguien lo escribe en el campo. Y como
    el serial es único, el primero se guardaría y el segundo se caería con
    "ya existe un artículo con ese número de serie": un error incomprensible
    para quien solo quiso decir que la báscula no traía placa.

    Lo mismo llega del Excel viejo, donde esa columna trae "S/S", "s/s" y
    celdas rellenas con puras rayas.
    """
    texto = (texto or '').strip()
    if not texto:
        return None
    if texto.replace(' ', '').upper() in _ESCRITURAS_DE_SIN_SERIAL:
        return None
    if set(texto) <= set('-–—.'):
        return None
    return texto


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

    # Los equipos —indicadores, básculas, balanzas— se controlan por unidad:
    # cada aparato trae su número de serie y la empresa necesita saber cuál
    # entró y cuál salió, no solo cuántos hay. Los repuestos no: nadie le pone
    # serial a cada uno de 500 conectores.
    #
    # El serial vivía acá, en el producto, con restricción de único. Eso solo
    # funciona si cada producto es una sola unidad física: con 4 indicadores
    # del mismo modelo el campo no daba, porque solo cabía un serial. Ahora
    # vive en UnidadArticulo, una fila por aparato.
    lleva_serie = models.BooleanField(
        default=False, verbose_name='Lleva número de serie',
        help_text='Equipos que se controlan uno por uno por su serial. Los '
                  'repuestos y consumibles van sin marcar, por cantidad.',
    )
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
        # El mensaje va escrito a mano: sin él, Django enseña el nombre técnico
        # de la restricción ("No se cumple la restricción
        # chk_critico_lte_alerta"), que a quien está capturando el catálogo no
        # le dice nada. Es el mismo texto que valida el formulario, así que se
        # vea por donde se vea, se lee igual.
        constraints = [
            models.CheckConstraint(
                check=models.Q(stock_critico__lte=models.F('stock_alerta')),
                name='chk_critico_lte_alerta',
                violation_error_message=UMBRALES_EN_ORDEN,
            ),
            models.CheckConstraint(
                check=models.Q(stock_alerta__lte=models.F('stock_optimo')),
                name='chk_alerta_lte_optimo',
                violation_error_message=UMBRALES_EN_ORDEN,
            ),
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

          ingresos - salidas

        Lo que regresa de una salida es un ingreso más (una devolución), con
        su propia fecha. Antes el regreso de un préstamo se anotaba en la
        misma salida y la volvía cero, y eso reescribía el pasado: el kardex
        pasaba a decir que el equipo nunca había salido.
        """
        from django.db.models import Case, IntegerField, Sum, When

        resultado = self.movimientos.aggregate(
            total=Sum(
                Case(
                    When(tipo_documento=MovimientoVenta.TipoDocumento.INGRESO, then=models.F('cantidad')),
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
    def serial(self):
        """
        Lo que se muestra en la columna de serial del catálogo.

        En los productos que no llevan serie es "S/S", igual que siempre: la
        abreviatura que ya usaban en la empresa. En los que sí la llevan no
        hay *un* serial que mostrar —hay varios—, así que se dice cuántas
        unidades hay y los seriales se listan en la ficha.
        """
        if not self.lleva_serie:
            return SIN_SERIAL
        cuantas = self.unidades_en_bodega
        return f'{cuantas} unidad' if cuantas == 1 else f'{cuantas} unidades'

    @property
    def unidades_en_bodega(self):
        """Cuántas unidades de este producto siguen en bodega."""
        return self.unidades.en_bodega().count()

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


def _ultimo_folio(modelo, prefijo):
    """El número más alto usado en esa serie, o 0 si no hay ninguno."""
    ultimo = (
        modelo.objects.filter(folio__startswith=f'{prefijo}-')
        .order_by('-folio')
        .values_list('folio', flat=True)
        .first()
    )
    if not ultimo:
        return 0
    try:
        return int(ultimo.rsplit('-', 1)[-1])
    except ValueError:
        # Alguien escribió un folio a mano con otro formato: se cuenta
        # cuántos hay en vez de reventar.
        return modelo.objects.filter(folio__startswith=f'{prefijo}-').count()

class MovimientoQuerySet(models.QuerySet):
    """Preguntas sobre las salidas que dependen de sus devoluciones."""

    def con_devueltas(self):
        # `suma_devuelta` y no `devueltas`: ese nombre ya es una propiedad del
        # modelo, y Django no puede escribir la columna anotada encima de ella.
        return self.annotate(
            suma_devuelta=models.functions.Coalesce(
                models.Sum('devoluciones__cantidad'), 0,
            ),
        )

    def salidas_pendientes(self):
        """Líneas de salida a las que todavía les falta resultado."""
        return (
            self.filter(tipo_documento=MovimientoVenta.TipoDocumento.SALIDA)
            .con_devueltas()
            .filter(cantidad__gt=models.F('cantidad_vendida') + models.F('suma_devuelta'))
        )

    def salidas_por_cerrar(self):
        """Líneas ya resueltas de boletas que el administrador no ha cerrado."""
        return (
            self.filter(
                tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
                fecha_cierre__isnull=True,
            )
            .con_devueltas()
            .filter(cantidad=models.F('cantidad_vendida') + models.F('suma_devuelta'))
        )


class MovimientoVenta(models.Model):
    """
    Reemplaza FO-SE-013 (ingreso) y FO-SE-012 (salida) en una sola tabla.

    **Una salida nace abierta.** Cuando el técnico se lleva algo, nadie sabe
    todavía si se va a instalar o si va a regresar: eso se sabe cuando vuelve.
    Por eso cada línea sale como pendiente y después se le registra su
    resultado —cuántas se vendieron y cuántas regresaron—, y cuando ya no le
    falta nada a ninguna línea, el administrador cierra la boleta.

    Lo que regresa no se anota en la salida: es su propio movimiento, un
    ingreso de devolución amarrado a la línea (`devolucion_de`), con la fecha
    en que regresó. Así el regreso puede ser parcial —de 4 celdas regresa 1—
    y el kardex conserva el día en que salieron.
    """

    class TipoDocumento(models.TextChoices):
        INGRESO = 'ingreso', 'Ingreso'
        SALIDA = 'salida', 'Salida'

    class TipoTransaccion(models.TextChoices):
        VENTA = 'venta', 'Venta'
        PRESTAMO_DEMO = 'prestamo_demo', 'Préstamo / Demo'
        # Lo que se lleva el técnico sin saber si lo va a usar: se resuelve
        # cuando regresa. No es lo mismo que un demo, que va a un cliente.
        CON_TECNICO = 'con_tecnico', 'Con el técnico'
        REPUESTOS = 'repuestos', 'Repuestos'
        MATERIALES_OTRO = 'materiales_otro', 'Materiales / Otro'
        # Lo que regresó de una salida. No se registra en una boleta de
        # ingreso: nace al registrar el resultado de la línea que salió.
        # Se lee "Devuelto" y no "Devolución": en comercio una devolución es
        # el cliente regresando algo que salió malo, y esto es lo que el
        # técnico trae de regreso — el "DEVUELTO POR" del FO-SE-012.
        DEVOLUCION = 'devolucion', 'Devuelto'
        # Saldo inicial al crear un artículo nuevo por carga masiva desde
        # Excel (RF-09) — no es una compra real, es "así arrancó el conteo".
        AJUSTE_INICIAL = 'ajuste_inicial', 'Ajuste / Saldo inicial'

    # Cómo puede salir cada línea de una boleta FO-SE-012. Repuestos y
    # materiales ya no se ofrecen al salir: si se usaron, se vendieron.
    TIPOS_DE_SALIDA = (
        TipoTransaccion.CON_TECNICO,
        TipoTransaccion.PRESTAMO_DEMO,
        TipoTransaccion.VENTA,
    )

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

    # El precio al que ocurrió ESTE movimiento, no el que el producto tenga hoy.
    #
    # Antes la boleta impresa sacaba el precio del catálogo, así que reimprimir
    # un FO-SE-013 después de un cambio de precio producía un documento distinto
    # al que se firmó y se archivó. Un documento que se contradice a sí mismo es
    # justo lo que no puede pasar en un sistema de gestión.
    #
    # En el ingreso se captura, porque es el precio de la factura del proveedor.
    # En los demás movimientos lo copia save() del catálogo.
    # Vacío (NULL) significa "nadie lo capturó", y es distinto de un precio de
    # cero, que sí existe: muestras, garantías, reposiciones sin costo. Con 0
    # como "sin capturar" no se podía registrar ninguno de esos casos, porque
    # save() lo confundía con un olvido y lo pisaba con el del catálogo.
    #
    # Después de guardar nunca queda en NULL: save() lo rellena al crear.
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )

    solicitado_por = models.CharField(max_length=150, blank=True)
    entregado_por = models.CharField(max_length=150, blank=True)
    cliente_nombre = models.CharField(max_length=150, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    no_factura = models.CharField(max_length=50, blank=True)
    envio_recibo = models.CharField(max_length=100, blank=True)
    observacion = models.TextField(blank=True)

    # --- El resultado de una línea de salida -------------------------------
    #
    # Cuántas de esta línea se confirmaron vendidas. Las que regresaron no van
    # acá: son sus devoluciones. Lo que falta para completar la cantidad está
    # pendiente. Un repuesto que se usó en un trabajo cuenta como vendido: se
    # lo llevó el cliente.
    cantidad_vendida = models.PositiveIntegerField(default=0)

    # En una devolución, la línea de salida de la que regresó.
    devolucion_de = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='devoluciones',
    )
    # Quién trajo de regreso lo que salió: el "DEVUELTO POR" del FO-SE-012.
    # Va en la devolución, que es la que registra el regreso.
    devuelto_por = models.CharField(max_length=150, blank=True)

    # Cuándo y quién cerró la boleta. Se escribe en todas las líneas del folio
    # a la vez, igual que el resto del encabezado. Cerrada, ya no se le puede
    # cambiar ningún resultado.
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='boletas_cerradas',
    )

    objects = MovimientoQuerySet.as_manager()

    class Meta:
        verbose_name = 'Movimiento de venta'
        verbose_name_plural = 'Movimientos de venta'
        ordering = ['-fecha']
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name='chk_mov_venta_cantidad_positiva'),
            models.CheckConstraint(
                check=models.Q(cantidad_vendida__lte=models.F('cantidad')),
                name='chk_mov_venta_vendidas_hasta_cantidad',
                violation_error_message='No se pueden vender más unidades de las que salieron.',
            ),
            # Una devolución es algo que entra: nunca una salida.
            models.CheckConstraint(
                check=models.Q(devolucion_de__isnull=True) | models.Q(tipo_documento='ingreso'),
                name='chk_mov_venta_devolucion_es_ingreso',
            ),
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

        Los ingresos se numeran mirando TAMBIÉN los de Bodega Técnica: el
        FO-SE-013 es un solo talonario para las tres bodegas, así que la
        serie tiene que ser una sola. Si se contaran por separado, dos
        boletas distintas saldrían con el mismo número.

        Se ordena por el folio como texto — funciona porque el número va
        rellenado con ceros a un ancho fijo. Si alguien escribió un folio a
        mano con otro formato, se ignora en vez de reventar.
        """
        prefijo = 'ING' if tipo_documento == cls.TipoDocumento.INGRESO else 'SAL'

        candidatos = [_ultimo_folio(cls, prefijo)]
        if prefijo == 'ING':
            from tecnica.models import MovimientoActivo
            candidatos.append(_ultimo_folio(MovimientoActivo, prefijo))

        numero = max(candidatos) + 1
        return f'{prefijo}-{numero:05d}'

    @property
    def es_salida(self):
        return self.tipo_documento == self.TipoDocumento.SALIDA

    @property
    def es_devolucion(self):
        return self.devolucion_de_id is not None

    @property
    def es_demo(self):
        return self.tipo_transaccion == self.TipoTransaccion.PRESTAMO_DEMO

    @property
    def devueltas(self):
        """
        Cuántas de esta línea regresaron, sumando sus devoluciones.

        Se suma en Python para aprovechar el prefetch de `devoluciones`: las
        pantallas preguntan esto por cada línea de la lista.
        """
        if not self.es_salida:
            return 0
        return sum(devolucion.cantidad for devolucion in self.devoluciones.all())

    @property
    def pendientes(self):
        """Lo que falta resolver: ni confirmado vendido ni regresado."""
        if not self.es_salida:
            return 0
        return self.cantidad - self.cantidad_vendida - self.devueltas

    @property
    def tiene_pendientes(self):
        return self.pendientes > 0

    @property
    def esta_cerrada(self):
        return self.fecha_cierre is not None

    @property
    def resultado(self):
        """
        Cómo va la línea, en partes: [('vendidas', 3), ('devueltas', 1)].

        En partes porque una línea puede terminar repartida: de 4 celdas se
        instalan 3 y regresa 1. Solo trae las partes que no son cero.
        """
        if not self.es_salida:
            return []
        partes = [
            ('vendidas', self.cantidad_vendida),
            ('devueltas', self.devueltas),
            ('pendientes', self.pendientes),
        ]
        return [(nombre, cuantas) for nombre, cuantas in partes if cuantas]

    @property
    def signo(self):
        """+1 si suma al stock, -1 si resta.

        Es la misma regla que aplica calcular_stock_desde_movimientos, pero
        en Python, para pintar el kardex sin volver a consultar la base. Ya
        no hay caso especial para los préstamos: lo que regresa es su propio
        ingreso.
        """
        if self.tipo_documento == self.TipoDocumento.INGRESO:
            return 1
        return -1

    def estado_de_unidades(self):
        """
        Qué pasó con cada aparato de esta línea de salida:
        [(unidad, 'vendida' | 'devuelta' | 'pendiente'), ...].

        Devuelta si está en alguna devolución de esta línea; vendida si su
        paso por esta salida quedó marcado así; si no, sigue pendiente.
        """
        devueltas = {
            unidad.pk
            for devolucion in self.devoluciones.all()
            for unidad in devolucion.unidades.all()
        }
        vendidas = {
            paso.unidad_id for paso in self.pasos_de_unidad.all() if paso.vendida
        }
        estados = []
        for unidad in self.unidades.all():
            if unidad.pk in devueltas:
                estados.append((unidad, 'devuelta'))
            elif unidad.pk in vendidas:
                estados.append((unidad, 'vendida'))
            else:
                estados.append((unidad, 'pendiente'))
        return estados

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
        # Si nadie capturó un precio, se copia el del catálogo al crear. Va acá
        # y no en cada pantalla porque los movimientos nacen en cinco lugares
        # distintos —ingreso, salida, baja, ajuste y las dos cargas masivas— y
        # basta que uno se olvide para que ese movimiento quede en Q 0.00 para
        # siempre. Solo al crear: después el precio es historia y no se toca
        # aunque el catálogo cambie, que es justamente el punto.
        if not self.pk and self.precio_unitario is None and self.articulo_id:
            self.precio_unitario = self.articulo.precio

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


# Dónde está una unidad: +1 en bodega, 0 fuera. Es la misma regla que
# Articulo.calcular_stock_desde_movimientos aplicada a un solo aparato —un
# ingreso la mete y una salida la saca—. Si regresa, entra con su devolución,
# que es otro ingreso. Escrita una sola vez para que la existencia del
# producto y el paradero de sus unidades no puedan contradecirse.
SALDO_DE_UNIDAD = models.Sum(
    models.Case(
        models.When(movimientos__tipo_documento='ingreso', then=1),
        models.When(movimientos__tipo_documento='salida', then=-1),
        default=0,
        output_field=models.IntegerField(),
    )
)


class UnidadQuerySet(models.QuerySet):
    """
    Las unidades se preguntan siempre por su saldo, nunca por una columna de
    estado: así no hay ninguna que mantener en sincronía.
    """

    def con_saldo(self):
        return self.annotate(saldo=SALDO_DE_UNIDAD)

    def en_bodega(self):
        """Las que se pueden vender o prestar hoy."""
        return self.con_saldo().filter(saldo__gt=0)

    def fuera(self):
        return self.con_saldo().filter(saldo__lte=0)


class UnidadArticulo(models.Model):
    """
    Un aparato físico, identificado por su número de serie.

    Cuatro indicadores del mismo modelo son cuatro unidades: el mismo
    producto en el catálogo —mismo precio, misma categoría, mismos
    umbrales— pero cada uno con su serial, y la empresa necesita saber
    cuál entró y cuál salió.

    De quién se compró y a quién se vendió no se guardan acá: ya los trae
    el movimiento que la hizo entrar y el que la hizo salir, que llevan
    proveedor, factura y cliente. Duplicarlos sería tener dos versiones
    del mismo dato.

    **Dónde está la unidad no es un campo, se deriva de sus movimientos**,
    igual que la existencia del producto (ver
    Articulo.calcular_stock_desde_movimientos). Es la misma regla aplicada a
    una sola unidad, y por eso las dos cuentas no pueden discrepar.

    Solo aplica a Bodega 1 y 2. La herramienta de Bodega Técnica se lleva
    por cantidad, no por unidad.
    """

    articulo = models.ForeignKey(
        Articulo, on_delete=models.PROTECT, related_name='unidades',
    )
    # Único en todo el sistema: un serial identifica un aparato físico, no
    # una posición dentro de un producto.
    numero_serie = models.CharField(max_length=100, unique=True)

    # Por qué movimientos pasó esta unidad. Antes eran dos llaves fijas
    # —movimiento_ingreso y movimiento_salida— y no alcanzaban: un equipo
    # que sale a demo y regresa vuelve a salir después, y la segunda salida
    # le pisaba la primera. La boleta del demo se quedaba sin sus seriales,
    # que es justo lo que no puede pasar con un documento ya firmado.
    movimientos = models.ManyToManyField(
        MovimientoVenta, through='MovimientoUnidad', related_name='unidades',
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    objects = UnidadQuerySet.as_manager()

    class Meta:
        verbose_name = 'Unidad'
        verbose_name_plural = 'Unidades'
        ordering = ['numero_serie']

    def __str__(self):
        return f'{self.articulo.codigo_interno} · {self.numero_serie}'

    @property
    def en_bodega(self):
        """
        La misma cuenta que SALDO_DE_UNIDAD, pero en Python.

        El nombre `saldo` queda libre a propósito: es como se llama la columna
        que agrega `con_saldo()`, y una propiedad con ese nombre le impide a
        Django escribirla al traer las filas.
        """
        return sum(movimiento.signo for movimiento in self.movimientos.all()) > 0

    @property
    def movimiento_ingreso(self):
        """Con qué documento entró la primera vez."""
        entradas = [
            m for m in self.movimientos.all()
            if m.tipo_documento == MovimientoVenta.TipoDocumento.INGRESO
        ]
        return min(entradas, key=lambda m: (m.fecha, m.id)) if entradas else None

    @property
    def movimiento_salida(self):
        """
        El documento que la tiene fuera **ahorita**, o None si está en bodega.

        Un demo devuelto no cuenta: la unidad volvió, y su salida ya no la
        tiene afuera. Los documentos anteriores siguen guardados y siguen
        listando sus seriales; lo que esta propiedad contesta es dónde está
        la unidad hoy.
        """
        if self.en_bodega:
            return None
        salidas = [
            m for m in self.movimientos.all()
            if m.tipo_documento == MovimientoVenta.TipoDocumento.SALIDA
        ]
        return max(salidas, key=lambda m: (m.fecha, m.id)) if salidas else None

    @property
    def estado(self):
        """Para pintarlo en la ficha del producto."""
        return 'En bodega' if self.en_bodega else 'Fuera de bodega'

    @property
    def boleta_de_referencia(self):
        """
        El número de boleta al que lleva la fila de esta unidad.

        Una unidad tiene dos boletas —con cuál entró y con cuál salió— y una
        fila un solo destino, así que se toma la que contesta la pregunta con
        la que uno abre la tabla: dónde está hoy. Si ya salió, la de salida;
        si sigue en bodega, la de ingreso. Vacío en la carga inicial, que no
        tiene boleta porque no hubo papel.
        """
        movimiento = self.movimiento_salida or self.movimiento_ingreso
        return movimiento.folio if movimiento else ''


class MovimientoUnidad(models.Model):
    """
    Qué unidades movió cada documento: una fila por serial de la boleta.

    Al borrar el movimiento se borra el vínculo (CASCADE), no la unidad. Es
    lo mismo que hace el stock: borrar una salida devuelve la existencia, y
    acá devuelve la unidad a bodega. Si fuera PROTECT las dos cuentas
    dirían cosas distintas después de un borrado.
    """

    movimiento = models.ForeignKey(
        MovimientoVenta, on_delete=models.CASCADE, related_name='pasos_de_unidad',
    )
    unidad = models.ForeignKey(
        UnidadArticulo, on_delete=models.CASCADE, related_name='pasos',
    )
    # Solo en las salidas: este aparato se confirmó vendido. Hace falta por
    # unidad porque en una línea con seriales hay que saber cuál se vendió y
    # cuál sigue pendiente, no solo cuántos.
    vendida = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Unidad del movimiento'
        verbose_name_plural = 'Unidades del movimiento'
        constraints = [
            models.UniqueConstraint(
                fields=['movimiento', 'unidad'], name='unidad_una_vez_por_movimiento',
            ),
        ]
        indexes = [models.Index(fields=['unidad', 'movimiento'])]

    def __str__(self):
        return f'{self.movimiento.folio} · {self.unidad.numero_serie}'


# ---------------------------------------------------------------------------
# Mover unidades
#
# Las dos únicas puertas por las que una unidad entra o sale. Van acá y no en
# la vista porque los movimientos nacen en varios lugares —la carga inicial
# del catálogo, la boleta de ingreso, la de salida— y el vínculo con el
# movimiento es lo que sostiene la regla de que nada se mueve sin respaldo.
# ---------------------------------------------------------------------------

def ingresar_unidades(movimiento, seriales):
    """
    Crea una unidad por serial y la ata al movimiento que la hizo entrar.

    Se llama siempre dentro de la transacción del que registra el documento:
    o entra la boleta completa con todos sus seriales, o no entra ninguno.
    """
    unidades = UnidadArticulo.objects.bulk_create([
        UnidadArticulo(articulo=movimiento.articulo, numero_serie=serial)
        for serial in seriales
    ])
    MovimientoUnidad.objects.bulk_create([
        MovimientoUnidad(movimiento=movimiento, unidad=unidad)
        for unidad in unidades
    ])
    return unidades


def sacar_unidades(movimiento, unidades, vendidas=False):
    """
    Ata a este movimiento las unidades que salen con él.

    La unidad no se marca ni se borra: queda registrada en el movimiento, y
    de ahí se deduce que ya no está en bodega. Si el movimiento se borra, o
    si la unidad regresa con su devolución, vuelve sola, sin que nadie tenga
    que acordarse de destildar nada.

    `vendidas` es para la línea que sale ya vendida: nace resuelta.
    """
    MovimientoUnidad.objects.bulk_create([
        MovimientoUnidad(movimiento=movimiento, unidad=unidad, vendida=vendidas)
        for unidad in unidades
    ])


def unidades_con_serial(seriales):
    """
    Las unidades que ya tienen alguno de esos seriales, sin importar cómo se
    escribieron las mayúsculas.

    Va en un solo lugar porque los seriales se comparan en tres pantallas —el
    alta del producto, la boleta de ingreso y el aviso mientras se escriben—
    y bastaba que una comparara distinto para que el mismo aparato entrara dos
    veces con otra escritura. El alta comparaba sin distinguir mayúsculas y el
    ingreso sí: "abc-1" pasaba teniendo ya "ABC-1".
    """
    if not seriales:
        return UnidadArticulo.objects.none()
    return (
        UnidadArticulo.objects
        .annotate(serial_mayus=models.functions.Upper('numero_serie'))
        .filter(serial_mayus__in=[serial.upper() for serial in seriales])
    )


# ---------------------------------------------------------------------------
# El resultado de una salida
#
# Una salida nace abierta y se resuelve después, cuando regresa el técnico.
# Estas dos funciones son las únicas que lo hacen: la pantalla, las pruebas y
# cualquier corrección futura pasan por acá, igual que las unidades pasan por
# ingresar_unidades y sacar_unidades.
# ---------------------------------------------------------------------------

def registrar_resultado(
    salida, *, usuario, vendidas=0, devueltas=0,
    unidades_vendidas=(), unidades_devueltas=(),
    fecha_regreso=None, devuelto_por='', observacion='',
):
    """
    Dice qué pasó con una línea de salida: cuántas se vendieron y cuántas
    regresaron. Lo que no sea ninguna de las dos sigue pendiente.

    Recibe el resultado **completo** de la línea, no solo lo que cambió. Así
    la misma pantalla sirve para registrarlo por partes —hoy regresa una, en
    dos semanas regresa el demo— y para corregir un dato mal puesto mientras
    la boleta siga abierta.

    Lo que regresa de más entra como una devolución nueva, con la fecha en que
    regresó. Si ahora regresaron menos que antes (se corrigió un error), se
    deshace empezando por la devolución más reciente.

    En una línea con seriales no se dan cantidades sino las unidades: hay que
    saber cuál aparato regresó, no solo cuántos.
    """
    with transaction.atomic():
        salida = (
            MovimientoVenta.objects.select_for_update()
            .select_related('articulo').get(pk=salida.pk)
        )
        if salida.tipo_documento != MovimientoVenta.TipoDocumento.SALIDA:
            raise ValidationError('Solo una línea de salida lleva resultado.')
        if salida.esta_cerrada:
            raise ValidationError(
                f'La boleta {salida.folio} ya está cerrada: sus resultados no se '
                'pueden cambiar.'
            )
        # Se bloquea el artículo desde el principio: la existencia se revisa
        # antes de tocar nada, y nadie más debe moverla mientras tanto.
        articulo = Articulo.objects.select_for_update().get(pk=salida.articulo_id)

        unidades = list(salida.unidades.all())
        con_serial = bool(unidades)
        if con_serial:
            de_la_linea = {unidad.pk for unidad in unidades}
            ids_vendidas = {unidad.pk for unidad in unidades_vendidas}
            ids_devueltas = {unidad.pk for unidad in unidades_devueltas}
            if not (ids_vendidas | ids_devueltas) <= de_la_linea:
                raise ValidationError('Alguna de esas unidades no salió en esta línea.')
            if ids_vendidas & ids_devueltas:
                raise ValidationError('Una unidad no puede quedar vendida y devuelta a la vez.')
            vendidas, devueltas = len(ids_vendidas), len(ids_devueltas)

        if vendidas < 0 or devueltas < 0:
            raise ValidationError('Las cantidades no pueden ser negativas.')
        if vendidas + devueltas > salida.cantidad:
            raise ValidationError(
                f'Salieron {salida.cantidad}: no pueden ser {vendidas} vendidas '
                f'y {devueltas} devueltas.'
            )

        devoluciones = list(
            salida.devoluciones.order_by('-fecha', '-id').prefetch_related('unidades')
        )
        if con_serial:
            ya_devueltas = {u.pk for d in devoluciones for u in d.unidades.all()}
            por_regresar = [u for u in unidades if u.pk in ids_devueltas - ya_devueltas]
            por_deshacer = [u for u in unidades if u.pk in ya_devueltas - ids_devueltas]
            cuantas_regresan = len(por_regresar)
        else:
            ya = sum(d.cantidad for d in devoluciones)
            cuantas_regresan = max(devueltas - ya, 0)
            cuantas_se_deshacen = max(ya - devueltas, 0)

        if cuantas_regresan:
            if fecha_regreso is None:
                raise ValidationError('Falta la fecha en que regresó.')
            if fecha_regreso < salida.fecha:
                raise ValidationError(
                    'El regreso no puede ser anterior a la salida '
                    f'({fechas.fecha_hora(salida.fecha)}).'
                )
            if not (devuelto_por or '').strip():
                raise ValidationError('Falta quién lo devolvió.')

        # Deshacer el regreso de algo que ya volvió a salir dejaría la
        # existencia en negativo. Se revisa antes de tocar nada: si se dejara
        # para el final, la base lo rechazaría a medio camino con un error
        # técnico en vez de este mensaje.
        if not con_serial and cuantas_se_deshacen:
            if articulo.calcular_stock_desde_movimientos() < cuantas_se_deshacen:
                raise ValidationError(
                    'No se puede deshacer ese regreso: lo que regresó de '
                    f'"{articulo.nombre_producto}" ya volvió a salir con otra boleta.'
                )

        # Primero se deshace lo que ya no regresó, después se registra lo que
        # sí: al revés, el stock subiría de más a mitad de camino.
        if con_serial:
            for unidad in por_deshacer:
                if not unidad.en_bodega:
                    salio_con = unidad.movimiento_salida
                    con_boleta = (
                        f' con la boleta {salio_con.folio}'
                        if salio_con is not None and salio_con.folio else ''
                    )
                    raise ValidationError(
                        f'El {unidad.numero_serie} ya volvió a salir{con_boleta}: '
                        'no se puede deshacer su regreso.'
                    )
            ids_por_deshacer = {unidad.pk for unidad in por_deshacer}
            for devolucion in devoluciones:
                quitar = [u.pk for u in devolucion.unidades.all() if u.pk in ids_por_deshacer]
                if not quitar:
                    continue
                MovimientoUnidad.objects.filter(
                    movimiento=devolucion, unidad_id__in=quitar,
                ).delete()
                quedan = devolucion.cantidad - len(quitar)
                if quedan:
                    devolucion.cantidad = quedan
                    devolucion.save()
                else:
                    devolucion.delete()
        else:
            for devolucion in devoluciones:
                if not cuantas_se_deshacen:
                    break
                if devolucion.cantidad <= cuantas_se_deshacen:
                    cuantas_se_deshacen -= devolucion.cantidad
                    devolucion.delete()
                else:
                    devolucion.cantidad -= cuantas_se_deshacen
                    cuantas_se_deshacen = 0
                    devolucion.save()

        if cuantas_regresan:
            devolucion = MovimientoVenta.objects.create(
                folio=salida.folio,
                tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
                tipo_transaccion=MovimientoVenta.TipoTransaccion.DEVOLUCION,
                articulo=salida.articulo,
                cantidad=cuantas_regresan,
                fecha=fecha_regreso,
                usuario=usuario,
                # Regresa al precio con que salió: es el mismo equipo.
                precio_unitario=salida.precio_unitario,
                cliente_nombre=salida.cliente_nombre,
                devolucion_de=salida,
                devuelto_por=devuelto_por.strip(),
                observacion=(observacion or '').strip(),
            )
            if con_serial:
                MovimientoUnidad.objects.bulk_create([
                    MovimientoUnidad(movimiento=devolucion, unidad=unidad)
                    for unidad in por_regresar
                ])

        # update() y no save(): lo vendido no mueve la existencia, así que no
        # hay nada que recalcular. La restricción de la base sigue cuidando
        # que no se vendan más de las que salieron.
        MovimientoVenta.objects.filter(pk=salida.pk).update(cantidad_vendida=vendidas)
        if con_serial:
            pasos = MovimientoUnidad.objects.filter(movimiento=salida)
            pasos.update(vendida=False)
            pasos.filter(unidad_id__in=ids_vendidas).update(vendida=True)

        articulo.recalcular_stock()


def cerrar_boleta(folio, usuario):
    """
    Cierra una boleta de salida: desde ahí ningún resultado se puede cambiar.

    Solo se cierra si a ninguna línea le falta resultado. El cierre se escribe
    en todas las líneas del folio, igual que el resto del encabezado.
    """
    with transaction.atomic():
        bloqueadas = list(
            MovimientoVenta.objects.select_for_update().filter(
                folio=folio, tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            )
        )
        if not bloqueadas:
            raise ValidationError(f'No hay ninguna boleta de salida con el número {folio}.')
        if any(linea.esta_cerrada for linea in bloqueadas):
            raise ValidationError(f'La boleta {folio} ya estaba cerrada.')

        lineas = MovimientoVenta.objects.filter(
            pk__in=[linea.pk for linea in bloqueadas],
        ).prefetch_related('devoluciones')
        sin_resultado = [linea for linea in lineas if linea.tiene_pendientes]
        if sin_resultado:
            raise ValidationError(
                f'Todavía hay {len(sin_resultado)} línea(s) sin resultado. '
                'La boleta se cierra cuando ya se sabe qué pasó con todo.'
            )

        ahora = timezone.now()
        MovimientoVenta.objects.filter(
            pk__in=[linea.pk for linea in bloqueadas],
        ).update(fecha_cierre=ahora, cerrada_por=usuario)
        return ahora
