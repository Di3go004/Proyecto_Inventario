"""
Un documento del talonario, juntando sus dos tablas.

El FO-SE-013 es un solo formato para las tres bodegas, así que una boleta
puede traer productos de venta (MovimientoVenta) y herramienta
(MovimientoActivo) en la misma hoja. Acá se recuperan las líneas de las dos
tablas bajo el mismo folio y se presentan iguales, para que la pantalla del
documento y el PDF no tengan que saber de cuál salió cada una.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db.models import Q

from tecnica.models import MovimientoActivo

from .models import MovimientoVenta


@dataclass
class LineaDocumento:
    """Una línea de la boleta, venga de la bodega que venga."""

    movimiento: object
    producto: object
    es_tecnica: bool
    cantidad: int
    proveedor: Optional[object]
    no_factura: str
    cliente_nombre: str
    esta_afuera: bool
    fecha_devolucion: object
    orden: tuple

    @property
    def pk(self):
        return self.movimiento.pk

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad

    @property
    def proveedor_efectivo(self):
        """
        El del movimiento manda sobre el del catálogo: una compra puntual a
        otro proveedor no debe reescribir el artículo.
        """
        return self.proveedor or self.producto.proveedor


def _de_venta(movimiento):
    return LineaDocumento(
        movimiento=movimiento,
        producto=movimiento.articulo,
        es_tecnica=False,
        cantidad=movimiento.cantidad,
        proveedor=movimiento.proveedor,
        no_factura=movimiento.no_factura,
        cliente_nombre=movimiento.cliente_nombre,
        esta_afuera=movimiento.esta_afuera,
        fecha_devolucion=movimiento.fecha_devolucion,
        # Las de venta van primero dentro de la misma fecha, para que la
        # boleta salga siempre en el mismo orden y no cambie entre impresiones.
        orden=(movimiento.fecha, 0, movimiento.pk),
    )


def _de_tecnica(movimiento):
    return LineaDocumento(
        movimiento=movimiento,
        producto=movimiento.activo,
        es_tecnica=True,
        cantidad=movimiento.cantidad,
        proveedor=movimiento.proveedor,
        no_factura=movimiento.no_factura,
        # Bodega Técnica no vende: estas columnas del FO-SE-012 no aplican.
        cliente_nombre='',
        esta_afuera=False,
        fecha_devolucion=None,
        orden=(movimiento.fecha, 1, movimiento.pk),
    )


def lineas_del_documento(folio):
    """
    Todas las líneas de ese folio, de las dos bodegas, en orden estable.

    Devuelve [] si el folio no existe — cada llamador decide si eso es un
    404, un mensaje o una lista vacía.
    """
    lineas = [
        _de_venta(movimiento)
        for movimiento in MovimientoVenta.objects
        .filter(folio=folio)
        .select_related('articulo', 'articulo__bodega', 'articulo__proveedor', 'usuario', 'proveedor')
    ]
    lineas += [
        _de_tecnica(movimiento)
        for movimiento in MovimientoActivo.objects
        .filter(folio=folio)
        .select_related('activo', 'activo__bodega', 'activo__proveedor', 'usuario', 'proveedor')
    ]
    lineas.sort(key=lambda linea: linea.orden)
    return lineas


def es_ingreso(lineas):
    """
    Si el documento es un ingreso (FO-SE-013) o una salida (FO-SE-012).

    No se puede preguntar `cabecera.tipo_documento`: un movimiento de Bodega
    Técnica no tiene ese campo, porque a esa bodega solo entran cosas. Al
    consultarlo en la plantilla salía vacío y el documento se pintaba entero
    como salida —encabezado, código de formato y columnas— aunque fuera un
    ingreso.
    """
    if not lineas:
        return True
    cabecera = lineas[0].movimiento
    return getattr(cabecera, 'tipo_documento', 'ingreso') == 'ingreso'


def totales(lineas):
    """Unidades y quetzales del documento completo."""
    return (
        sum(linea.cantidad for linea in lineas),
        sum((linea.subtotal for linea in lineas), Decimal('0')),
    )


# ---------------------------------------------------------------------------
# Historial de entradas y salidas
#
# La pantalla muestra las tres bodegas juntas, que es como se lleva en papel:
# un solo talonario FO-SE-013 y una sola numeración. Antes solo listaba
# MovimientoVenta, así que un ingreso a Bodega Técnica se guardaba bien pero
# no aparecía en ningún lado.
# ---------------------------------------------------------------------------

@dataclass
class FilaHistorial:
    """Un movimiento de cualquier bodega, presentado igual."""

    movimiento: object
    producto: object
    es_tecnica: bool
    etiqueta: str          # Ingreso / Salida / Baja / Ajuste
    tono: str              # clase del chip
    signo: int             # +1 o -1, para pintar la cantidad
    transaccion: str
    esta_afuera: bool
    fecha_devolucion: object

    @property
    def pk(self):
        return self.movimiento.pk

    @property
    def fecha(self):
        return self.movimiento.fecha

    @property
    def folio(self):
        return self.movimiento.folio

    @property
    def cantidad(self):
        return self.movimiento.cantidad

    @property
    def solicitado_por(self):
        return self.movimiento.solicitado_por


ETIQUETAS_TECNICA = {
    MovimientoActivo.Tipo.INGRESO: ('Ingreso', 'chip-good', 1),
    MovimientoActivo.Tipo.BAJA: ('Baja', 'chip-critical', -1),
    MovimientoActivo.Tipo.AJUSTE: ('Ajuste', 'chip-neutral', 1),
}


def _fila_de_venta(movimiento):
    es_ingreso = movimiento.tipo_documento == MovimientoVenta.TipoDocumento.INGRESO
    return FilaHistorial(
        movimiento=movimiento,
        producto=movimiento.articulo,
        es_tecnica=False,
        etiqueta='Ingreso' if es_ingreso else 'Salida',
        tono='chip-good' if es_ingreso else 'chip-critical',
        signo=1 if es_ingreso else -1,
        transaccion=movimiento.get_tipo_transaccion_display(),
        esta_afuera=movimiento.esta_afuera,
        fecha_devolucion=movimiento.fecha_devolucion,
    )


def _fila_de_tecnica(movimiento):
    etiqueta, tono, signo = ETIQUETAS_TECNICA[movimiento.tipo]
    return FilaHistorial(
        movimiento=movimiento,
        producto=movimiento.activo,
        es_tecnica=True,
        etiqueta=etiqueta,
        tono=tono,
        signo=signo,
        # En Bodega Técnica el motivo ocupa el lugar del tipo de transacción:
        # es lo que explica por qué se movió.
        transaccion=movimiento.get_motivo_display() if movimiento.motivo else '',
        esta_afuera=False,
        fecha_devolucion=None,
    )


def filas_de_historial(q='', tipo='', transaccion='', bodega_id='', desde=None, hasta=None, afuera=''):
    """
    El historial de las tres bodegas, ya filtrado y ordenado por fecha.

    Se resuelve en Python y no con una consulta sola porque son dos tablas
    distintas; a la escala de esta bodega (unos miles de movimientos al año)
    el costo es despreciable frente a tener el historial partido en dos
    pantallas.
    """
    ventas = (
        MovimientoVenta.objects
        .select_related('articulo', 'articulo__bodega', 'usuario', 'proveedor')
    )
    tecnica = (
        MovimientoActivo.objects
        .select_related('activo', 'activo__bodega', 'usuario', 'proveedor')
    )

    if q:
        ventas = ventas.filter(
            Q(folio__icontains=q)
            | Q(articulo__codigo_interno__icontains=q)
            | Q(articulo__nombre_producto__icontains=q)
            | Q(cliente_nombre__icontains=q)
            | Q(solicitado_por__icontains=q)
            | Q(no_factura__icontains=q)
        )
        tecnica = tecnica.filter(
            Q(folio__icontains=q)
            | Q(activo__codigo_interno__icontains=q)
            | Q(activo__nombre_producto__icontains=q)
            | Q(solicitado_por__icontains=q)
            | Q(no_factura__icontains=q)
        )

    if tipo == MovimientoVenta.TipoDocumento.INGRESO:
        ventas = ventas.filter(tipo_documento=tipo)
        tecnica = tecnica.filter(tipo=MovimientoActivo.Tipo.INGRESO)
    elif tipo == MovimientoVenta.TipoDocumento.SALIDA:
        ventas = ventas.filter(tipo_documento=tipo)
        tecnica = tecnica.none()   # a Bodega Técnica solo entran cosas
    elif tipo == 'baja':
        ventas = ventas.none()
        tecnica = tecnica.filter(tipo=MovimientoActivo.Tipo.BAJA)

    if transaccion:
        # El tipo de transacción (venta, préstamo, repuestos) es de la boleta
        # de venta; en Bodega Técnica no existe.
        ventas = ventas.filter(tipo_transaccion=transaccion)
        tecnica = tecnica.none()

    if bodega_id:
        ventas = ventas.filter(articulo__bodega_id=bodega_id)
        tecnica = tecnica.filter(activo__bodega_id=bodega_id)

    if desde:
        ventas = ventas.filter(fecha__date__gte=desde)
        tecnica = tecnica.filter(fecha__date__gte=desde)
    if hasta:
        ventas = ventas.filter(fecha__date__lte=hasta)
        tecnica = tecnica.filter(fecha__date__lte=hasta)

    if afuera == 'si':
        # Préstamos/demo sin devolución (RF-06): solo los hay en venta. Los de
        # Bodega Técnica se ven en su propia pantalla de préstamos.
        ventas = ventas.filter(
            tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
            fecha_devolucion__isnull=True,
        )
        tecnica = tecnica.none()

    filas = [_fila_de_venta(m) for m in ventas] + [_fila_de_tecnica(m) for m in tecnica]
    filas.sort(key=lambda f: (f.fecha, f.pk), reverse=True)
    return filas
