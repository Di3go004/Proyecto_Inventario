"""
Pruebas de la pantalla de categorías (RF-02/RF-03).

Las categorías existían en el modelo desde el principio, pero no había
ninguna creada ni forma de crearlas fuera del panel /admin/ —que se quitó de
la navegación—, así que el desplegable del catálogo salía vacío y parecía
que la función no servía.
"""

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Bodega, Categoria
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo


class BaseCategorias(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_cat', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='op_cat', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)


class SembradoInicialTests(TestCase):
    """
    La migración de datos tiene que dejar categorías listas: si el sistema
    arranca con la tabla vacía, el desplegable del catálogo sale sin nada.
    """

    def test_el_sistema_arranca_con_categorias_en_las_dos_bodegas(self):
        self.assertGreater(Categoria.objects.filter(modulo=Categoria.Modulo.VENTAS).count(), 0)
        self.assertGreater(Categoria.objects.filter(modulo=Categoria.Modulo.TECNICA).count(), 0)

    def test_limpiar_catalogo_no_se_lleva_las_categorias(self):
        """Se vuelve a importar el Excel, no a reconfigurar el sistema."""
        cuantas = Categoria.objects.count()

        call_command('limpiar_catalogo', que='todo', si_estoy_seguro=True, verbosity=0)

        self.assertEqual(Categoria.objects.count(), cuantas)


class PermisosCategoriasTests(BaseCategorias):
    def test_solo_el_administrador_entra(self):
        self.client.force_login(self.operador)
        for nombre in ('lista_categorias', 'categoria_nueva'):
            respuesta = self.client.get(reverse(nombre))
            self.assertIn(respuesta.status_code, (302, 403), f'{nombre} quedó abierta al operador')

    def test_el_administrador_ve_la_lista(self):
        self.assertEqual(self.client.get(reverse('lista_categorias')).status_code, 200)


class CrearYEditarTests(BaseCategorias):
    def test_crea_una_categoria(self):
        respuesta = self.client.post(reverse('categoria_nueva'), {
            'nombre': 'Prensas hidráulicas', 'modulo': Categoria.Modulo.VENTAS,
        })

        self.assertRedirects(respuesta, reverse('lista_categorias'))
        self.assertTrue(Categoria.objects.filter(nombre='Prensas hidráulicas').exists())

    def test_no_permite_dos_iguales_en_la_misma_bodega(self):
        """
        El índice único distingue mayúsculas, así que sin normalizar entrarían
        "Poleas" y "poleas" como dos categorías distintas.
        """
        Categoria.objects.create(nombre='Poleas', modulo=Categoria.Modulo.VENTAS)

        respuesta = self.client.post(reverse('categoria_nueva'), {
            'nombre': '  poleas  ', 'modulo': Categoria.Modulo.VENTAS,
        })

        self.assertEqual(respuesta.status_code, 200, 'debe volver al formulario con el error')
        self.assertEqual(Categoria.objects.filter(nombre__iexact='poleas').count(), 1)

    def test_junta_los_espacios_de_en_medio(self):
        """
        Pegar el nombre desde el Excel arrastra espacios dobles. Sin juntarlos,
        "Celdas  de  carga" entra como otra categoría y en la lista se ve
        idéntica a la que ya existía.
        """
        self.client.post(reverse('categoria_nueva'), {
            'nombre': 'Celdas  de   carga  especiales', 'modulo': Categoria.Modulo.VENTAS,
        })

        self.assertTrue(Categoria.objects.filter(nombre='Celdas de carga especiales').exists())

    def test_el_mismo_nombre_si_puede_existir_en_la_otra_bodega(self):
        Categoria.objects.create(nombre='Herramienta', modulo=Categoria.Modulo.VENTAS)

        self.client.post(reverse('categoria_nueva'), {
            'nombre': 'Herramienta', 'modulo': Categoria.Modulo.TECNICA,
        })

        self.assertEqual(Categoria.objects.filter(nombre='Herramienta').count(), 2)

    def test_al_editar_no_se_puede_cambiar_de_bodega(self):
        """
        Moverla dejaría a sus artículos apuntando a una categoría que su
        propio campo ya no admite (el FK filtra por módulo).
        """
        categoria = Categoria.objects.create(nombre='Poleas', modulo=Categoria.Modulo.VENTAS)

        self.client.post(reverse('categoria_editar', args=[categoria.pk]), {
            'nombre': 'Poleas', 'modulo': Categoria.Modulo.TECNICA,
        })

        categoria.refresh_from_db()
        self.assertEqual(categoria.modulo, Categoria.Modulo.VENTAS)

    def test_editar_el_nombre_no_desclasifica_los_productos(self):
        categoria = Categoria.objects.create(nombre='Poleas', modulo=Categoria.Modulo.VENTAS)
        articulo = Articulo.objects.create(
            nombre_producto='Polea 3t', modelo='P-3', bodega=self.bodega, categoria=categoria,
        )

        self.client.post(reverse('categoria_editar', args=[categoria.pk]), {'nombre': 'Poleas y ganchos'})

        articulo.refresh_from_db()
        self.assertEqual(articulo.categoria_id, categoria.pk)
        self.assertEqual(articulo.categoria.nombre, 'Poleas y ganchos')


class EliminarCategoriaTests(BaseCategorias):
    def test_elimina_una_que_nadie_usa(self):
        categoria = Categoria.objects.create(nombre='Sin usar', modulo=Categoria.Modulo.VENTAS)

        self.client.post(reverse('categoria_eliminar', args=[categoria.pk]))

        self.assertFalse(Categoria.objects.filter(pk=categoria.pk).exists())

    def test_eliminar_una_en_uso_no_borra_los_productos(self):
        """SET_NULL: el producto se queda, sin categoría. Nunca se pierde stock."""
        categoria = Categoria.objects.create(nombre='En uso', modulo=Categoria.Modulo.VENTAS)
        articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=self.bodega, categoria=categoria,
        )

        self.client.post(reverse('categoria_eliminar', args=[categoria.pk]))

        articulo.refresh_from_db()
        self.assertIsNone(articulo.categoria)
        self.assertTrue(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_avisa_cuantos_productos_quedarian_sin_categoria(self):
        categoria = Categoria.objects.create(nombre='En uso', modulo=Categoria.Modulo.VENTAS)
        for i in range(3):
            Articulo.objects.create(
                nombre_producto=f'Báscula {i}', modelo=f'B-{i}',
                bodega=self.bodega, categoria=categoria,
            )

        respuesta = self.client.get(reverse('categoria_eliminar', args=[categoria.pk]))

        self.assertContains(respuesta, '3')
        self.assertContains(respuesta, 'sin categoría')


class DesplegableDelCatalogoTests(BaseCategorias):
    """
    Cada bodega solo debe ofrecer sus propias categorías: una báscula no se
    puede clasificar como "Herramienta eléctrica" ni al revés.
    """

    def test_el_formulario_de_articulo_solo_ofrece_las_de_ventas(self):
        from ventas.forms import ArticuloForm

        opciones = ArticuloForm().fields['categoria'].queryset

        self.assertGreater(opciones.count(), 0, 'el desplegable no puede salir vacío')
        self.assertFalse(opciones.filter(modulo=Categoria.Modulo.TECNICA).exists())

    def test_el_formulario_de_activo_solo_ofrece_las_de_tecnica(self):
        from tecnica.forms import ActivoForm

        opciones = ActivoForm().fields['categoria'].queryset

        self.assertGreater(opciones.count(), 0)
        self.assertFalse(opciones.filter(modulo=Categoria.Modulo.VENTAS).exists())

    def test_la_opcion_no_repite_la_bodega_en_cada_renglon(self):
        """
        El __str__ de Categoria dice "Balanzas (Ventas)". En el desplegable,
        que ya está filtrado a una sola bodega, ese sufijo sale idéntico en
        todas las opciones y solo estorba.
        """
        from ventas.forms import ArticuloForm

        campo = ArticuloForm().fields['categoria']
        etiquetas = [campo.label_from_instance(c) for c in campo.queryset]

        self.assertIn('Balanzas', etiquetas)
        self.assertFalse([e for e in etiquetas if '(' in e], f'sobra el sufijo: {etiquetas}')

    def test_un_activo_guarda_su_categoria(self):
        categoria = Categoria.objects.get(nombre='Herramienta manual', modulo=Categoria.Modulo.TECNICA)
        activo = Activo.objects.create(
            nombre_producto='Llave de tubo', modelo='LT-1',
            bodega=self.tecnica, categoria=categoria,
        )

        activo.refresh_from_db()
        self.assertEqual(activo.categoria.nombre, 'Herramienta manual')
