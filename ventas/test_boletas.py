"""
Pruebas de las boletas en PDF de Bodega 1 y 2 (RF-10).

Un PDF es difícil de inspeccionar por dentro sin arrastrar otra dependencia
solo para las pruebas, así que se comprueba lo que sí se puede afirmar con
certeza: que el archivo se genera y es válido, que las reglas de armado
(cuántas líneas por hoja, qué casilla se marca, cómo se recorta una
descripción larga) son las correctas, y que la vista responde como debe a
cada rol. El aspecto visual se revisó abriendo los PDF generados.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega, Proveedor
from usuarios.models import Usuario
from ventas import boletas
from ventas.models import Articulo, MovimientoVenta


class BaseBoletas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.proveedor = Proveedor.objects.create(nombre='BRECKNELL')
        cls.operador = Usuario.objects.create_user(
            username='op_pdf', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='cont_pdf', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='Báscula de plataforma', modelo='BP-300',
            capacidad='300kg', bodega=cls.bodega, precio=1500,
        )

    def crear_documento(self, folio, tipo_documento, cuantas=1, **extra):
        datos = dict(
            folio=folio, tipo_documento=tipo_documento,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            fecha=timezone.now(), usuario=self.operador,
            solicitado_por='Marisol Pérez',
        )
        datos.update(extra)
        if tipo_documento == MovimientoVenta.TipoDocumento.SALIDA:
            MovimientoVenta.objects.create(
                folio='ING-SEED', tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
                tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
                articulo=self.articulo, cantidad=cuantas * 10,
                fecha=timezone.now(), usuario=self.operador,
            )
        for _ in range(cuantas):
            MovimientoVenta.objects.create(articulo=self.articulo, cantidad=1, **datos)


class GeneracionTests(BaseBoletas):
    def test_genera_un_pdf_valido(self):
        self.crear_documento('ING-00001', MovimientoVenta.TipoDocumento.INGRESO, cuantas=3)

        contenido = boletas.boleta_documento('ING-00001')

        self.assertTrue(contenido.startswith(b'%PDF'), 'debe ser un PDF de verdad')
        self.assertGreater(len(contenido), 1000)

    def test_la_salida_tambien_genera(self):
        self.crear_documento('SAL-00001', MovimientoVenta.TipoDocumento.SALIDA, cuantas=2)
        self.assertTrue(boletas.boleta_documento('SAL-00001').startswith(b'%PDF'))

    def test_un_folio_que_no_existe_avisa(self):
        with self.assertRaises(MovimientoVenta.DoesNotExist):
            boletas.boleta_documento('NO-EXISTE')


class ArmadoDeLaHojaTests(BaseBoletas):
    def test_las_lineas_se_reparten_en_hojas(self):
        por_hoja = boletas.FILAS_POR_PAGINA

        self.assertEqual(len(boletas.agrupar_en_paginas(list(range(por_hoja)))), 1)
        self.assertEqual(len(boletas.agrupar_en_paginas(list(range(por_hoja + 1)))), 2)
        self.assertEqual(len(boletas.agrupar_en_paginas(list(range(por_hoja * 3)))), 3)

    def test_la_primera_hoja_va_llena(self):
        grupos = boletas.agrupar_en_paginas(list(range(boletas.FILAS_POR_PAGINA + 2)))
        self.assertEqual(len(grupos[0]), boletas.FILAS_POR_PAGINA)
        self.assertEqual(len(grupos[1]), 2)

    def test_la_descripcion_lleva_el_codigo_interno(self):
        movimiento = MovimientoVenta(articulo=self.articulo, cantidad=1)
        texto = boletas._descripcion(movimiento)

        self.assertIn('Báscula de plataforma', texto)
        self.assertIn(self.articulo.codigo_interno, texto)

    def test_una_descripcion_larga_se_recorta(self):
        """
        Regresión: un nombre muy largo hacía crecer la fila a tres renglones
        y empujaba el bloque de firmas a una hoja aparte casi vacía.
        """
        largo = Articulo.objects.create(
            nombre_producto='B' * 200, modelo='XL-1', bodega=self.bodega,
        )
        texto = boletas._descripcion(MovimientoVenta(articulo=largo, cantidad=1))
        nombre = texto.split('<br/>')[0]

        self.assertLessEqual(len(nombre), boletas.MAX_DESCRIPCION)
        self.assertTrue(nombre.endswith('…'))


class CasillasTests(BaseBoletas):
    """La X tiene que caer en la casilla del tipo de movimiento registrado."""

    def marcadas(self, tipo_transaccion):
        from core import pdf
        tabla = pdf.casillas(boletas.OPCIONES_TIPO, tipo_transaccion)
        # Cada fila es [etiqueta, marca]; se devuelven las etiquetas con X.
        return [
            fila[0].text for fila in tabla._cellvalues if fila[1].text == 'X'
        ]

    def test_marca_solo_la_casilla_que_corresponde(self):
        self.assertEqual(
            self.marcadas(MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO),
            ['Equipo préstamo'],
        )
        self.assertEqual(
            self.marcadas(MovimientoVenta.TipoTransaccion.VENTA),
            ['Equipo venta'],
        )

    def test_un_tipo_sin_casilla_no_marca_ninguna(self):
        """El ajuste inicial de la carga masiva no es una casilla del papel."""
        self.assertEqual(
            self.marcadas(MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL), [],
        )


class VistaDelPdfTests(BaseBoletas):
    def setUp(self):
        self.client.login(username='op_pdf', password='clave-de-prueba')
        self.crear_documento('ING-00042', MovimientoVenta.TipoDocumento.INGRESO, cuantas=2)
        self.url = reverse('documento_pdf', args=['ING-00042'])

    def test_responde_un_pdf_para_ver_en_el_navegador(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertIn('inline', respuesta['Content-Disposition'])
        self.assertIn('ING-00042.pdf', respuesta['Content-Disposition'])
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_un_folio_inexistente_da_404(self):
        self.assertEqual(
            self.client.get(reverse('documento_pdf', args=['SAL-99999'])).status_code, 404,
        )

    def test_contabilidad_tambien_puede_imprimir(self):
        """RF-04: imprimir es consultar, no modificar."""
        self.client.login(username='cont_pdf', password='clave-de-prueba')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_sin_sesion_no_se_descarga(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_el_documento_ofrece_el_enlace_al_pdf(self):
        pantalla = self.client.get(reverse('documento_detalle', args=['ING-00042']))
        self.assertContains(pantalla, self.url)
