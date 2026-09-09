"""
Cómo se escribe el serial en la columna del catálogo.

Antes el serial vivía en el producto, con restricción de único. Eso solo
funciona si cada producto es una sola unidad física: con 4 indicadores del
mismo modelo el campo no daba, porque solo cabía un serial. Ahora vive en la
unidad (ver `test_unidades.py`).

Lo que queda acá es la forma de mostrarlo:

- Un producto que **no** lleva serie sigue diciendo **S/S**, la abreviatura que
  ya usaban en la empresa. No cambió nada para los repuestos.
- Uno que **sí** la lleva no tiene *un* serial que mostrar —tiene varios—, así
  que dice cuántas unidades hay y los seriales se listan en la ficha.
"""

import io

import openpyxl
from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import (
    SIN_SERIAL, Articulo, MovimientoVenta, UnidadArticulo, ingresar_unidades,
)


class BaseSerial(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.admin = Usuario.objects.create_user(
            username='admin_serial', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.repuesto = Articulo.objects.create(
            nombre_producto='CONECTOR RJ45', modelo='C-1', bodega=cls.bodega, precio=25,
        )
        cls.equipo = Articulo.objects.create(
            nombre_producto='INDICADOR SE7581P', modelo='SE7581P', bodega=cls.bodega,
            precio=5500, lleva_serie=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def dar_unidades(self, articulo, *seriales):
        movimiento = MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL,
            cantidad=len(seriales), usuario=self.admin,
        )
        ingresar_unidades(movimiento, seriales)
        articulo.refresh_from_db()
        return movimiento


class LoQueNoLlevaSerieTests(BaseSerial):
    """Para los repuestos no cambió nada."""

    def test_dice_ss(self):
        self.assertEqual(self.repuesto.serial, SIN_SERIAL)
        self.assertEqual(self.repuesto.serial, 'S/S')

    def test_el_catalogo_lo_muestra(self):
        respuesta = self.client.get(reverse('catalogo_articulos'))

        self.assertContains(respuesta, 'S/S')

    def test_la_ficha_lo_muestra(self):
        respuesta = self.client.get(reverse('articulo_detalle', args=[self.repuesto.pk]))

        self.assertContains(respuesta, 'S/S')
        self.assertContains(respuesta, 'Número de serial')

    def test_la_ficha_no_le_pinta_la_lista_de_unidades(self):
        respuesta = self.client.get(reverse('articulo_detalle', args=[self.repuesto.pk]))

        self.assertNotContains(respuesta, 'Unidades</h2>', html=False)


class LoQueSiLlevaSerieTests(BaseSerial):
    def test_sin_unidades_dice_cero(self):
        self.assertEqual(self.equipo.serial, '0 unidades')

    def test_con_una_lo_dice_en_singular(self):
        self.dar_unidades(self.equipo, 'A-1001')

        self.assertEqual(self.equipo.serial, '1 unidad')

    def test_con_varias_dice_cuantas(self):
        self.dar_unidades(self.equipo, 'A-1001', 'A-1002', 'A-1003', 'A-1004')

        self.assertEqual(self.equipo.serial, '4 unidades')

    def test_no_dice_ss(self):
        """Decir S/S en un equipo con seriales sería mentir."""
        self.dar_unidades(self.equipo, 'A-1001')

        self.assertNotEqual(self.equipo.serial, SIN_SERIAL)

    def test_la_ficha_cambia_la_etiqueta(self):
        self.dar_unidades(self.equipo, 'A-1001')

        respuesta = self.client.get(reverse('articulo_detalle', args=[self.equipo.pk]))

        self.assertContains(respuesta, 'Unidades en bodega')


class FiltroDePlantillaTests(TestCase):
    """
    El filtro sigue existiendo para las pantallas que trabajan con datos
    sueltos y no con un artículo del catálogo.
    """

    def test_hace_lo_mismo_que_antes(self):
        from ventas.templatetags.catalogo_extras import serial

        self.assertEqual(serial('AB-12345'), 'AB-12345')
        self.assertEqual(serial(''), SIN_SERIAL)
        self.assertEqual(serial(None), SIN_SERIAL)


class ReporteDeExistenciasTests(BaseSerial):
    def hoja(self):
        respuesta = self.client.get(reverse('reporte_existencias'), {'formato': 'excel'})
        self.assertEqual(respuesta.status_code, 200)
        return openpyxl.load_workbook(io.BytesIO(respuesta.content)).active

    def columnas(self, hoja):
        for fila in range(1, 15):
            if hoja.cell(row=fila, column=1).value == 'Código':
                titulos = {}
                for columna in range(1, 20):
                    valor = hoja.cell(row=fila, column=columna).value
                    if valor:
                        titulos[valor] = columna
                return fila, titulos
        self.fail('no se encontró el encabezado de la hoja')

    def test_la_pantalla_muestra_las_dos_formas(self):
        self.dar_unidades(self.equipo, 'A-1001', 'A-1002')

        respuesta = self.client.get(reverse('reporte_existencias'))

        self.assertContains(respuesta, 'S/S')
        self.assertContains(respuesta, '2 unidades')

    def test_el_excel_trae_la_columna(self):
        _fila, titulos = self.columnas(self.hoja())

        self.assertIn('N.º de serial', titulos)

    def test_el_formato_de_moneda_sigue_en_las_columnas_de_dinero(self):
        """
        Regresión: la columna del serial corre las que van después, y los
        formatos de moneda se indican por número de columna.
        """
        from core import exportar

        hoja = self.hoja()
        fila_enc, titulos = self.columnas(hoja)

        for titulo in ('Precio unitario', 'Valor total'):
            with self.subTest(columna=titulo):
                celda = hoja.cell(row=fila_enc + 1, column=titulos[titulo])
                self.assertEqual(celda.number_format, exportar.FORMATO_MONEDA)

        for titulo in ('Existencia', 'Nivel'):
            with self.subTest(columna=titulo):
                celda = hoja.cell(row=fila_enc + 1, column=titulos[titulo])
                self.assertNotEqual(celda.number_format, exportar.FORMATO_MONEDA)
