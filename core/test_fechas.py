"""
Las fechas van en año-mes-día (ISO 8601), el estándar de la empresa.

El formato se define una sola vez, en config/formats/es/formats.py. Las
pantallas lo piden por nombre (|date:"DATE_FORMAT") y el código Python pasa
por core/fechas.py. Antes había 22 fechas en plantillas y 8 en Python con su
propio "día/mes/año" escrito a mano: cambiar el formato obligaba a buscarlas
una por una, y la que se escapara seguiría diciendo la fecha al revés.

Las dos últimas clases son guardias: fallan si alguien vuelve a escribir un
formato a mano.
"""

import datetime
import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import timezone

from core import exportar, fechas

RAIZ = Path(settings.BASE_DIR)


class ElFormatoTests(SimpleTestCase):
    def test_fecha(self):
        self.assertEqual(fechas.fecha(datetime.date(2026, 9, 28)), '2026-09-28')

    def test_fecha_con_hora(self):
        momento = timezone.make_aware(datetime.datetime(2026, 9, 28, 8, 31))
        self.assertEqual(fechas.fecha_hora(momento), '2026-09-28 08:31')

    def test_se_escribe_en_hora_de_guatemala(self):
        """
        Guardada en UTC, una salida de las 7:30 de la noche es la 1:30 del día
        siguiente. Sin pasarla a la hora local, la boleta saldría con otra fecha.
        """
        en_utc = datetime.datetime(2026, 9, 29, 1, 30, tzinfo=datetime.timezone.utc)

        self.assertEqual(fechas.fecha(en_utc), '2026-09-28')
        self.assertEqual(fechas.fecha_hora(en_utc), '2026-09-28 19:30')

    def test_sin_fecha_queda_vacio(self):
        self.assertEqual(fechas.fecha(None), '')
        self.assertEqual(fechas.fecha_hora(None), '')

    def test_las_pantallas_usan_el_mismo(self):
        momento = timezone.make_aware(datetime.datetime(2026, 9, 28, 8, 31))
        plantilla = Template('{{ m|date:"DATETIME_FORMAT" }} · {{ m|date:"DATE_FORMAT" }}')

        self.assertEqual(plantilla.render(Context({'m': momento})), '2026-09-28 08:31 · 2026-09-28')

    def test_el_excel_tambien(self):
        """Excel no lee el formato de Django: se escribe aparte, igual."""
        self.assertEqual(exportar.FORMATO_FECHA, 'YYYY-MM-DD HH:MM')

    def test_se_sigue_aceptando_la_fecha_escrita_como_antes(self):
        """Quien la escriba a mano como día/mes/año no se topa con un error."""
        from django import forms

        class Prueba(forms.Form):
            dia = forms.DateField()

        for escrita in ('2026-09-28', '28/09/2026'):
            with self.subTest(escrita=escrita):
                formulario = Prueba({'dia': escrita})
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.cleaned_data['dia'], datetime.date(2026, 9, 28))


class NingunaPlantillaEscribeSuPropioFormatoTests(SimpleTestCase):
    """
    Una plantilla pide el formato por nombre. Si escribe el suyo ("d/m/Y"),
    ya no cambia cuando cambia el de la empresa.
    """

    NOMBRES = {'DATE_FORMAT', 'DATETIME_FORMAT', 'SHORT_DATE_FORMAT', 'SHORT_DATETIME_FORMAT'}

    def test_solo_formatos_por_nombre(self):
        a_mano = []
        for plantilla in (RAIZ / 'templates').rglob('*.html'):
            texto = plantilla.read_text(encoding='utf-8')
            for formato in re.findall(r'\|(?:date|time):"([^"]*)"', texto):
                if formato not in self.NOMBRES:
                    a_mano.append(f'{plantilla.relative_to(RAIZ)}: "{formato}"')

        self.assertEqual(a_mano, [], 'Usá |date:"DATE_FORMAT" o |date:"DATETIME_FORMAT"')

    def test_la_guardia_si_revisa_algo(self):
        """Si la búsqueda no encontrara ninguna fecha, la prueba de arriba no probaría nada."""
        encontradas = sum(
            len(re.findall(r'\|date:"', p.read_text(encoding='utf-8')))
            for p in (RAIZ / 'templates').rglob('*.html')
        )
        self.assertGreater(encontradas, 15)


class NingunCodigoEscribeLaFechaAlRevesTests(SimpleTestCase):
    """
    Día primero (%d/%m) o el de Estados Unidos (%m/%d) en Python son una fecha
    que no sigue el estándar. Se usa core/fechas.py. El ISO (%Y-%m-%d) sí se
    permite escrito: lo pide el calendario del navegador para comunicarse, y
    va en el nombre de los archivos de Excel.

    Se salvan el propio archivo de formatos —que acepta día/mes/año escrito a
    mano, para no rechazarle la fecha a nadie— y las pruebas y migraciones.
    """

    PERMITIDOS = {Path('config/formats/es/formats.py')}
    AL_REVES = re.compile(r'%d[/.-]%m|%m/%d')

    def archivos(self):
        for archivo in RAIZ.rglob('*.py'):
            relativo = archivo.relative_to(RAIZ)
            partes = relativo.parts
            if relativo in self.PERMITIDOS or 'migrations' in partes:
                continue
            if partes[0] in ('.git', 'node_modules', 'staticfiles', 'media'):
                continue
            if relativo.name.startswith('test'):
                continue
            yield archivo, relativo

    def test_nadie_escribe_dia_mes_ni_mes_dia(self):
        al_reves = [
            f'{relativo}: {linea.strip()}'
            for archivo, relativo in self.archivos()
            for linea in archivo.read_text(encoding='utf-8').splitlines()
            if self.AL_REVES.search(linea)
        ]
        self.assertEqual(al_reves, [], 'Usá core.fechas.fecha() o fecha_hora()')

    def test_la_guardia_si_revisa_algo(self):
        self.assertGreater(sum(1 for _ in self.archivos()), 30)
