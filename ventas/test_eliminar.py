"""
Pruebas de qué se puede borrar del catálogo y qué no.

El caso que originó esto: después de importar el Excel, la carga masiva le
deja a cada artículo un movimiento de "ajuste / saldo inicial", y eso hacía
que los 216 quedaran imposibles de borrar para siempre — incluso los que se
hubieran importado por error. Encima el aviso daba a entender que
desactivarlos servía de algo, y no servía.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BaseEliminar(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.admin = Usuario.objects.create_user(
            username='admin_del', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def crear_articulo(self, nombre='Báscula', modelo='BP-1'):
        return Articulo.objects.create(
            nombre_producto=nombre, modelo=modelo, capacidad='1kg', bodega=self.bodega,
        )

    def mover(self, articulo, tipo_transaccion, cantidad=5):
        return MovimientoVenta.objects.create(
            articulo=articulo, cantidad=cantidad,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=tipo_transaccion,
            fecha=timezone.now(), usuario=self.admin,
        )

    def borrar(self, articulo):
        return self.client.post(reverse('articulo_eliminar', args=[articulo.pk]), follow=True)


class SePuedeBorrarTests(BaseEliminar):
    def test_uno_sin_ningun_movimiento(self):
        articulo = self.crear_articulo()

        self.borrar(articulo)

        self.assertFalse(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_uno_que_solo_trae_el_saldo_inicial_de_la_carga_masiva(self):
        """
        Regresión: el saldo inicial no es historial, es el conteo con el que
        arrancó. Si es lo único que tiene, no debe bloquear el borrado.
        """
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL)

        self.borrar(articulo)

        self.assertFalse(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_el_saldo_inicial_se_borra_con_el(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL)

        self.borrar(articulo)

        self.assertEqual(MovimientoVenta.objects.count(), 0, 'no debe quedar el ajuste huérfano')

    def test_la_pantalla_avisa_que_el_saldo_inicial_se_va_con_el(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL)

        pantalla = self.client.get(reverse('articulo_eliminar', args=[articulo.pk]))

        self.assertContains(pantalla, 'saldo inicial')
        self.assertContains(pantalla, 'Sí, eliminar')


class NoSePuedeBorrarTests(BaseEliminar):
    def con_movimiento_real(self):
        articulo = self.crear_articulo()
        self.mover(articulo, MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL, cantidad=10)
        self.mover(articulo, MovimientoVenta.TipoTransaccion.VENTA, cantidad=1)
        return articulo

    def test_uno_con_movimientos_registrados_por_alguien(self):
        articulo = self.con_movimiento_real()

        self.borrar(articulo)

        self.assertTrue(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_no_se_pierde_ningun_movimiento_en_el_intento(self):
        articulo = self.con_movimiento_real()
        antes = MovimientoVenta.objects.count()

        self.borrar(articulo)

        self.assertEqual(MovimientoVenta.objects.count(), antes)

    def test_desactivarlo_no_lo_habilita(self):
        """
        Era justo lo que el aviso viejo daba a entender: "desmárcalo como
        activo" sonaba a que después sí se podría borrar. Nunca fue así.
        """
        articulo = self.con_movimiento_real()
        Articulo.objects.filter(pk=articulo.pk).update(activo=False)

        self.borrar(articulo)

        self.assertTrue(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_el_aviso_dice_que_desactivar_tampoco_sirve(self):
        articulo = self.con_movimiento_real()

        respuesta = self.borrar(articulo)

        self.assertContains(respuesta, 'Desactivarlo tampoco')

    def test_la_pantalla_explica_cuantos_movimientos_lo_bloquean(self):
        articulo = self.con_movimiento_real()

        pantalla = self.client.get(reverse('articulo_eliminar', args=[articulo.pk]))

        self.assertContains(pantalla, '1 movimiento(s)')
        self.assertNotContains(pantalla, 'Sí, eliminar')
        self.assertContains(pantalla, 'Ir a Editar')


class SoloElAdministradorBorraTests(BaseEliminar):
    def test_el_operador_no_puede(self):
        operador = Usuario.objects.create_user(
            username='op_del', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        articulo = self.crear_articulo()
        self.client.force_login(operador)

        respuesta = self.client.post(reverse('articulo_eliminar', args=[articulo.pk]))

        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(Articulo.objects.filter(pk=articulo.pk).exists())
