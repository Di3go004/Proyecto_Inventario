"""
Un solo número por documento: el de la boleta de papel.

Había dos campos para lo mismo. Cuando se diseñó el modelo, el folio iba a ser
una serie automática del sistema, así que hacía falta `no_boleta` aparte para
anotar el número del talonario. Después se decidió que el folio se escribe a
mano —lo trae impreso el papel—, y el segundo campo quedó pidiendo un dato que
ya estaba en el primero.

No se imprimía en el PDF, no lo buscaba el buscador, no lo mapeaba la carga
masiva y no salía en ningún reporte: solo pedía escribir dos veces el mismo
número. En pantalla ahora se llama **boleta** en todas partes, que es lo que
es; "folio" se queda como nombre del campo en la base, donde no lo lee nadie.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BaseBoleta(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_boleta', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='BASCULA', modelo='B-1', bodega=cls.venta, precio=100,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def ingreso(self, folio='ING-00001'):
        return MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin, folio=folio, solicitado_por='Diego González',
        )


class ElCampoDuplicadoYaNoExisteTests(BaseBoleta):
    def test_no_esta_en_ninguno_de_los_dos_modelos(self):
        for modelo in (MovimientoVenta, MovimientoActivo):
            with self.subTest(modelo=modelo.__name__):
                campos = [f.name for f in modelo._meta.get_fields()]
                self.assertNotIn('no_boleta', campos)

    def test_el_formulario_ya_no_lo_pide(self):
        for pantalla in ('movimiento_ingreso', 'movimiento_salida'):
            with self.subTest(pantalla=pantalla):
                respuesta = self.client.get(reverse(pantalla))
                self.assertNotContains(respuesta, 'no_boleta')

    def test_la_pantalla_del_documento_ya_no_lo_muestra(self):
        self.ingreso()

        respuesta = self.client.get(reverse('documento_detalle', args=['ING-00001']))

        self.assertNotContains(respuesta, 'Boleta de ingreso a bodega')
        self.assertNotContains(respuesta, 'Boleta de salida</dt>', html=False)


class ElUnicoNumeroEsElDeLaBoletaTests(BaseBoleta):
    def test_el_formulario_lo_llama_numero_de_boleta(self):
        respuesta = self.client.get(reverse('movimiento_ingreso'))

        self.assertContains(respuesta, 'Número de boleta')
        self.assertNotContains(respuesta, 'Folio de la boleta')

    def test_se_sigue_guardando_lo_que_se_escribe(self):
        """El número viene del talonario de papel; no se genera."""
        movimiento = self.ingreso(folio='A-4471')

        self.assertEqual(movimiento.folio, 'A-4471')

    def test_la_boleta_impresa_lo_lleva(self):
        self.ingreso(folio='A-4471')

        respuesta = self.client.get(reverse('documento_pdf', args=['A-4471']))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')


class SeLlamaIgualEnTodasLasPantallasTests(BaseBoleta):
    """
    Antes la misma cosa se llamaba "folio" en unas pantallas y "boleta" en
    otras, y encima había un campo aparte llamado también "boleta". Que no
    vuelva a pasar.
    """

    def test_ninguna_pantalla_dice_folio(self):
        self.ingreso()

        pantallas = [
            reverse('movimientos_ventas'),
            reverse('movimiento_ingreso'),
            reverse('movimiento_salida'),
            reverse('documento_detalle', args=['ING-00001']),
            reverse('kardex_articulo', args=[self.articulo.pk]),
            reverse('articulo_detalle', args=[self.articulo.pk]),
            reverse('reporte_movimientos'),
        ]
        for url in pantallas:
            with self.subTest(pantalla=url):
                cuerpo = self.client.get(url).content.decode()
                self.assertNotIn('Folio', cuerpo)
                self.assertNotIn('folio,', cuerpo, 'quedó en el texto del buscador')

    def test_el_historial_titula_la_columna_Boleta(self):
        self.ingreso()

        respuesta = self.client.get(reverse('movimientos_ventas'))

        self.assertContains(respuesta, '<th>Boleta</th>', html=True)

    def test_el_buscador_lo_dice_asi(self):
        respuesta = self.client.get(reverse('movimientos_ventas'))

        self.assertContains(respuesta, 'Buscar por número de boleta')

    def test_la_pantalla_del_documento_se_titula_Boleta(self):
        self.ingreso()

        respuesta = self.client.get(reverse('documento_detalle', args=['ING-00001']))

        self.assertContains(respuesta, 'Boleta ING-00001')

    def test_el_mensaje_al_guardar_habla_de_la_boleta(self):
        respuesta = self.client.post(reverse('movimiento_ingreso'), {
            'folio': 'ING-00099', 'fecha': '2026-09-08T10:00',
            'tipo_transaccion': MovimientoVenta.TipoTransaccion.VENTA,
            'solicitado_por': 'Diego González', 'no_factura': '', 'observacion': '',
            'linea_texto': [self.articulo.codigo_interno],
            'linea_articulo': [str(self.articulo.pk)],
            'linea_cantidad': ['2'], 'linea_precio': [''],
        }, follow=True)

        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(
            any('boleta ING-00099' in m for m in mensajes),
            f'el mensaje no menciona la boleta: {mensajes}',
        )

    def test_el_error_de_un_numero_que_no_existe_tambien(self):
        respuesta = self.client.get(reverse('documento_detalle', args=['NO-EXISTE']), follow=True)

        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(
            any('boleta' in m.lower() for m in mensajes),
            f'el mensaje no habla de la boleta: {mensajes}',
        )
