"""
Pruebas del comando `limpiar_catalogo`.

Es el comando que se corre una sola vez, el día que se pasa de las pruebas a
los datos reales (ver PUESTA_EN_MARCHA.md), y es irreversible. Por eso se
prueban las tres cosas que más caro salen si fallan justo ese día: que sin
--si-estoy-seguro no borre nada, que no se lleve por delante proveedores,
categorías ni usuarios, y que el correlativo de folios vuelva a arrancar en
ING-00001 —si siguiera en el número de las pruebas, las boletas reales
saldrían con folios que no cuadran con el talonario de papel.
"""

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Bodega, Categoria, Proveedor
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class LimpiarCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.proveedor = Proveedor.objects.create(nombre='BRECKNELL')
        cls.categoria = Categoria.objects.create(nombre='Indicadores')
        cls.usuario = Usuario.objects.create_user(
            username='admin_limpieza', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def sembrar_ventas(self, cuantos_folios=3):
        articulo = Articulo.objects.create(
            nombre_producto='Báscula de prueba', modelo='BP-1', bodega=self.bodega,
            proveedor=self.proveedor, categoria=self.categoria,
        )
        for _ in range(cuantos_folios):
            MovimientoVenta.objects.create(
                folio=MovimientoVenta.siguiente_folio('ingreso'), articulo=articulo, cantidad=1,
                tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
                tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
                fecha=timezone.now(), usuario=self.usuario,
            )
        return articulo

    def test_sin_la_confirmacion_no_borra_nada(self):
        self.sembrar_ventas()

        call_command('limpiar_catalogo', que='ventas', verbosity=0)

        self.assertEqual(Articulo.objects.count(), 1)
        self.assertEqual(MovimientoVenta.objects.count(), 3)

    def test_borra_articulos_y_movimientos(self):
        self.sembrar_ventas()

        call_command('limpiar_catalogo', que='ventas', si_estoy_seguro=True, verbosity=0)

        self.assertEqual(Articulo.objects.count(), 0)
        self.assertEqual(MovimientoVenta.objects.count(), 0)

    def test_el_correlativo_de_folios_vuelve_a_empezar(self):
        """
        El folio se calcula del último que exista. Si tras limpiar siguiera en
        ING-00004, la primera boleta real no arrancaría en 1 como el talonario.
        """
        self.sembrar_ventas()
        self.assertEqual(MovimientoVenta.siguiente_folio('ingreso'), 'ING-00004')

        call_command('limpiar_catalogo', que='ventas', si_estoy_seguro=True, verbosity=0)

        self.assertEqual(MovimientoVenta.siguiente_folio('ingreso'), 'ING-00001')

    def test_no_toca_proveedores_categorias_bodegas_ni_usuarios(self):
        """Esos se configuran una vez; volver a capturarlos sería el castigo."""
        self.sembrar_ventas()

        call_command('limpiar_catalogo', que='todo', si_estoy_seguro=True, verbosity=0)

        self.assertTrue(Proveedor.objects.filter(pk=self.proveedor.pk).exists())
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())
        self.assertTrue(Bodega.objects.filter(pk=self.bodega.pk).exists())
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())

    def test_limpiar_ventas_no_toca_la_bodega_tecnica(self):
        self.sembrar_ventas()
        Activo.objects.create(
            nombre_producto='Rotomartillo', modelo='RM-1', bodega=self.tecnica,
        )

        call_command('limpiar_catalogo', que='ventas', si_estoy_seguro=True, verbosity=0)

        self.assertEqual(Articulo.objects.count(), 0)
        self.assertEqual(Activo.objects.count(), 1, 'son dos inventarios distintos')
