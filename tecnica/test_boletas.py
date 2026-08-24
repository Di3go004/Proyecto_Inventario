"""
Pruebas de la hoja FO-SE-066 en PDF (RF-10).

Lo que más importa aquí es que lo impreso coincida con lo que se está viendo
en pantalla: si los filtros de la lista y los del PDF se separaran, alguien
archivaría una hoja que no corresponde a lo que creía estar imprimiendo.
"""

from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica import boletas, views
from tecnica.models import Activo, PrestamoActivo
from usuarios.models import Usuario


class BaseHoja(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.operador = Usuario.objects.create_user(
            username='op_hoja', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='cont_hoja', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.taladro = Activo.objects.create(
            codigo_interno='SE-TEC-001', nombre_producto='Taladro percutor', bodega=cls.bodega,
        )
        cls.rotomartillo = Activo.objects.create(
            codigo_interno='SE-TEC-002', nombre_producto='Rotomartillo', bodega=cls.bodega,
        )

    def prestar(self, activo, solicitante='Ivan Leiva', devuelto_en=None):
        prestamo = PrestamoActivo.objects.create(
            activo=activo, solicitante=solicitante, entregado_por='Bodega',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.operador,
        )
        if devuelto_en:
            prestamo.fecha_regreso = timezone.now()
            prestamo.recibido_por = 'Bodega'
            prestamo.estado_al_regresar = devuelto_en
            prestamo.save()
        return prestamo


class GeneracionTests(BaseHoja):
    def test_la_hoja_en_blanco_tambien_se_genera(self):
        """Imprimirla vacía para llenarla a mano es un uso válido del formato."""
        contenido = boletas.hoja_prestamos([])

        self.assertTrue(contenido.startswith(b'%PDF'))
        self.assertGreater(len(contenido), 1000)

    def test_genera_con_prestamos(self):
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo, devuelto_en=Activo.Estado.BUEN_ESTADO)

        contenido = boletas.hoja_prestamos(PrestamoActivo.objects.all())

        self.assertTrue(contenido.startswith(b'%PDF'))

    def test_anota_el_estado_solo_si_la_herramienta_volvio_distinta(self):
        igual = self.prestar(self.taladro, devuelto_en=Activo.Estado.BUEN_ESTADO)
        distinta = self.prestar(self.rotomartillo, devuelto_en=Activo.Estado.MAL_ESTADO)

        self.assertNotIn('Regresó en', boletas._herramienta(igual))
        self.assertIn('Regresó en: Mal estado', boletas._herramienta(distinta))

    def test_un_prestamo_abierto_no_anota_estado_de_regreso(self):
        abierto = self.prestar(self.taladro)
        self.assertNotIn('Regresó en', boletas._herramienta(abierto))


class FiltrosCompartidosTests(BaseHoja):
    """
    El PDF y la pantalla tienen que filtrar igual: comparten
    _prestamos_filtrados justamente para que no se separen.
    """

    def filtrar(self, **parametros):
        peticion = RequestFactory().get('/movimientos/tecnica/', parametros)
        prestamos, _valores = views._prestamos_filtrados(peticion)
        return list(prestamos)

    def test_por_defecto_solo_los_que_estan_afuera(self):
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo, devuelto_en=Activo.Estado.BUEN_ESTADO)

        self.assertEqual(self.filtrar(), [PrestamoActivo.objects.get(activo=self.taladro)])

    def test_todos_incluye_los_devueltos(self):
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo, devuelto_en=Activo.Estado.BUEN_ESTADO)

        self.assertEqual(len(self.filtrar(estado='todos')), 2)

    def test_busca_por_persona(self):
        self.prestar(self.taladro, solicitante='Marisol Pérez')
        self.prestar(self.rotomartillo, solicitante='Otra persona')

        encontrados = self.filtrar(q='Marisol')
        self.assertEqual(len(encontrados), 1)
        self.assertEqual(encontrados[0].solicitante, 'Marisol Pérez')


class VistaDeLaHojaTests(BaseHoja):
    def setUp(self):
        self.client.login(username='op_hoja', password='clave-de-prueba')
        self.url = reverse('prestamos_pdf')

    def test_responde_un_pdf(self):
        self.prestar(self.taladro)
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertIn('inline', respuesta['Content-Disposition'])
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_sin_prestamos_devuelve_la_hoja_en_blanco(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_avisa_en_vez_de_imprimir_un_tomo_entero(self):
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo)

        with patch.object(views, 'MAX_PRESTAMOS_PDF', 1):
            respuesta = self.client.get(self.url, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Acota el rango de fechas')

    def test_conserva_los_filtros_al_redirigir_por_exceso(self):
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo)

        with patch.object(views, 'MAX_PRESTAMOS_PDF', 1):
            respuesta = self.client.get(self.url, {'estado': 'todos'})

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('estado=todos', respuesta['Location'])

    def test_el_pdf_recibe_exactamente_lo_que_muestra_la_pantalla(self):
        """
        No basta con que el enlace lleve los filtros: hay que comprobar que la
        vista los aplica antes de armar el PDF. Si se imprimiera todo el
        historial cuando en pantalla hay un filtro puesto, alguien archivaría
        una hoja que no corresponde a lo que creyó imprimir.
        """
        self.prestar(self.taladro)
        self.prestar(self.rotomartillo, devuelto_en=Activo.Estado.BUEN_ESTADO)

        with patch.object(views.boletas, 'hoja_prestamos', return_value=b'%PDF-') as generar:
            self.client.get(self.url, {'estado': 'devueltos'})

        recibidos = list(generar.call_args.args[0])
        self.assertEqual([p.activo for p in recibidos], [self.rotomartillo])

    def test_contabilidad_tambien_puede_imprimir(self):
        self.client.login(username='cont_hoja', password='clave-de-prueba')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_sin_sesion_no_se_descarga(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_la_pantalla_ofrece_el_enlace_al_pdf(self):
        self.assertContains(self.client.get(reverse('prestamos_tecnica')), self.url)
