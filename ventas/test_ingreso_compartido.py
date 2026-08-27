"""
El FO-SE-013 es un solo formato para las tres bodegas.

La empresa usa un único talonario de ingreso para Bodega 1, Bodega 2 y
Bodega Técnica, así que la misma pantalla ofrece los dos catálogos, el
correlativo es una sola serie, y una boleta puede traer productos de las dos
en la misma hoja.

La salida (FO-SE-012) no: a Bodega Técnica solo entran cosas — lo que baja su
existencia es dar de baja, que se registra aparte y sin boleta.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas import documentos
from ventas.models import Articulo, MovimientoVenta


class BaseIngreso(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega1 = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.btec = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.operador = Usuario.objects.create_user(
            username='op_ing', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.bascula = Articulo.objects.create(
            nombre_producto='Báscula de plataforma', modelo='BP-300',
            bodega=cls.bodega1, precio=1500,
        )
        cls.taladro = Activo.objects.create(
            codigo_interno='SE-TEC-001', nombre_producto='Taladro percutor',
            bodega=cls.btec, precio=900,
        )

    def setUp(self):
        self.client.force_login(self.operador)

    def ingresar(self, lineas, **extra):
        """`lineas`: [(identificador, cantidad), ...]"""
        datos = {
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'tipo_transaccion': MovimientoVenta.TipoTransaccion.VENTA,
            'solicitado_por': 'Marisol Pérez',
            'no_factura': '', 'no_boleta': '', 'observacion': '',
            'linea_articulo': [ident for ident, _c in lineas],
            'linea_cantidad': [str(c) for _i, c in lineas],
            'linea_texto': ['' for _l in lineas],
        }
        datos.update(extra)
        return self.client.post(reverse('movimiento_ingreso'), datos)


class BuscadorCompartidoTests(BaseIngreso):
    def test_el_ingreso_ofrece_tambien_la_bodega_tecnica(self):
        respuesta = self.client.get(
            reverse('api_buscar_articulos'), {'q': 'taladro', 'incluir': 'tecnica'},
        ).json()

        self.assertEqual(len(respuesta['resultados']), 1)
        self.assertEqual(respuesta['resultados'][0]['id'], f'act-{self.taladro.pk}')

    def test_sin_pedirlo_no_aparecen_los_activos(self):
        """La salida (FO-SE-012) no debe ofrecer herramienta."""
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'taladro'}).json()

        self.assertEqual(respuesta['resultados'], [])

    def test_el_id_dice_de_que_catalogo_salio(self):
        """
        Sin prefijo el id sería ambiguo: el 12 de Bodega 1 y 2 no es el 12 de
        Bodega Técnica, y la misma pantalla ofrece los dos.
        """
        de_venta = self.client.get(
            reverse('api_buscar_articulos'), {'q': 'plataforma', 'incluir': 'tecnica'},
        ).json()
        de_tecnica = self.client.get(
            reverse('api_buscar_articulos'), {'q': 'taladro', 'incluir': 'tecnica'},
        ).json()

        self.assertTrue(de_venta['resultados'][0]['id'].startswith('art-'))
        self.assertTrue(de_tecnica['resultados'][0]['id'].startswith('act-'))


class IngresoATecnicaTests(BaseIngreso):
    def test_un_ingreso_a_tecnica_sube_su_existencia(self):
        self.ingresar([(f'act-{self.taladro.pk}', 3)])

        self.taladro.refresh_from_db()
        self.assertEqual(self.taladro.existencia, 3)
        self.assertEqual(MovimientoActivo.objects.count(), 1)

    def test_el_movimiento_guarda_los_datos_de_la_boleta(self):
        self.ingresar([(f'act-{self.taladro.pk}', 1)], no_factura='F-991', solicitado_por='Byron')

        movimiento = MovimientoActivo.objects.get()
        self.assertEqual(movimiento.tipo, MovimientoActivo.Tipo.INGRESO)
        self.assertEqual(movimiento.no_factura, 'F-991')
        self.assertEqual(movimiento.solicitado_por, 'Byron')
        self.assertTrue(movimiento.folio.startswith('ING-'))

    def test_una_boleta_puede_traer_las_dos_bodegas(self):
        """Un solo talonario: la boleta real puede mezclar."""
        self.ingresar([(f'art-{self.bascula.pk}', 2), (f'act-{self.taladro.pk}', 5)])

        self.bascula.refresh_from_db()
        self.taladro.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 2)
        self.assertEqual(self.taladro.existencia, 5)

        folio = MovimientoVenta.objects.get().folio
        self.assertEqual(MovimientoActivo.objects.get().folio, folio, 'mismo folio')

    def test_la_pantalla_del_documento_junta_las_dos_bodegas(self):
        self.ingresar([(f'art-{self.bascula.pk}', 2), (f'act-{self.taladro.pk}', 5)])
        folio = MovimientoVenta.objects.get().folio

        respuesta = self.client.get(reverse('documento_detalle', args=[folio]))

        self.assertEqual(len(respuesta.context['lineas']), 2)
        self.assertContains(respuesta, 'Báscula de plataforma')
        self.assertContains(respuesta, 'Taladro percutor')

    def test_la_boleta_en_pdf_incluye_las_dos(self):
        self.ingresar([(f'art-{self.bascula.pk}', 2), (f'act-{self.taladro.pk}', 5)])
        folio = MovimientoVenta.objects.get().folio

        respuesta = self.client.get(reverse('documento_pdf', args=[folio]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b'%PDF'))
        self.assertEqual(len(documentos.lineas_del_documento(folio)), 2)

    def test_un_ingreso_solo_de_tecnica_tambien_saca_su_boleta(self):
        """
        El movimiento de Bodega Técnica no tiene tipo de documento ni tipo de
        transacción: la boleta tiene que armarse igual, con esas casillas sin
        marcar como cuando no aplican en el papel.
        """
        self.ingresar([(f'act-{self.taladro.pk}', 4)])
        folio = MovimientoActivo.objects.get().folio

        respuesta = self.client.get(reverse('documento_pdf', args=[folio]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b'%PDF'))


class FolioCompartidoTests(BaseIngreso):
    """
    Un solo talonario, una sola serie. Si cada bodega contara por su lado,
    dos boletas distintas saldrían con el mismo número.
    """

    def test_el_correlativo_cuenta_las_dos_tablas(self):
        self.ingresar([(f'art-{self.bascula.pk}', 1)])       # ING-00001
        self.ingresar([(f'act-{self.taladro.pk}', 1)])       # ING-00002

        self.assertEqual(MovimientoVenta.objects.get().folio, 'ING-00001')
        self.assertEqual(MovimientoActivo.objects.get().folio, 'ING-00002')

    def test_despues_de_uno_tecnico_el_siguiente_de_venta_no_lo_repite(self):
        self.ingresar([(f'act-{self.taladro.pk}', 1)])       # ING-00001
        self.ingresar([(f'art-{self.bascula.pk}', 1)])       # ING-00002

        self.assertEqual(MovimientoActivo.objects.get().folio, 'ING-00001')
        self.assertEqual(MovimientoVenta.objects.get().folio, 'ING-00002')

    def test_la_salida_lleva_su_propia_serie(self):
        self.ingresar([(f'act-{self.taladro.pk}', 1)])

        siguiente = MovimientoVenta.siguiente_folio(MovimientoVenta.TipoDocumento.SALIDA)

        self.assertEqual(siguiente, 'SAL-00001', 'el ingreso técnico no corre la de salida')
