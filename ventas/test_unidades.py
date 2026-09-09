"""
Control por unidad en Bodega 1 y 2 (Fase A).

Cuatro indicadores del mismo modelo son **cuatro unidades**: el mismo producto
en el catálogo —mismo precio, misma categoría, mismos umbrales— pero cada uno
con su número de serie. La empresa necesita saber cuál entró y cuál sigue en
bodega, no solo cuántos hay.

Antes el serial vivía en el producto con restricción de único, lo que solo
funciona si cada producto es una sola unidad física. Con 4 indicadores el
campo no daba: solo cabía un serial.

No todos los productos se controlan así. A los 500 conectores nadie les pone
serial, y por eso hay un interruptor por producto: los marcados van por
unidad, los demás siguen por cantidad exactamente como antes.

De qué proveedor entró y a qué cliente salió **no se guardan en la unidad**:
ya los trae el movimiento que la hizo entrar y el que la hará salir.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta, UnidadArticulo


class BaseUnidades(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.admin = Usuario.objects.create_user(
            username='admin_unidades', password='clave-de-prueba',
            rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            'codigo_interno': '', 'nombre_producto': 'INDICADOR SE7581P',
            'marca': 'BRECKNELL', 'modelo': 'SE7581P', 'capacidad': '',
            'bodega': self.bodega.pk, 'categoria': '', 'proveedor': '',
            'precio': '5500', 'imagen_url': '',
            'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2,
            'activo': 'on',
        }
        datos.update(extra)
        return datos

    def crear(self, **extra):
        respuesta = self.client.post(reverse('articulo_nuevo'), self.datos(**extra))
        self.assertEqual(respuesta.status_code, 302, f'no guardó: {respuesta.context["form"].errors if respuesta.context else ""}')
        return Articulo.objects.get(nombre_producto=self.datos(**extra)['nombre_producto'])


class ElInterruptorTests(BaseUnidades):
    def test_por_defecto_los_productos_no_llevan_serie(self):
        """Los repuestos son la mayoría: el caso común no debe pedir nada."""
        self.assertFalse(self.crear(nombre_producto='CONECTOR').lleva_serie)

    def test_se_puede_marcar(self):
        self.assertTrue(self.crear(lleva_serie='on').lleva_serie)

    def test_el_formulario_lo_ofrece(self):
        respuesta = self.client.get(reverse('articulo_nuevo'))

        self.assertContains(respuesta, 'lleva_serie')
        self.assertContains(respuesta, 'Lleva número de serie')


class CapturaAlCrearTests(BaseUnidades):
    def test_los_seriales_se_convierten_en_unidades(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001\nA-1002\nA-1003\nA-1004')

        self.assertEqual(articulo.unidades.count(), 4)
        self.assertEqual(
            sorted(articulo.unidades.values_list('numero_serie', flat=True)),
            ['A-1001', 'A-1002', 'A-1003', 'A-1004'],
        )

    def test_cada_unidad_cuenta_como_existencia(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001\nA-1002\nA-1003\nA-1004')

        self.assertEqual(articulo.stock_actual, 4)
        self.assertEqual(articulo.unidades_en_bodega, 4)

    def test_detras_de_las_unidades_queda_un_movimiento(self):
        """
        La regla del sistema: la existencia sale de los movimientos. Si las
        unidades se crearan sueltas, el catálogo y el historial dirían cosas
        distintas.
        """
        articulo = self.crear(lleva_serie='on', seriales='A-1001\nA-1002')

        movimiento = articulo.movimientos.get()
        self.assertEqual(movimiento.tipo_transaccion, MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL)
        self.assertEqual(movimiento.cantidad, 2)
        self.assertEqual(movimiento.usuario, self.admin)

    def test_las_unidades_apuntan_a_ese_movimiento(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001\nA-1002')

        movimiento = articulo.movimientos.get()
        for unidad in articulo.unidades.all():
            self.assertEqual(unidad.movimiento_ingreso, movimiento)

    def test_se_puede_crear_sin_seriales_y_agregarlos_despues_por_boleta(self):
        articulo = self.crear(lleva_serie='on', seriales='')

        self.assertEqual(articulo.unidades.count(), 0)
        self.assertEqual(articulo.stock_actual, 0)

    def test_las_lineas_vacias_se_ignoran(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001\n\n  \nA-1002\n')

        self.assertEqual(articulo.unidades.count(), 2)

    def test_un_producto_sin_marcar_no_acepta_seriales(self):
        respuesta = self.client.post(
            reverse('articulo_nuevo'), self.datos(seriales='A-1001'),
        )

        self.assertEqual(respuesta.status_code, 200, 'debió volver al formulario')
        self.assertEqual(UnidadArticulo.objects.count(), 0)


class SolamenteAlCrearTests(BaseUnidades):
    """
    Si se pudieran agregar seriales editando, el catálogo sería una puerta
    trasera para meter existencia sin boleta — lo mismo que se cerró en
    Bodega Técnica.
    """

    def test_al_editar_ya_no_se_piden(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001')

        respuesta = self.client.get(reverse('articulo_editar', args=[articulo.pk]))

        self.assertNotContains(respuesta, 'name="seriales"')

    def test_mandarlos_en_el_POST_de_edicion_no_crea_nada(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001')

        self.client.post(
            reverse('articulo_editar', args=[articulo.pk]),
            self.datos(lleva_serie='on', seriales='A-9999',
                       codigo_interno=articulo.codigo_interno),
        )

        self.assertEqual(articulo.unidades.count(), 1)
        self.assertFalse(UnidadArticulo.objects.filter(numero_serie='A-9999').exists())


class SerialesUnicosTests(BaseUnidades):
    """Un serial identifica un aparato físico: no se repite en el sistema."""

    def test_no_deja_repetirlo_en_la_misma_lista(self):
        respuesta = self.client.post(
            reverse('articulo_nuevo'),
            self.datos(lleva_serie='on', seriales='A-1001\nA-1001'),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'repetido')
        self.assertEqual(UnidadArticulo.objects.count(), 0)

    def test_no_deja_repetirlo_en_otro_producto(self):
        self.crear(lleva_serie='on', seriales='A-1001')

        respuesta = self.client.post(
            reverse('articulo_nuevo'),
            self.datos(nombre_producto='OTRO INDICADOR', modelo='X-9',
                       lleva_serie='on', seriales='A-1001'),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrado')

    def test_lo_detecta_sin_importar_mayusculas(self):
        self.crear(lleva_serie='on', seriales='a-1001')

        respuesta = self.client.post(
            reverse('articulo_nuevo'),
            self.datos(nombre_producto='OTRO', modelo='X-9',
                       lleva_serie='on', seriales='A-1001'),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrado')

    def test_la_base_tambien_lo_impide(self):
        """No solo el formulario: por si entra por otra puerta."""
        articulo = self.crear(lleva_serie='on', seriales='A-1001')
        movimiento = articulo.movimientos.get()

        with self.assertRaises(IntegrityError), transaction.atomic():
            UnidadArticulo.objects.create(
                articulo=articulo, numero_serie='A-1001', movimiento_ingreso=movimiento,
            )


class LaFichaListaLasUnidadesTests(BaseUnidades):
    def test_las_muestra_con_su_estado(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001\nA-1002')

        respuesta = self.client.get(reverse('articulo_detalle', args=[articulo.pk]))

        self.assertContains(respuesta, 'A-1001')
        self.assertContains(respuesta, 'A-1002')
        self.assertContains(respuesta, 'En bodega')

    def test_dice_con_que_entraron(self):
        articulo = self.crear(lleva_serie='on', seriales='A-1001')

        respuesta = self.client.get(reverse('articulo_detalle', args=[articulo.pk]))

        self.assertContains(respuesta, 'Carga inicial')

    def test_un_producto_sin_serie_no_pinta_la_lista(self):
        articulo = self.crear(nombre_producto='CONECTOR')

        respuesta = self.client.get(reverse('articulo_detalle', args=[articulo.pk]))

        self.assertNotContains(respuesta, 'N.º de serie</th>', html=False)


class ElBuscadorEncuentraPorSerialTests(BaseUnidades):
    def test_buscar_el_serial_lleva_al_producto(self):
        self.crear(lleva_serie='on', seriales='A-1001\nA-1002')

        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'A-1002'})

        nombres = [r['nombre'] for r in respuesta.json()['resultados']]
        self.assertIn('INDICADOR SE7581P', nombres)

    def test_no_lo_devuelve_repetido_por_cada_unidad(self):
        """El producto es uno solo aunque tenga cuatro seriales parecidos."""
        self.crear(lleva_serie='on', seriales='A-1001\nA-1002\nA-1003\nA-1004')

        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'A-100'})

        self.assertEqual(len(respuesta.json()['resultados']), 1)


class LoQueNoCambiaTests(BaseUnidades):
    """Los repuestos siguen funcionando exactamente como antes."""

    def test_un_producto_sin_serie_arranca_en_cero(self):
        self.assertEqual(self.crear(nombre_producto='CONECTOR').stock_actual, 0)

    def test_y_su_existencia_entra_por_un_ingreso(self):
        articulo = self.crear(nombre_producto='CONECTOR')

        MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.REPUESTOS,
            cantidad=500, usuario=self.admin, folio='A-1',
        )

        articulo.refresh_from_db()
        self.assertEqual(articulo.stock_actual, 500)
        self.assertEqual(articulo.unidades.count(), 0)

    def test_los_umbrales_siguen_calculandose_por_producto(self):
        """
        Es lo que se habría perdido con una fila por serial: con 4 unidades
        el producto está en nivel normal, no cuatro filas en crítico.
        """
        articulo = self.crear(lleva_serie='on', seriales='A-1\nA-2\nA-3\nA-4\nA-5\nA-6')

        self.assertEqual(articulo.stock_actual, 6)
        self.assertEqual(articulo.nivel_alerta, 'normal')
