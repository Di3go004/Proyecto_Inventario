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
from ventas import boletas, documentos
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


class ProveedorEnLaBoletaTests(BaseBoletas):
    """
    En la columna "Nombre de proveedor" del FO-SE-013 va el proveedor del
    artículo. Antes se pedía a mano al registrar el ingreso, que era escribir
    otra vez un dato que el catálogo ya tenía; ahora se hereda solo.
    """

    def _columna_proveedor(self, folio):
        filas = boletas._filas(documentos.lineas_del_documento(folio), es_ingreso=True)
        return [fila[3].text for fila in filas]

    def test_hereda_el_proveedor_del_articulo(self):
        self.articulo.proveedor = self.proveedor
        self.articulo.save()
        self.crear_documento('ING-00010', MovimientoVenta.TipoDocumento.INGRESO)

        self.assertEqual(self._columna_proveedor('ING-00010'), ['BRECKNELL'])

    def test_el_proveedor_del_movimiento_le_gana_al_del_catalogo(self):
        """Una compra puntual a otro proveedor no debe reescribir el catálogo."""
        self.articulo.proveedor = self.proveedor
        self.articulo.save()
        otro = Proveedor.objects.create(nombre='CELASA')
        self.crear_documento('ING-00011', MovimientoVenta.TipoDocumento.INGRESO, proveedor=otro)

        self.assertEqual(self._columna_proveedor('ING-00011'), ['CELASA'])

    def test_si_no_hay_proveedor_la_celda_queda_en_blanco(self):
        """
        El artículo sin proveedor en el catálogo no puede reventar la boleta:
        se imprime la casilla vacía, para llenarla a mano como antes.
        """
        self.assertIsNone(self.articulo.proveedor)
        self.crear_documento('ING-00012', MovimientoVenta.TipoDocumento.INGRESO)

        self.assertEqual(self._columna_proveedor('ING-00012'), [''])


class ProveedorEnPantallaTests(BaseBoletas):
    """
    Cuando la casilla de la boleta sale vacía hay que poder ver por qué desde
    la pantalla del documento, o parece que el sistema perdió el dato.
    """

    def test_el_documento_muestra_el_proveedor_heredado(self):
        self.articulo.proveedor = self.proveedor
        self.articulo.save()
        self.crear_documento('ING-00013', MovimientoVenta.TipoDocumento.INGRESO)

        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse('documento_detalle', args=['ING-00013']))

        self.assertContains(respuesta, 'BRECKNELL')
        self.assertNotContains(respuesta, 'Sin proveedor')

    def test_avisa_cuando_al_articulo_le_falta_el_proveedor(self):
        self.crear_documento('ING-00014', MovimientoVenta.TipoDocumento.INGRESO)

        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse('documento_detalle', args=['ING-00014']))

        self.assertContains(respuesta, 'Sin proveedor')

    def test_solo_el_administrador_recibe_el_enlace_para_corregirlo(self):
        """Editar el artículo es de administrador; a los demás sería un 403."""
        self.crear_documento('ING-00015', MovimientoVenta.TipoDocumento.INGRESO)
        enlace = reverse('articulo_editar', args=[self.articulo.pk])
        direccion = reverse('documento_detalle', args=['ING-00015'])

        self.client.force_login(self.operador)
        self.assertNotContains(self.client.get(direccion), enlace)

        admin = Usuario.objects.create_user(
            username='admin_pdf', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.client.force_login(admin)
        self.assertContains(self.client.get(direccion), enlace)


class TamanoDeLaHojaTests(BaseBoletas):
    """
    El talonario real de FO-SE-013 y FO-SE-012 es de media carta. Salían en
    carta completa, y así la boleta impresa no calzaba con las de papel de
    los años anteriores, que se archivan en el mismo folder.
    """

    def test_va_en_media_carta_apaisada(self):
        from reportlab.lib.units import mm

        ancho, alto = boletas.PAGINA
        self.assertAlmostEqual(ancho / mm, 216, delta=1)
        self.assertAlmostEqual(alto / mm, 140, delta=1)
        self.assertGreater(ancho, alto, 'la boleta es apaisada')

    def test_es_la_carta_partida_a_la_mitad(self):
        """
        No sirve el HALF_LETTER de ReportLab: ese mide 140 × 203 mm (5.5 × 8")
        y no es media carta.
        """
        from reportlab.lib.pagesizes import HALF_LETTER, letter

        self.assertEqual(boletas.PAGINA, (letter[0], letter[1] / 2))
        self.assertNotEqual(boletas.PAGINA, HALF_LETTER)

    def test_una_boleta_llena_cabe_en_una_sola_hoja(self):
        """
        Con las firmas abajo, no puede pasarse a una segunda página: la hoja
        que se firma y archiva tiene que ser una.
        """
        self.crear_documento(
            'SAL-LLENA', MovimientoVenta.TipoDocumento.SALIDA,
            cuantas=boletas.FILAS_POR_PAGINA,
            observacion='Equipo entregado para demostración en planta del cliente.',
        )
        contenido = boletas.boleta_documento('SAL-LLENA')

        self.assertEqual(self.cuantas_paginas(contenido), 1)

    def cuantas_paginas(self, pdf_bytes):
        """Cuenta los objetos /Type /Page del PDF (sin /Pages, que es el índice)."""
        import re
        return len(re.findall(rb'/Type\s*/Page[^s]', pdf_bytes))


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

    @property
    def ancho_descripcion(self):
        """La columna "DESCRIPCIÓN Y CÓDIGO" de FO-SE-012."""
        return boletas.COLUMNAS_SALIDA[1][1]

    def linea_de(self, articulo):
        """
        Una línea de boleta suelta, sin guardar nada. La boleta ya no recibe
        el movimiento crudo: recibe la línea normalizada, porque un mismo
        folio puede traer productos de las dos bodegas.
        """
        return documentos._de_venta(MovimientoVenta(articulo=articulo, cantidad=1))

    def test_la_descripcion_lleva_el_codigo_interno(self):
        texto = boletas._descripcion(self.linea_de(self.articulo), self.ancho_descripcion)

        self.assertIn('Báscula de plataforma', texto)
        self.assertIn(self.articulo.codigo_interno, texto)

    def test_una_descripcion_larga_se_recorta_a_un_renglon(self):
        """
        Regresión: un nombre muy largo hacía crecer la fila a dos renglones y,
        en media carta, empujaba el bloque de firmas a una hoja aparte.
        """
        largo = Articulo.objects.create(
            nombre_producto='BASCULA ELECTRONICA ' * 9, modelo='XL-1', bodega=self.bodega,
        )
        texto = boletas._descripcion(self.linea_de(largo), self.ancho_descripcion)

        self.assertTrue(texto.endswith('…'))
        self.assertTrue(self.cabe_en_un_renglon(texto, self.ancho_descripcion))

    def test_un_nombre_normal_no_se_recorta(self):
        """Los nombres reales del catálogo entran completos, con su código."""
        texto = boletas._descripcion(self.linea_de(self.articulo), self.ancho_descripcion)

        self.assertFalse(texto.endswith('…'))
        self.assertTrue(self.cabe_en_un_renglon(texto, self.ancho_descripcion))

    def cabe_en_un_renglon(self, texto, ancho_columna):
        from reportlab.pdfbase.pdfmetrics import stringWidth

        from core import pdf
        ancho = stringWidth(texto, pdf.CELDA_CHICA.fontName, pdf.CELDA_CHICA.fontSize)
        return ancho <= ancho_columna - boletas.RELLENO_CELDA


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
