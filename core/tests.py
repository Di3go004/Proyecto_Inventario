"""
Pruebas de la paginación de los catálogos.

Importa sobre todo que los filtros no se pierdan al cambiar de página: es
el error clásico de las tablas paginadas y aquí sería muy molesto, porque
los catálogos tienen 200+ registros.
"""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Bodega
from core.paginacion import POR_PAGINA
from tecnica.ayuda_pruebas import dar_existencia
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo


class PaginacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega1 = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.bodega2 = Bodega.objects.create(nombre='Bodega 2', tipo=Bodega.Tipo.VENTA)
        cls.bodega_tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_pag', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

        # 30 artículos: más de una página (25 por página), y repartidos entre
        # las dos bodegas para poder probar filtro + paginación juntos.
        for i in range(30):
            Articulo.objects.create(
                nombre_producto=f'Articulo {i:03d}',
                modelo=f'MOD-{i:03d}',
                bodega=cls.bodega1 if i < 20 else cls.bodega2,
            )
        for i in range(30):
            activo = Activo.objects.create(
                codigo_interno=f'SE-ET{i:03d}',
                nombre_producto=f'Herramienta {i:03d}',
                bodega=cls.bodega_tecnica,
            )
            # Con existencia 0 estarían agotadas y el filtro por estado las
            # dejaría fuera, que es justo lo que debe hacer.
            dar_existencia(activo, 1, cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_la_primera_pagina_trae_el_tope_por_pagina(self):
        respuesta = self.client.get(reverse('catalogo_articulos'))
        self.assertEqual(len(respuesta.context['articulos']), POR_PAGINA)
        self.assertEqual(respuesta.context['pagina'].paginator.count, 30)

    def test_la_segunda_pagina_trae_el_resto(self):
        respuesta = self.client.get(reverse('catalogo_articulos'), {'pagina': 2})
        self.assertEqual(len(respuesta.context['articulos']), 5)
        self.assertEqual(respuesta.context['pagina'].number, 2)

    def test_las_paginas_no_repiten_registros(self):
        p1 = self.client.get(reverse('catalogo_articulos'), {'pagina': 1}).context['articulos']
        p2 = self.client.get(reverse('catalogo_articulos'), {'pagina': 2}).context['articulos']
        codigos_p1 = {a.codigo_interno for a in p1}
        codigos_p2 = {a.codigo_interno for a in p2}
        self.assertEqual(len(codigos_p1 & codigos_p2), 0, 'una página repite artículos de la otra')

    def test_una_pagina_que_no_existe_devuelve_la_ultima(self):
        """Alguien puede editar la URL, o quedar en una página que ya no
        existe después de filtrar. No debe romperse."""
        respuesta = self.client.get(reverse('catalogo_articulos'), {'pagina': 999})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['pagina'].number, respuesta.context['pagina'].paginator.num_pages)

    def test_una_pagina_que_no_es_numero_devuelve_la_primera(self):
        respuesta = self.client.get(reverse('catalogo_articulos'), {'pagina': 'abc'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['pagina'].number, 1)

    def test_el_filtro_se_respeta_al_cambiar_de_pagina(self):
        """Lo importante: paginar dentro del subconjunto filtrado, no del total."""
        respuesta = self.client.get(reverse('catalogo_articulos'), {'bodega': self.bodega2.id})
        self.assertEqual(respuesta.context['pagina'].paginator.count, 10)
        for articulo in respuesta.context['articulos']:
            self.assertEqual(articulo.bodega, self.bodega2)

    def test_los_enlaces_de_paginacion_conservan_los_filtros(self):
        # Se filtra por "solo activos" (los 30) para que de verdad haya más
        # de una página: con un filtro que deje 25 o menos, los controles de
        # paginación no se dibujan y no habría enlace que revisar.
        respuesta = self.client.get(reverse('catalogo_articulos'), {'activo': 'si'})
        contenido = respuesta.content.decode()

        self.assertGreater(respuesta.context['pagina'].paginator.num_pages, 1)
        self.assertIn('activo=si', contenido, 'el enlace de paginación perdió el filtro')
        self.assertIn('pagina=2', contenido)

    def test_el_contador_de_filtros_activos(self):
        sin_filtros = self.client.get(reverse('catalogo_articulos'))
        self.assertEqual(sin_filtros.context['filtros_activos'], 0)

        con_filtros = self.client.get(
            reverse('catalogo_articulos'), {'bodega': self.bodega1.id, 'activo': 'si'},
        )
        self.assertEqual(con_filtros.context['filtros_activos'], 2)

    def test_la_busqueda_por_texto_no_cuenta_como_filtro(self):
        """El buscador siempre está a la vista, así que no necesita avisar."""
        respuesta = self.client.get(reverse('catalogo_articulos'), {'q': 'Articulo'})
        self.assertEqual(respuesta.context['filtros_activos'], 0)

    def test_bodega_tecnica_tambien_pagina(self):
        respuesta = self.client.get(reverse('catalogo_activos'))
        self.assertEqual(len(respuesta.context['activos']), POR_PAGINA)
        self.assertEqual(respuesta.context['pagina'].paginator.count, 30)

    def test_bodega_tecnica_respeta_filtro_al_paginar(self):
        Activo.objects.filter(codigo_interno='SE-ET000').update(estado=Activo.Estado.MAL_ESTADO)
        respuesta = self.client.get(reverse('catalogo_activos'), {'estado': 'mal_estado'})
        self.assertEqual(respuesta.context['pagina'].paginator.count, 1)
        self.assertEqual(respuesta.context['filtros_activos'], 1)


class ComentariosDePlantillaTests(SimpleTestCase):
    """
    Django solo entiende {# ... #} cuando abre y cierra en la MISMA línea.
    Si se parte en dos, el comentario deja de serlo y se imprime como texto
    visible en medio de la página. Ya pasó dos veces (una en los catálogos y
    otra en el historial de movimientos), así que ahora se revisa solo.
    """

    def test_ningun_comentario_corto_queda_abierto(self):
        raiz = Path(settings.BASE_DIR) / 'templates'
        abiertos = []
        for plantilla in sorted(raiz.rglob('*.html')):
            for numero, linea in enumerate(plantilla.read_text(encoding='utf-8').splitlines(), 1):
                if '{#' in linea and '#}' not in linea:
                    abiertos.append(f'{plantilla.relative_to(raiz)}:{numero}')

        self.assertEqual(
            abiertos, [],
            'Comentario {# #} sin cerrar en la misma línea: se vería en pantalla. '
            'Para varias líneas hay que usar el bloque comment de Django.',
        )


class PlantillasCompilanTests(SimpleTestCase):
    """
    Compila TODAS las plantillas para cazar etiquetas sin cerrar.

    A un {% if %} al que le falta su {% endif %} no se le ve nada raro al
    escribirlo: la plantilla revienta hasta que alguien abre esa pantalla.
    Solo lo agarra una prueba que justo pinte esa vista, y no todas las
    tienen. Compilar alcanza para detectarlo y no necesita datos ni contexto.
    """

    def test_todas_las_plantillas_compilan(self):
        raiz = Path(settings.BASE_DIR) / 'templates'
        rotas = []
        for plantilla in sorted(raiz.rglob('*.html')):
            nombre = plantilla.relative_to(raiz).as_posix()
            try:
                get_template(nombre)
            except Exception as error:
                rotas.append(f'{nombre}: {error}')

        self.assertEqual(rotas, [], 'Plantillas que no compilan: ' + '; '.join(rotas))


class FormatoGuatemalaTests(SimpleTestCase):
    """
    Django trae el "es" de España, que usa la coma para los decimales: los
    precios salían como `Q 1.500,00`. Guatemala lo usa al revés. Se corrige
    con config/formats/es/formats.py y esto lo deja fijado.
    """

    def render(self, plantilla, contexto):
        from django.template import Context, Template
        return Template(plantilla).render(Context(contexto))

    def test_los_precios_usan_punto_decimal_y_coma_de_miles(self):
        from decimal import Decimal

        self.assertEqual(
            self.render('{{ p|floatformat:2 }}', {'p': Decimal('1500.50')}),
            '1,500.50',
        )
        self.assertEqual(
            self.render('{{ p|floatformat:2 }}', {'p': Decimal('1004087')}),
            '1,004,087.00',
        )

    def test_las_fechas_van_en_dia_mes_ano(self):
        import datetime

        self.assertEqual(
            self.render('{{ f }}', {'f': datetime.date(2026, 8, 25)}),
            '25/08/2026',
        )

    def test_los_formularios_siguen_recibiendo_numeros_crudos(self):
        """
        Lo que se muestra se formatea, pero un <input type="number"> manda y
        espera el punto decimal sin separadores. Si el formato se colara al
        formulario, no se podría guardar un precio.
        """
        from django import forms

        class Prueba(forms.Form):
            precio = forms.DecimalField()

        form = Prueba(data={'precio': '1500.50'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.cleaned_data['precio']), '1500.50')


class AutodeteccionDeColumnasTests(SimpleTestCase):
    """
    La carga masiva propone qué columna es cuál mirando el encabezado. Los dos
    Excel reales traen varias columnas con la palabra "EXISTENCIA" —el saldo
    al inicio de la semana, el de cada semana y el total del mes— y la buena
    es la última. Antes ganaba la que estuviera más a la izquierda, así que la
    pantalla proponía el saldo del arranque de la semana 1.
    """

    # Los encabezados reales de FO-SE-053, en el orden en que vienen.
    COLUMNAS_VENTAS = [
        ('B', 'PRODUCTO'), ('C', 'No. BODEGA'), ('D', 'MARCA'), ('E', 'MODELO'),
        ('P', 'EXISTENCIA INICIO SEMANA'), ('AJ', 'EXISTENCIA POR SEMANA'),
        ('AP', 'TOTAL EXISTENCIA MENSUAL'),
    ]
    COLUMNAS_TECNICA = [
        ('B', 'PRODUCTO'), ('E', 'CODIGO INTERNO'), ('L', 'VIENE MES ANTERIOR'),
        ('AB', 'EXISTENCIA POR SEMANA'), ('AG', 'TOTAL EXISTENCIA MENSUAL'),
    ]

    def test_ventas_propone_el_total_del_mes(self):
        from ventas.importador import autodetectar_mapeo

        mapeo = autodetectar_mapeo(self.COLUMNAS_VENTAS)

        self.assertEqual(mapeo['stock_inicial'], 'AP')

    def test_tecnica_propone_el_total_del_mes(self):
        from tecnica.importador import autodetectar_mapeo

        mapeo = autodetectar_mapeo(self.COLUMNAS_TECNICA)

        self.assertEqual(
            mapeo['existencia'], 'AG',
            '"VIENE MES ANTERIOR" es el saldo del mes pasado y en enero viene vacío',
        )

    def test_si_falta_la_preferida_usa_la_siguiente(self):
        """Una hoja recortada a mano igual tiene que poder importarse."""
        from tecnica.importador import autodetectar_mapeo

        mapeo = autodetectar_mapeo([('B', 'PRODUCTO'), ('C', 'EXISTENCIA POR SEMANA')])

        self.assertEqual(mapeo['existencia'], 'C')
