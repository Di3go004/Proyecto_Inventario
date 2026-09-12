"""
La descripción de un activo de Bodega Técnica.

Nació por los kits. Un `KIT CHANGAN ROJO` no dice en su nombre qué trae
adentro, y lo que la empresa necesita saber es qué objeto, marca y modelo
lleva cada pieza. Son varios datos por registro, así que va un texto: armar
el kit y sus piezas como registros aparte sería lo correcto de libro, pero
sobreingeniería para algo que nadie va a filtrar ni contar.

Queda libre a propósito, sin formato impuesto: según el producto se usa para
otra cosa.

Lo que la vuelve útil de verdad es que **el buscador la cubre**. Escribir
"STANLEY" encuentra los kits que traen algo de esa marca — una pregunta que
hoy no se puede contestar sin abrir los 23 kits a mano. Un texto que se
escribe y no se puede recuperar no sirve de nada.

No se muestra en la tabla del catálogo: un párrafo por fila la volvería
ilegible. Vive en la ficha.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo
from usuarios.models import Usuario


class BaseDescripcion(TestCase):
    CONTENIDO = (
        '1 llave ajustable TRUPER 8"\n'
        '2 desarmadores STANLEY PH2\n'
        '1 alicate TRUPER'
    )

    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(
            nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA,
        )
        cls.admin = Usuario.objects.create_user(
            username='admin_desc', password='clave-de-prueba',
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.kit = Activo.objects.create(
            codigo_interno='SE-KIT-1', nombre_producto='KIT CHANGAN ROJO',
            bodega=cls.bodega, precio=500, descripcion=cls.CONTENIDO,
        )
        cls.taladro = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='TALADRO',
            bodega=cls.bodega, precio=900,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            'codigo_interno': 'SE-NUEVO-1', 'nombre_producto': 'KIT NUEVO',
            'marca': '', 'modelo': '', 'descripcion': '',
            'categoria': '', 'bodega': self.bodega.pk, 'proveedor': '',
            'precio': '100', 'imagen_url': '', 'estado': Activo.Estado.BUEN_ESTADO,
            'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2,
        }
        datos.update(extra)
        return datos


class SeGuardaYSeLeeTests(BaseDescripcion):
    def test_se_captura_al_crear_el_activo(self):
        respuesta = self.client.post(
            reverse('activo_nuevo'), self.datos(descripcion=self.CONTENIDO),
        )

        self.assertEqual(respuesta.status_code, 302)
        creado = Activo.objects.get(codigo_interno='SE-NUEVO-1')
        self.assertEqual(creado.descripcion, self.CONTENIDO)

    def test_es_opcional(self):
        """La mayoría de los activos no la necesitan."""
        respuesta = self.client.post(reverse('activo_nuevo'), self.datos())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Activo.objects.get(codigo_interno='SE-NUEVO-1').descripcion, '')

    def test_se_puede_corregir_editando(self):
        """
        A diferencia de los seriales de Bodega 1 y 2, esta sí se edita: es un
        dato del producto, no existencia con respaldo documental.
        """
        self.client.post(
            reverse('activo_editar', args=[self.kit.pk]),
            self.datos(codigo_interno=self.kit.codigo_interno,
                       nombre_producto=self.kit.nombre_producto,
                       descripcion='1 llave ajustable TRUPER 10"'),
        )

        self.kit.refresh_from_db()
        self.assertEqual(self.kit.descripcion, '1 llave ajustable TRUPER 10"')

    def test_el_formulario_la_ofrece_con_su_ejemplo(self):
        respuesta = self.client.get(reverse('activo_nuevo'))

        self.assertContains(respuesta, 'name="descripcion"')
        self.assertContains(respuesta, 'Descripciones extra del producto')

    def test_los_renglones_se_respetan_en_la_ficha(self):
        """
        El contenido de un kit es una lista. Sin esto los tres renglones
        saldrían pegados en una sola línea.
        """
        respuesta = self.client.get(reverse('activo_detalle', args=[self.kit.pk]))

        self.assertContains(respuesta, '<br>')
        self.assertContains(respuesta, 'STANLEY PH2')


class DondeSeVeYDondeNoTests(BaseDescripcion):
    def test_la_ficha_la_muestra(self):
        respuesta = self.client.get(reverse('activo_detalle', args=[self.kit.pk]))

        self.assertContains(respuesta, 'Descripción')
        self.assertContains(respuesta, 'llave ajustable TRUPER')

    def test_un_activo_sin_descripcion_no_pinta_el_rótulo(self):
        """Un rótulo con una raya al lado no informa nada."""
        respuesta = self.client.get(reverse('activo_detalle', args=[self.taladro.pk]))

        self.assertNotContains(respuesta, '<dt>Descripción</dt>', html=False)

    def test_la_tabla_del_catalogo_no_la_trae(self):
        """
        Un párrafo por fila volvería la tabla ilegible. La descripción vive en
        la ficha, a un clic.
        """
        respuesta = self.client.get(reverse('catalogo_activos'))

        self.assertContains(respuesta, 'KIT CHANGAN ROJO')
        self.assertNotContains(respuesta, 'desarmadores STANLEY')


class ElBuscadorLaCubreTests(BaseDescripcion):
    """
    Lo que vuelve consultable el campo. Sin esto se podría escribir el
    contenido de un kit y no habría forma de recuperarlo.
    """

    def encontrados(self, texto):
        respuesta = self.client.get(reverse('catalogo_activos'), {'q': texto})
        return [a.codigo_interno for a in respuesta.context['activos']]

    def test_buscar_una_marca_de_adentro_encuentra_el_kit(self):
        self.assertEqual(self.encontrados('STANLEY'), ['SE-KIT-1'])

    def test_buscar_una_pieza_tambien(self):
        self.assertEqual(self.encontrados('alicate'), ['SE-KIT-1'])

    def test_no_distingue_mayusculas(self):
        self.assertEqual(self.encontrados('stanley'), ['SE-KIT-1'])

    def test_lo_que_no_esta_no_aparece(self):
        self.assertEqual(self.encontrados('DEWALT'), [])

    def test_sigue_encontrando_por_codigo_y_nombre(self):
        """El buscador ganó un campo, no cambió los que ya tenía."""
        self.assertEqual(self.encontrados('SE-T1'), ['SE-T1'])
        self.assertEqual(self.encontrados('TALADRO'), ['SE-T1'])

    def test_se_combina_con_los_filtros(self):
        respuesta = self.client.get(reverse('catalogo_activos'), {
            'q': 'STANLEY', 'precio_min': '1000',
        })

        self.assertEqual([a.codigo_interno for a in respuesta.context['activos']], [])


class LoQueNoCambioTests(BaseDescripcion):
    def test_bodega_1_y_2_no_tiene_el_campo(self):
        """
        Se pidió solo para Bodega Técnica. Los kits son de la herramienta; en
        venta el catálogo ya tiene capacidad para el dato que se repite.
        """
        from ventas.models import Articulo

        self.assertFalse(hasattr(Articulo, 'descripcion'))

    def test_los_252_activos_de_produccion_quedarian_vacios(self):
        """La migración agrega el campo en blanco, sin tocar nada."""
        self.assertEqual(self.taladro.descripcion, '')
