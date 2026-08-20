"""
Pruebas de la lógica de stock de Bodega 1 y 2 (RF-06, RF-08, RF-11).

El stock es el dato más delicado del sistema: si miente, todo lo demás
(alertas, valorización, reportes) miente con él. Estas pruebas fijan el
comportamiento para que ningún cambio futuro lo rompa en silencio.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BaseVentas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.usuario = Usuario.objects.create_user(
            username='operador', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )

    def crear_articulo(self, **extra):
        datos = dict(
            nombre_producto='Báscula de prueba', modelo='BP-100',
            capacidad='300kg', bodega=self.bodega,
        )
        datos.update(extra)
        return Articulo.objects.create(**datos)

    def mover(self, articulo, tipo_documento, cantidad,
              tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA, **extra):
        return MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=tipo_documento,
            tipo_transaccion=tipo_transaccion, cantidad=cantidad,
            usuario=self.usuario, **extra,
        )


class StockTests(BaseVentas):
    def test_ingreso_suma_al_stock(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)
        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 10)

    def test_salida_resta_del_stock(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)
        self.mover(articulo, MovimientoVenta.TipoDocumento.SALIDA, 4)
        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 6)

    def test_editar_la_cantidad_de_un_movimiento_recalcula_el_stock(self):
        """Regresión: antes el stock solo se ajustaba al crear, así que editar
        un movimiento desde el panel de administración lo dejaba mintiendo."""
        articulo = self.crear_articulo()
        movimiento = self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)

        movimiento.cantidad = 3
        movimiento.save()

        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 3)

    def test_borrar_un_movimiento_recalcula_el_stock(self):
        """Regresión: borrar un movimiento no revertía su efecto en el stock."""
        articulo = self.crear_articulo()
        movimiento = self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)

        movimiento.delete()

        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 0)

    def test_salida_mayor_al_stock_se_rechaza_con_mensaje_claro(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 5)

        with self.assertRaises(ValidationError) as caso:
            self.mover(articulo, MovimientoVenta.TipoDocumento.SALIDA, 99)

        self.assertIn('No hay suficiente stock', str(caso.exception))
        articulo.refresh_from_db()
        self.assertEqual(
            articulo.stock_actual, 5,
            'el stock no debe cambiar si la salida se rechazo',
        )
        self.assertEqual(
            MovimientoVenta.objects.filter(articulo=articulo, cantidad=99).count(), 0,
            'el movimiento rechazado no debe quedar guardado',
        )

    def test_el_stock_se_deriva_de_los_movimientos_aunque_lo_toquen_a_mano(self):
        """Si alguien fuerza un valor incorrecto, recalcular_stock lo corrige."""
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 7)

        Articulo.objects.filter(pk=articulo.pk).update(stock_actual=999)
        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 999)

        articulo.recalcular_stock()
        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 7)


class PrestamoDemoTests(BaseVentas):
    """RF-06: una salida de préstamo/demo espera regreso; al cerrarla el
    equipo vuelve físicamente a la bodega y el stock se restaura."""

    def test_prestamo_descuenta_mientras_esta_afuera(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)
        self.mover(
            articulo, MovimientoVenta.TipoDocumento.SALIDA, 2,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )
        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 8)

    def test_al_registrar_la_devolucion_el_stock_vuelve(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoDocumento.INGRESO, 10)
        prestamo = self.mover(
            articulo, MovimientoVenta.TipoDocumento.SALIDA, 2,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )

        prestamo.fecha_devolucion = timezone.now()
        prestamo.devuelto_por = 'Ivan Leiva'
        prestamo.save()

        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 10)

    def test_solo_prestamo_demo_admite_datos_de_devolucion(self):
        articulo = self.crear_articulo()
        movimiento = MovimientoVenta(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA, cantidad=1,
            usuario=self.usuario, fecha_devolucion=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            movimiento.clean()


class NivelAlertaTests(BaseVentas):
    """RF-11: umbrales pedidos por la empresa (óptimo 20 / alerta 5 / crítico 2)."""

    def nivel_con_stock(self, stock):
        articulo = self.crear_articulo()
        Articulo.objects.filter(pk=articulo.pk).update(stock_actual=stock)
        articulo.refresh_from_db()
        return articulo.nivel_alerta

    def test_umbrales(self):
        self.assertEqual(self.nivel_con_stock(0), 'critico')
        self.assertEqual(self.nivel_con_stock(2), 'critico')
        self.assertEqual(self.nivel_con_stock(3), 'alerta')
        self.assertEqual(self.nivel_con_stock(5), 'alerta')
        self.assertEqual(self.nivel_con_stock(10), 'normal')
        self.assertEqual(self.nivel_con_stock(20), 'optimo')
        self.assertEqual(self.nivel_con_stock(50), 'optimo')


class CodigoInternoTests(BaseVentas):
    """Estándar pedido por la empresa: SE-MODELO-capacidad, respetando la
    notación del Sistema Internacional de Unidades en la capacidad."""

    def test_se_genera_solo_al_dejarlo_vacio(self):
        articulo = self.crear_articulo(modelo='F4985205', capacidad='60kg')
        self.assertEqual(articulo.codigo_interno, 'SE-F4985205-60kg')

    def test_respeta_mayusculas_de_las_unidades_si(self):
        # Voltios y amperios van en mayuscula; forzar minusculas romperia la notacion.
        articulo = self.crear_articulo(modelo='ZF120A-0421000', capacidad='4.2V/10A')
        self.assertEqual(articulo.codigo_interno, 'SE-ZF120A-0421000-4.2V-10A')

    def test_el_administrador_puede_escribir_uno_propio(self):
        articulo = self.crear_articulo(codigo_interno='SE-CUSTOM-001')
        self.assertEqual(articulo.codigo_interno, 'SE-CUSTOM-001')

    def test_dos_productos_con_igual_modelo_y_capacidad_no_chocan(self):
        primero = self.crear_articulo(modelo='BI 12T', capacidad='12t')
        segundo = self.crear_articulo(modelo='BI 12T', capacidad='12t')
        self.assertEqual(primero.codigo_interno, 'SE-BI-12T-12t')
        self.assertEqual(segundo.codigo_interno, 'SE-BI-12T-12t-2')
