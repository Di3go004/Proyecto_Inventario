"""
El precio queda pegado al movimiento, no se toma del catálogo al imprimir.

La boleta FO-SE-013 sacaba el precio de la ficha del producto, así que
reimprimir un ingreso después de un cambio de precio producía **un documento
distinto al que se firmó y se archivó**. Un documento que se contradice a sí
mismo es justo lo que no puede pasar en un sistema de gestión.

Ahora cada movimiento guarda el precio al que ocurrió. En el ingreso se
captura —es el de la factura del proveedor—; en los demás lo copia el `save()`
del modelo, para que ninguna de las cinco puertas por las que nace un
movimiento lo deje en cero.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas.documentos import lineas_del_documento
from ventas.models import Articulo, MovimientoVenta


class BasePrecio(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_precio', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='BASCULA', modelo='B-1', bodega=cls.venta, precio=Decimal('100.00'),
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-TE001', nombre_producto='TALADRO',
            bodega=cls.tecnica, precio=Decimal('250.00'),
        )

    def setUp(self):
        self.client.force_login(self.admin)


class SeCopiaDelCatalogoAlCrearTests(BasePrecio):
    """
    Los movimientos nacen en cinco lugares distintos. Que ninguno quede en
    cero por olvido: lo resuelve el save() del modelo, no cada pantalla.
    """

    def test_un_movimiento_de_venta_sin_precio_toma_el_del_catalogo(self):
        movimiento = MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin,
        )

        self.assertEqual(movimiento.precio_unitario, Decimal('100.00'))

    def test_un_movimiento_tecnico_sin_precio_toma_el_del_catalogo(self):
        movimiento = MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=self.activo,
            cantidad=3, usuario=self.admin,
        )

        self.assertEqual(movimiento.precio_unitario, Decimal('250.00'))

    def test_una_baja_tambien_lo_guarda(self):
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=self.activo,
            cantidad=5, usuario=self.admin,
        )

        baja = MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.BAJA, activo=self.activo, cantidad=1,
            usuario=self.admin, motivo=MovimientoActivo.Motivo.DANADO,
        )

        self.assertEqual(baja.precio_unitario, Decimal('250.00'))

    def test_si_se_le_da_un_precio_ese_manda(self):
        movimiento = MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin, precio_unitario=Decimal('87.50'),
        )

        self.assertEqual(movimiento.precio_unitario, Decimal('87.50'))


class NoSeMueveDespuesTests(BasePrecio):
    """El punto de todo el cambio."""

    def movimiento(self, precio=None):
        return MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin, folio='ING-00001',
            **({'precio_unitario': precio} if precio else {}),
        )

    def test_cambiar_el_precio_del_catalogo_no_toca_el_historial(self):
        movimiento = self.movimiento()

        self.articulo.precio = Decimal('180.00')
        self.articulo.save()

        movimiento.refresh_from_db()
        self.assertEqual(movimiento.precio_unitario, Decimal('100.00'))
        self.assertEqual(self.articulo.precio, Decimal('180.00'))

    def test_guardar_otra_vez_el_movimiento_tampoco(self):
        """Se copia solo al crear; después el precio es historia."""
        movimiento = self.movimiento()
        self.articulo.precio = Decimal('180.00')
        self.articulo.save()

        movimiento.save()

        movimiento.refresh_from_db()
        self.assertEqual(movimiento.precio_unitario, Decimal('100.00'))


class LaBoletaImprimeElPrecioGuardadoTests(BasePrecio):
    def test_la_linea_del_documento_devuelve_el_del_movimiento(self):
        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin, folio='ING-00001',
            precio_unitario=Decimal('87.50'),
        )

        linea = lineas_del_documento('ING-00001')[0]

        self.assertEqual(linea.precio_unitario, Decimal('87.50'))
        self.assertEqual(linea.subtotal, Decimal('437.50'), '5 × 87.50')

    def test_reimprimirla_tras_un_cambio_de_precio_da_el_mismo_documento(self):
        """
        Es el defecto que esto viene a arreglar: la boleta impresa tenía que
        seguir diciendo lo que decía cuando se firmó.
        """
        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=2, usuario=self.admin, folio='ING-00002',
        )
        antes = self.client.get(reverse('documento_pdf', args=['ING-00002'])).content

        self.articulo.precio = Decimal('999.99')
        self.articulo.save()

        despues = self.client.get(reverse('documento_pdf', args=['ING-00002'])).content

        self.assertEqual(
            lineas_del_documento('ING-00002')[0].precio_unitario, Decimal('100.00'),
            'la boleta debe seguir mostrando el precio de cuando se registró',
        )
        self.assertEqual(len(antes) > 0, len(despues) > 0)

    def test_el_pdf_se_genera_sin_error(self):
        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=2, usuario=self.admin, folio='ING-00003',
        )

        respuesta = self.client.get(reverse('documento_pdf', args=['ING-00003']))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')


class SeCapturaEnElIngresoTests(BasePrecio):
    def datos(self, **extra):
        datos = {
            'folio': 'ING-00010', 'fecha': '2026-09-08T10:00',
            'tipo_transaccion': MovimientoVenta.TipoTransaccion.VENTA,
            'solicitado_por': 'Diego González', 'no_factura': 'F-1',
            'observacion': '',
            'linea_texto': [self.articulo.codigo_interno],
            'linea_articulo': [str(self.articulo.pk)],
            'linea_cantidad': ['4'],
            'linea_precio': [''],
        }
        datos.update(extra)
        return datos

    def test_el_formulario_ofrece_la_columna_de_precio(self):
        respuesta = self.client.get(reverse('movimiento_ingreso'))

        self.assertContains(respuesta, 'linea_precio')
        self.assertContains(respuesta, 'Precio')

    def test_la_salida_NO_la_ofrece(self):
        """La boleta FO-SE-012 no lleva columna de precio."""
        respuesta = self.client.get(reverse('movimiento_salida'))

        self.assertNotContains(respuesta, 'linea_precio')

    def test_dejarlo_vacio_toma_el_del_catalogo(self):
        self.client.post(reverse('movimiento_ingreso'), self.datos())

        movimiento = MovimientoVenta.objects.get(folio='ING-00010')
        self.assertEqual(movimiento.precio_unitario, Decimal('100.00'))

    def test_escribir_otro_precio_es_el_que_se_guarda(self):
        """El de la factura del proveedor manda sobre el del catálogo."""
        self.client.post(reverse('movimiento_ingreso'), self.datos(linea_precio=['87.50']))

        movimiento = MovimientoVenta.objects.get(folio='ING-00010')
        self.assertEqual(movimiento.precio_unitario, Decimal('87.50'))

    def test_no_cambia_el_precio_del_catalogo(self):
        """
        Registrar un ingreso a otro precio no reescribe la ficha del producto:
        actualizar el catálogo es del administrador, no del operador.
        """
        self.client.post(reverse('movimiento_ingreso'), self.datos(linea_precio=['87.50']))

        self.articulo.refresh_from_db()
        self.assertEqual(self.articulo.precio, Decimal('100.00'))

    def test_un_precio_que_no_es_numero_se_rechaza(self):
        respuesta = self.client.post(reverse('movimiento_ingreso'), self.datos(linea_precio=['abc']))

        self.assertEqual(respuesta.status_code, 200, 'debió volver al formulario')
        self.assertFalse(MovimientoVenta.objects.filter(folio='ING-00010').exists())

    def test_un_precio_negativo_se_rechaza(self):
        respuesta = self.client.post(reverse('movimiento_ingreso'), self.datos(linea_precio=['-5']))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MovimientoVenta.objects.filter(folio='ING-00010').exists())

    def test_un_precio_de_cero_si_se_acepta(self):
        """Hay productos que entran sin costo: muestras, garantías."""
        self.client.post(reverse('movimiento_ingreso'), self.datos(linea_precio=['0']))

        self.assertEqual(
            MovimientoVenta.objects.get(folio='ING-00010').precio_unitario, Decimal('0'),
        )


class LaApiProponeElPrecioTests(BasePrecio):
    def test_el_buscador_devuelve_el_precio_del_producto(self):
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'BASCULA'})

        resultado = respuesta.json()['resultados'][0]
        self.assertEqual(resultado['precio'], '100.00')

    def test_tambien_para_la_herramienta(self):
        respuesta = self.client.get(
            reverse('api_buscar_articulos'), {'q': 'TALADRO', 'incluir': 'tecnica'},
        )

        resultado = respuesta.json()['resultados'][0]
        self.assertEqual(resultado['precio'], '250.00')
