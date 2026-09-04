"""
El comando que borra el historial de Bodega Técnica y deja todo en 0.

El formulario de alta dejaba escribir una cantidad inicial, y eso generaba un
movimiento de tipo "Ajuste" sin folio y sin boleta detrás. Así entraron 219
cantidades que nunca debieron entrar por ahí. El alta ya se arregló; esto
limpia lo que quedó, para arrancar el historial de verdad desde cero.

Lo delicado es que borra sin vuelta atrás, así que lo que más se prueba acá es
que **no** borre cuando no debe.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from usuarios.models import Usuario


class BaseLimpieza(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.usuario = Usuario.objects.create_user(
            username='admin_limpieza', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def activo_con_existencia(self, codigo, cantidad):
        activo = Activo.objects.create(
            codigo_interno=codigo, nombre_producto=f'Cosa {codigo}',
            bodega=self.bodega, precio=10,
        )
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.AJUSTE, activo=activo,
            cantidad=cantidad, usuario=self.usuario,
            observacion='Saldo inicial al crear el activo.',
        )
        activo.refresh_from_db()
        return activo

    def correr(self, *args):
        salida = StringIO()
        call_command('limpiar_historial_tecnica', *args, stdout=salida, stderr=salida)
        return salida.getvalue()


class SinConfirmarNoTocaNadaTests(BaseLimpieza):
    """Lo más importante: por defecto no borra."""

    def test_sin_la_bandera_no_borra_nada(self):
        activo = self.activo_con_existencia('SE-T1', 43)

        self.correr()

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 43)
        self.assertEqual(MovimientoActivo.objects.count(), 1)

    def test_avisa_que_hay_que_respaldar_antes(self):
        self.activo_con_existencia('SE-T1', 43)

        salida = self.correr()

        self.assertIn('respaldo', salida)
        self.assertIn('--si-estoy-seguro', salida)

    def test_dice_cuanto_se_borraria(self):
        self.activo_con_existencia('SE-T1', 43)
        self.activo_con_existencia('SE-T2', 7)

        salida = self.correr()

        self.assertIn('2', salida)


class ConPrestamosAbiertosSeDetieneTests(BaseLimpieza):
    """
    Dejar la existencia en 0 con herramienta afuera diría que la bodega no
    tiene nada de algo que sí salió y tiene que volver.
    """

    def test_no_borra_si_hay_algo_sin_devolver(self):
        activo = self.activo_con_existencia('SE-T1', 5)
        PrestamoActivo.objects.create(
            activo=activo, cantidad=2, solicitante='Ivan Leiva',
            usuario=self.usuario, estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        salida = self.correr('--si-estoy-seguro')

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 5, 'no debió borrar nada')
        self.assertEqual(MovimientoActivo.objects.count(), 1)
        self.assertIn('sin devolver', salida)

    def test_si_ya_regresó_todo_sí_borra(self):
        activo = self.activo_con_existencia('SE-T1', 5)
        PrestamoActivo.objects.create(
            activo=activo, cantidad=2, solicitante='Ivan Leiva',
            usuario=self.usuario, estado_al_salir=Activo.Estado.BUEN_ESTADO,
            fecha_regreso=timezone.now(), estado_al_regresar=Activo.Estado.BUEN_ESTADO,
        )

        self.correr('--si-estoy-seguro')

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 0)


class CuandoSeConfirmaTests(BaseLimpieza):
    def test_borra_el_historial(self):
        self.activo_con_existencia('SE-T1', 43)
        self.activo_con_existencia('SE-T2', 7)

        self.correr('--si-estoy-seguro')

        self.assertEqual(MovimientoActivo.objects.count(), 0)

    def test_deja_todas_las_existencias_en_cero(self):
        """No se escriben a mano: la señal post_delete las recalcula sola."""
        self.activo_con_existencia('SE-T1', 43)
        self.activo_con_existencia('SE-T2', 7)

        self.correr('--si-estoy-seguro')

        self.assertEqual(Activo.objects.filter(existencia__gt=0).count(), 0)

    def test_NO_borra_los_activos(self):
        """
        Es la diferencia con limpiar_catalogo: el catálogo se queda entero,
        con sus códigos, precios y marcas. Solo se va el historial.
        """
        self.activo_con_existencia('SE-T1', 43)
        self.activo_con_existencia('SE-T2', 7)

        self.correr('--si-estoy-seguro')

        self.assertEqual(Activo.objects.count(), 2)
        self.assertEqual(Activo.objects.get(codigo_interno='SE-T1').precio, 10)

    def test_no_toca_Bodega_1_y_2(self):
        from ventas.models import Articulo, MovimientoVenta
        venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=venta, precio=100,
        )
        MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.REPUESTOS,
            cantidad=9, usuario=self.usuario,
        )
        self.activo_con_existencia('SE-T1', 43)

        self.correr('--si-estoy-seguro')

        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 9)
        self.assertEqual(MovimientoVenta.objects.count(), 1)

    def test_si_ya_estaba_vacío_lo_dice_y_no_falla(self):
        salida = self.correr('--si-estoy-seguro')

        self.assertIn('vacío', salida)
