"""
El reporte de existencias y valorización en PDF, para imprimir.

El Excel es para trabajar los datos; este es para imprimir y archivar. Trae
lo mismo —el resumen por bodega, Bodega Técnica y el detalle con cada unidad
debajo de su producto— pero con los totales ya hechos, agrupado por bodega y
en carta horizontal.

Lo que más importa, igual que en el Excel: que diga lo mismo que la pantalla.
Las pruebas leen el texto del PDF tal como sale impreso.
"""

import re

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.ayuda_pruebas import dar_existencia
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import (
    Articulo, MovimientoVenta, UnidadArticulo, ingresar_unidades, sacar_unidades,
)
from ventas.test_salidas_abiertas import cuantas_hojas, texto_del_pdf

TIPO = MovimientoVenta.TipoTransaccion


class BaseReportePdf(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.b1 = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.b2 = Bodega.objects.create(nombre='Bodega 2', tipo=Bodega.Tipo.VENTA)
        cls.btec = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)

        clave = 'clave-de-prueba'
        cls.admin = Usuario.objects.create_user(
            username='admin_pdf', password=clave, rol=Usuario.Rol.ADMINISTRADOR,
            first_name='Diego', last_name='Prueba',
        )
        cls.contable = Usuario.objects.create_user(
            username='cont_pdf', password=clave, rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.operador = Usuario.objects.create_user(
            username='op_pdf', password=clave, rol=Usuario.Rol.OPERADOR,
        )
        cls.practicante = Usuario.objects.create_user(
            username='prac_pdf', password=clave, rol=Usuario.Rol.PRACTICANTE,
        )

        # Bodega 1: un indicador con serie (entraron 3, se vendió 1) y celdas.
        cls.indicador = cls.articulo('Indicador ZM405', cls.b1, 2500, lleva_serie=True)
        entrada = cls.ingresar(cls.indicador, 3, folio='ING-00001')
        ingresar_unidades(entrada, ['A-1001', 'A-1002', 'A-1003'])
        venta = MovimientoVenta.objects.create(
            folio='SAL-00001', articulo=cls.indicador, cantidad=1, cantidad_vendida=1,
            tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=TIPO.VENTA, usuario=cls.admin,
        )
        sacar_unidades(venta, UnidadArticulo.objects.filter(numero_serie='A-1002'), vendidas=True)
        cls.celda = cls.articulo('Celda de carga', cls.b1, 800)
        cls.ingresar(cls.celda, 10)

        # Bodega 2: una báscula activa y un producto inactivo.
        cls.bascula = cls.articulo('Báscula de piso', cls.b2, 3000)
        cls.ingresar(cls.bascula, 2)
        cls.inactivo = cls.articulo('Modelo descontinuado', cls.b2, 100, activo=False)
        cls.ingresar(cls.inactivo, 5)

        cls.taladro = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='Taladro', bodega=cls.btec, precio=900,
        )
        dar_existencia(cls.taladro, 1, cls.admin)

    @classmethod
    def articulo(cls, nombre, bodega, precio, lleva_serie=False, activo=True):
        return Articulo.objects.create(
            nombre_producto=nombre, modelo=nombre.split()[0], capacidad='1kg',
            bodega=bodega, precio=precio, lleva_serie=lleva_serie, activo=activo,
        )

    @classmethod
    def ingresar(cls, articulo, cantidad, folio='ING-TEST'):
        return MovimientoVenta.objects.create(
            folio=folio, articulo=articulo, cantidad=cantidad,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=TIPO.VENTA, usuario=cls.admin,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def pdf(self, **filtros):
        respuesta = self.client.get(reverse('reporte_existencias'), {'formato': 'pdf', **filtros})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def texto(self, **filtros):
        return texto_del_pdf(self.pdf(**filtros).content)


class EntregaTests(BaseReportePdf):
    def test_se_abre_en_el_navegador_para_imprimir(self):
        respuesta = self.pdf()

        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertEqual(respuesta.content[:5], b'%PDF-')
        # inline y no attachment: se abre en el visor, que es desde donde se
        # manda a la impresora, igual que las boletas.
        hoy = f'{timezone.localtime():%Y-%m-%d}'
        self.assertEqual(
            respuesta['Content-Disposition'], f'inline; filename="existencias-{hoy}.pdf"',
        )
        self.assertIn('no-store', respuesta['Cache-Control'])

    def test_va_en_carta_horizontal(self):
        contenido = self.pdf().content
        # 792 × 612 puntos: carta (8.5 × 11") acostada.
        cajas = re.findall(rb'/MediaBox\s*\[\s*0 0 792 612\s*\]', contenido)
        self.assertEqual(len(cajas), cuantas_hojas(contenido))

    def test_lo_ven_administrador_y_contabilidad(self):
        self.client.force_login(self.contable)
        self.assertEqual(self.pdf()['Content-Type'], 'application/pdf')

    def test_el_operador_y_el_practicante_no(self):
        for usuario in (self.operador, self.practicante):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                respuesta = self.client.get(reverse('reporte_existencias'), {'formato': 'pdf'})
                self.assertEqual(respuesta.status_code, 403)

    def test_la_pantalla_ofrece_el_pdf_con_sus_filtros(self):
        respuesta = self.client.get(reverse('reporte_existencias'), {'bodega': self.b2.pk})
        self.assertContains(respuesta, 'Imprimir (PDF)')
        enlace = re.search(r'href="\?([^"]*formato=pdf[^"]*)"[^>]*target="_blank"',
                           respuesta.content.decode())
        self.assertIsNotNone(enlace, 'el botón abre el PDF en otra pestaña')
        self.assertIn(f'bodega={self.b2.pk}', enlace.group(1))


class ContenidoTests(BaseReportePdf):
    def test_encabezado_con_empresa_titulo_filtros_y_quien_lo_genero(self):
        texto = self.texto()

        self.assertIn('SOLUCIONES EXACTAS, S.A.', texto)
        self.assertIn('Existencias y valorización', texto)
        self.assertIn('Bodega: Todas', texto)
        self.assertIn('Solo artículos activos', texto)
        self.assertIn(f'Generado el {timezone.localtime():%Y-%m-%d}', texto)
        self.assertIn('por Diego Prueba', texto)

    def test_resumen_por_bodega_con_su_total(self):
        texto = self.texto()

        # Bodega 1: 2 indicadores × 2,500 + 10 celdas × 800. Bodega 2: 2 × 3,000.
        self.assertIn('Q 13,000.00', texto)
        self.assertIn('Q 6,000.00', texto)
        self.assertIn('Total Bodega 1 y 2', texto)
        self.assertIn('Q 19,000.00', texto)

    def test_trae_bodega_tecnica(self):
        texto = self.texto()
        self.assertIn('Bodega Técnica', texto)
        self.assertIn('Q 900.00', texto)

    def test_cada_unidad_en_bodega_va_debajo_de_su_producto(self):
        texto = self.texto()

        producto = texto.index('Indicador ZM405')
        primera, segunda = texto.index('A-1001'), texto.index('A-1003')
        siguiente = texto.index('Total Bodega 1', producto)
        self.assertTrue(producto < primera < segunda < siguiente, 'las unidades van bajo su producto')
        self.assertIn('Entró con la boleta ING-00001', texto)
        # La vendida ya no es existencia.
        self.assertNotIn('A-1002', texto)

    def test_cada_bodega_cierra_con_su_total_y_el_detalle_con_el_general(self):
        texto = self.texto()
        detalle = texto[texto.index('Detalle por artículo'):]

        # El total de Bodega 1 va antes de empezar Bodega 2, y el de Bodega 2
        # después de sus productos.
        bodega_2 = detalle.index('Báscula de piso')
        self.assertLess(detalle.index('Total Bodega 1'), bodega_2)
        self.assertLess(detalle.index('Q 13,000.00'), bodega_2)
        self.assertGreater(detalle.index('Total Bodega 2'), bodega_2)
        self.assertGreater(detalle.index('Q 6,000.00'), bodega_2)
        # El general cierra el detalle; el otro es el del resumen.
        self.assertEqual(texto.count('Total Bodega 1 y 2'), 2)
        self.assertGreater(detalle.index('Total Bodega 1 y 2'), detalle.index('Total Bodega 2'))
        self.assertGreater(detalle.index('Q 19,000.00'), detalle.index('Q 6,000.00'))

    def test_con_una_sola_bodega_no_dice_total_bodega_1_y_2(self):
        texto = self.texto(bodega=self.b2.pk)
        # Con lo de una sola bodega, "Total Bodega 1 y 2" se leería como el
        # total de las dos. El total que va es el de la bodega.
        self.assertNotIn('Total Bodega 1 y 2', texto)
        self.assertIn('Total Bodega 2', texto)
        self.assertIn('Q 6,000.00', texto)

    def test_respeta_los_filtros_de_la_pantalla(self):
        solo_bodega_2 = self.texto(bodega=self.b2.pk)
        self.assertIn('Bodega: Bodega 2', solo_bodega_2)
        self.assertIn('Báscula de piso', solo_bodega_2)
        self.assertNotIn('Celda de carga', solo_bodega_2)

        self.assertNotIn('Modelo descontinuado', self.texto())
        con_inactivos = self.texto(activos='no')
        self.assertIn('Modelo descontinuado', con_inactivos)
        self.assertIn('Activos e inactivos', con_inactivos)

    def test_dice_lo_mismo_que_la_pantalla(self):
        pantalla = self.client.get(reverse('reporte_existencias')).context['totales']
        texto = self.texto()

        self.assertIn(f"Q {pantalla['valor']:,.2f}", texto)
        for producto in ('Indicador ZM405', 'Celda de carga', 'Báscula de piso'):
            self.assertIn(producto, texto)

    def test_un_nombre_con_simbolos_sale_tal_cual(self):
        # El PDF interpreta etiquetas. Sin escapar, "<SE>" desaparecía del
        # nombre sin avisar, y un "<" sin cerrar tumbaba el reporte entero.
        for nombre in ('Indicador <SE> 7600', 'Cable de 3/4 <largo'):
            self.ingresar(self.articulo(nombre, self.b1, 10), 1)
        texto = self.texto()
        self.assertIn('Indicador <SE> 7600', texto)
        self.assertIn('Cable de 3/4 <largo', texto)

    def test_sin_articulos_no_revienta(self):
        vacia = Bodega.objects.create(nombre='Bodega 3', tipo=Bodega.Tipo.VENTA)
        self.assertIn('No hay artículos que coincidan', self.texto(bodega=vacia.pk))


class HojasTests(BaseReportePdf):
    def test_numera_las_hojas_y_repite_de_que_reporte_es(self):
        for numero in range(80):
            self.ingresar(self.articulo(f'Repuesto {numero:03d}', self.b1, 5), 1)

        contenido = self.pdf().content
        hojas = cuantas_hojas(contenido)
        texto = texto_del_pdf(contenido)

        self.assertGreater(hojas, 2)
        for numero in range(1, hojas + 1):
            self.assertIn(f'Página {numero} de {hojas}', texto)
        # De la segunda en adelante, una línea arriba dice de qué reporte es: una
        # hoja suelta se tiene que poder reconocer.
        self.assertEqual(texto.count('Existencias y valorización  ·  Bodega: Todas'), hojas - 1)
