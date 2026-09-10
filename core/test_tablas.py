"""
Que ninguna tabla tenga más celdas que encabezados.

Se agregó después de una: editando el kardex quedó una celda de "Boleta"
repetida, así que las filas traían nueve celdas contra ocho títulos. En
pantalla eso corre todos los datos una columna a la derecha —la fecha bajo
"Boleta", el cliente bajo un encabezado que no existe— y no rompe nada, no
lanza ningún error, y ninguna prueba de contenido lo nota: los textos que
buscan siguen estando, solo que en la columna equivocada.

Es una clase de error, no un error: cada vez que se agrega o quita una
columna hay que tocar el encabezado y las filas, y olvidarse de uno de los
dos lados no avisa. Por eso la prueba recorre las pantallas con tabla en vez
de comprobar una sola.
"""

from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega, Proveedor
from tecnica.ayuda_pruebas import dar_existencia
from tecnica.models import Activo, PrestamoActivo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta, ingresar_unidades


class LectorDeTablas(HTMLParser):
    """
    Cuenta celdas por fila, tabla por tabla.

    Cuenta `colspan` como las columnas que ocupa: las filas de "no hay nada
    que mostrar" son una sola celda estirada a todo lo ancho y son correctas.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tablas = []
        self._tabla = None
        self._fila = None
        self._en_encabezado = False

    def handle_starttag(self, etiqueta, atributos):
        atributos = dict(atributos)
        if etiqueta == 'table':
            self._tabla = {'titulos': None, 'filas': []}
        elif etiqueta == 'tr' and self._tabla is not None:
            self._fila = {'celdas': 0, 'encabezado': False}
        elif etiqueta in ('th', 'td') and self._fila is not None:
            try:
                cuantas = int(atributos.get('colspan', 1))
            except ValueError:
                cuantas = 1
            self._fila['celdas'] += cuantas
            if etiqueta == 'th':
                self._fila['encabezado'] = True

    def handle_endtag(self, etiqueta):
        if etiqueta == 'tr' and self._fila is not None and self._tabla is not None:
            if self._fila['encabezado'] and self._tabla['titulos'] is None:
                self._tabla['titulos'] = self._fila['celdas']
            elif self._fila['celdas']:
                self._tabla['filas'].append(self._fila['celdas'])
            self._fila = None
        elif etiqueta == 'table' and self._tabla is not None:
            self.tablas.append(self._tabla)
            self._tabla = None


class TablasCuadradasTests(TestCase):
    """Cada pantalla con tabla, con datos de verdad adentro."""

    @classmethod
    def setUpTestData(cls):
        cls.b1 = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.btec = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_tablas', password='clave-de-prueba',
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        proveedor = Proveedor.objects.create(nombre='Proveedor de prueba')

        cls.equipo = Articulo.objects.create(
            nombre_producto='INDICADOR SE7581P', modelo='SE7581P', bodega=cls.b1,
            precio=1000, lleva_serie=True, proveedor=proveedor,
        )
        cls.repuesto = Articulo.objects.create(
            nombre_producto='CONECTOR RJ45', modelo='C-1', bodega=cls.b1, precio=25,
        )

        ingreso = MovimientoVenta.objects.create(
            folio='ING-00001', articulo=cls.equipo, cantidad=2,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            usuario=cls.admin, proveedor=proveedor, no_factura='F-1',
        )
        ingresar_unidades(ingreso, ['A-1001', 'A-1002'])

        MovimientoVenta.objects.create(
            folio='ING-00002', articulo=cls.repuesto, cantidad=500,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.REPUESTOS,
            usuario=cls.admin,
        )
        # Un préstamo abierto y una devolución, para que las columnas de
        # estado de las tablas tengan las dos formas.
        prestamo = MovimientoVenta.objects.create(
            folio='SAL-00001', articulo=cls.repuesto, cantidad=1,
            tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
            usuario=cls.admin, cliente_nombre='Cliente X',
        )
        cls.prestamo_pk = prestamo.pk

        cls.taladro = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='TALADRO', bodega=cls.btec,
            precio=900,
        )
        dar_existencia(cls.taladro, 2, cls.admin)
        PrestamoActivo.objects.create(
            activo=cls.taladro, cantidad=1, solicitante='Ivan Leiva',
            fecha_salida=timezone.now(), estado_al_salir=Activo.Estado.BUEN_ESTADO,
            usuario=cls.admin,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def pantallas(self):
        return [
            ('catálogo de venta', reverse('catalogo_articulos')),
            ('ficha del producto', reverse('articulo_detalle', args=[self.equipo.pk])),
            ('kardex', reverse('kardex_articulo', args=[self.equipo.pk])),
            ('entradas y salidas', reverse('movimientos_ventas')),
            ('documento', reverse('documento_detalle', args=['ING-00001'])),
            ('catálogo de técnica', reverse('catalogo_activos')),
            ('ficha del activo', reverse('activo_detalle', args=[self.taladro.pk])),
            ('préstamos de herramienta', reverse('prestamos_tecnica')),
            ('resumen', reverse('resumen')),
            ('reporte de existencias', reverse('reporte_existencias')),
            ('reporte de alertas', reverse('reporte_alertas')),
            ('reporte de movimientos', reverse('reporte_movimientos')),
            ('reporte de técnica', reverse('reporte_tecnica')),
            ('reporte de préstamos', reverse('reporte_prestamos')),
        ]

    def test_ninguna_fila_tiene_mas_celdas_que_titulos(self):
        descuadres = []

        for nombre, url in self.pantallas():
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200, f'{nombre} no abrió')

            lector = LectorDeTablas()
            lector.feed(respuesta.content.decode())

            for numero, tabla in enumerate(lector.tablas, start=1):
                titulos = tabla['titulos']
                if not titulos:
                    continue        # una tabla de maquetación, sin encabezado
                for celdas in tabla['filas']:
                    if celdas != titulos:
                        descuadres.append(
                            f'{nombre}: la tabla {numero} tiene {titulos} '
                            f'títulos y una fila de {celdas} celdas'
                        )

        self.assertEqual(
            descuadres, [],
            'Hay filas que no cuadran con su encabezado: los datos salen '
            'corridos una columna. Suele ser una celda que quedó de más o de '
            'menos al agregar o quitar una columna.\n  ' + '\n  '.join(descuadres),
        )

    def test_la_prueba_agarraria_una_celda_de_mas(self):
        """
        Si el lector no contara bien, la prueba de arriba pasaría siempre.
        """
        lector = LectorDeTablas()
        lector.feed(
            '<table><thead><tr><th>A</th><th>B</th></tr></thead>'
            '<tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody></table>'
        )

        self.assertEqual(lector.tablas[0]['titulos'], 2)
        self.assertEqual(lector.tablas[0]['filas'], [3])

    def test_una_fila_vacia_estirada_no_cuenta_como_descuadre(self):
        """Las de "no hay nada que mostrar" son una celda con colspan."""
        lector = LectorDeTablas()
        lector.feed(
            '<table><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead>'
            '<tbody><tr><td colspan="3">Sin datos</td></tr></tbody></table>'
        )

        self.assertEqual(lector.tablas[0]['filas'], [3])
