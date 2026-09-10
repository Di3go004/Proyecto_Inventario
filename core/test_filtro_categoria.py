"""
Filtrar el catálogo por categoría, en las dos bodegas.

Los dos catálogos ya filtraban por proveedor, precio y estado, pero no por
categoría — que es justamente como está organizada la bodega en la práctica:
"enseñame las básculas", "enseñame la herramienta manual".

Las categorías van por módulo: las de venta no aparecen en el catálogo de
herramienta ni al revés. Y se puede pedir las que **no** tienen categoría,
que es lo que hace útil el conteo de "sin clasificar" del Resumen — sin esto
el sistema decía cuántos faltaban pero no daba forma de encontrarlos.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega, Categoria
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo


class BaseFiltroCategoria(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.btec = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_cat', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

        cls.basculas = Categoria.objects.create(
            nombre='ZZ Básculas de prueba', modulo=Categoria.Modulo.VENTAS,
        )
        cls.repuestos = Categoria.objects.create(
            nombre='ZZ Repuestos de prueba', modulo=Categoria.Modulo.VENTAS,
        )
        cls.manual = Categoria.objects.create(
            nombre='ZZ Herramienta manual de prueba', modulo=Categoria.Modulo.TECNICA,
        )
        cls.electrica = Categoria.objects.create(
            nombre='ZZ Herramienta eléctrica de prueba', modulo=Categoria.Modulo.TECNICA,
        )

        cls.bascula = Articulo.objects.create(
            nombre_producto='BASCULA DE PLATAFORMA', modelo='BP-1',
            bodega=cls.bodega, precio=1500, categoria=cls.basculas,
        )
        cls.conector = Articulo.objects.create(
            nombre_producto='CONECTOR RJ45', modelo='C-1',
            bodega=cls.bodega, precio=25, categoria=cls.repuestos,
        )
        cls.huerfano = Articulo.objects.create(
            nombre_producto='ARTICULO SIN CLASIFICAR', modelo='X-1',
            bodega=cls.bodega, precio=10,
        )

        cls.martillo = Activo.objects.create(
            codigo_interno='SE-M1', nombre_producto='MARTILLO', bodega=cls.btec,
            precio=80, categoria=cls.manual,
        )
        cls.taladro = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='TALADRO', bodega=cls.btec,
            precio=900, categoria=cls.electrica,
        )
        cls.activo_huerfano = Activo.objects.create(
            codigo_interno='SE-X1', nombre_producto='ACTIVO SIN CLASIFICAR',
            bodega=cls.btec, precio=10,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def nombres(self, respuesta, clave):
        return [p.nombre_producto for p in respuesta.context[clave]]


class CatalogoDeVentaTests(BaseFiltroCategoria):
    def pedir(self, **filtros):
        return self.client.get(reverse('catalogo_articulos'), filtros)

    def test_el_formulario_ofrece_el_filtro(self):
        respuesta = self.pedir()

        self.assertContains(respuesta, 'name="categoria"')
        self.assertContains(respuesta, 'ZZ Básculas de prueba')

    def test_filtra_por_categoria(self):
        respuesta = self.pedir(categoria=self.basculas.pk)

        self.assertEqual(self.nombres(respuesta, 'articulos'), ['BASCULA DE PLATAFORMA'])

    def test_pide_los_que_no_tienen_categoria(self):
        """El Resumen los cuenta; esta es la forma de ir a ponerles una."""
        respuesta = self.pedir(categoria='sin')

        self.assertEqual(self.nombres(respuesta, 'articulos'), ['ARTICULO SIN CLASIFICAR'])

    def test_sin_filtro_salen_todos(self):
        self.assertEqual(len(self.pedir().context['articulos']), 3)

    def test_se_combina_con_los_demas_filtros(self):
        """
        Los filtros se aplican uno sobre otro, no se reemplazan: es como
        funciona el resto de este catálogo.
        """
        respuesta = self.pedir(categoria=self.repuestos.pk, precio_max='50')
        self.assertEqual(self.nombres(respuesta, 'articulos'), ['CONECTOR RJ45'])

        vacio = self.pedir(categoria=self.basculas.pk, precio_max='50')
        self.assertEqual(self.nombres(vacio, 'articulos'), [])

    def test_cuenta_como_filtro_puesto(self):
        """El número junto a "Filtros" avisa que hay algo aplicado."""
        self.assertEqual(self.pedir(categoria=self.basculas.pk).context['filtros_activos'], 1)
        self.assertEqual(self.pedir().context['filtros_activos'], 0)

    def test_no_ofrece_las_categorias_de_herramienta(self):
        respuesta = self.pedir()

        ofrecidas = [c.nombre for c in respuesta.context['categorias']]
        self.assertIn('ZZ Básculas de prueba', ofrecidas)
        self.assertNotIn('ZZ Herramienta manual de prueba', ofrecidas)


class CatalogoDeTecnicaTests(BaseFiltroCategoria):
    def pedir(self, **filtros):
        return self.client.get(reverse('catalogo_activos'), filtros)

    def test_el_formulario_ofrece_el_filtro(self):
        respuesta = self.pedir()

        self.assertContains(respuesta, 'name="categoria"')
        self.assertContains(respuesta, 'ZZ Herramienta manual de prueba')

    def test_filtra_por_categoria(self):
        respuesta = self.pedir(categoria=self.manual.pk)

        self.assertEqual(self.nombres(respuesta, 'activos'), ['MARTILLO'])

    def test_pide_los_que_no_tienen_categoria(self):
        respuesta = self.pedir(categoria='sin')

        self.assertEqual(self.nombres(respuesta, 'activos'), ['ACTIVO SIN CLASIFICAR'])

    def test_se_combina_con_el_filtro_de_precio(self):
        respuesta = self.pedir(categoria=self.electrica.pk, precio_min='500')
        self.assertEqual(self.nombres(respuesta, 'activos'), ['TALADRO'])

        vacio = self.pedir(categoria=self.manual.pk, precio_min='500')
        self.assertEqual(self.nombres(vacio, 'activos'), [])

    def test_cuenta_como_filtro_puesto(self):
        self.assertEqual(self.pedir(categoria=self.manual.pk).context['filtros_activos'], 1)

    def test_no_ofrece_las_categorias_de_venta(self):
        respuesta = self.pedir()

        ofrecidas = [c.nombre for c in respuesta.context['categorias']]
        self.assertIn('ZZ Herramienta manual de prueba', ofrecidas)
        self.assertNotIn('ZZ Básculas de prueba', ofrecidas)
