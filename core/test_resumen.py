"""
El Resumen: las alertas de las dos bodegas, lado a lado.

Antes solo traía las de Bodega 1 y 2, y las listaba todas. Recién cargado el
inventario eso eran 185 filas de Ventas —y habrían sido 437 al sumar
Técnica—, con la pantalla tardando cerca de un segundo en abrir para decir lo
mismo que dicen las diez primeras. Es la pantalla a la que cae todo el mundo
al iniciar sesión, así que ahora muestra solo lo más urgente y deja el resto a
un clic, en el reporte de alertas.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from core.views import ALERTAS_EN_EL_RESUMEN
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas.models import Articulo


class BaseResumen(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_resumen', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def articulo(self, nombre, stock):
        return Articulo.objects.create(
            nombre_producto=nombre, modelo=nombre[:8], bodega=self.venta,
            precio=10, stock_actual=stock,
        )

    def activo(self, codigo, existencia=0):
        activo = Activo.objects.create(
            codigo_interno=codigo, nombre_producto=f'Herramienta {codigo}',
            bodega=self.tecnica, precio=10,
        )
        if existencia:
            MovimientoActivo.objects.create(
                tipo=MovimientoActivo.Tipo.INGRESO, activo=activo,
                cantidad=existencia, usuario=self.admin, folio='A-1',
            )
            activo.refresh_from_db()
        return activo

    def resumen(self):
        return self.client.get(reverse('resumen'))


class LaBodegaTecnicaTieneSuPanelTests(BaseResumen):
    def test_muestra_las_alertas_de_bodega_tecnica(self):
        self.activo('SE-TE001')

        respuesta = self.resumen()

        self.assertContains(respuesta, 'Bodega Técnica')
        self.assertContains(respuesta, 'SE-TE001')

    def test_van_en_un_panel_aparte_de_las_de_ventas(self):
        """
        Cada bodega tiene su catálogo, así que cada fila enlaza a un lugar
        distinto: juntarlas obligaría a etiquetar línea por línea.
        """
        self.articulo('BASCULA', 0)
        activo = self.activo('SE-TE001')

        respuesta = self.resumen()

        self.assertIn('alertas', respuesta.context)
        self.assertIn('alertas_tecnica', respuesta.context)
        self.assertNotIn(
            activo, list(respuesta.context['alertas']),
            'el activo no debe salir en el panel de Bodega 1 y 2',
        )

    def test_cada_fila_lleva_al_catalogo_que_le_toca(self):
        articulo = self.articulo('BASCULA', 0)
        activo = self.activo('SE-TE001')

        respuesta = self.resumen()

        self.assertContains(respuesta, reverse('articulo_detalle', args=[articulo.pk]))
        self.assertContains(respuesta, reverse('activo_detalle', args=[activo.pk]))

    def test_si_no_hay_nada_en_alerta_lo_dice(self):
        self.activo('SE-TE001', existencia=50)

        respuesta = self.resumen()

        self.assertContains(respuesta, 'Sin herramienta en alerta')


class SoloLasMasUrgentesTests(BaseResumen):
    def test_no_lista_mas_de_las_que_caben(self):
        for i in range(ALERTAS_EN_EL_RESUMEN + 8):
            self.activo(f'SE-TE{i:03d}')
            self.articulo(f'BASCULA {i}', 0)

        respuesta = self.resumen()

        self.assertEqual(len(respuesta.context['alertas']), ALERTAS_EN_EL_RESUMEN)
        self.assertEqual(len(respuesta.context['alertas_tecnica']), ALERTAS_EN_EL_RESUMEN)

    def test_dice_cuantas_hay_en_total(self):
        cuantas = ALERTAS_EN_EL_RESUMEN + 8
        for i in range(cuantas):
            self.activo(f'SE-TE{i:03d}')

        respuesta = self.resumen()

        self.assertEqual(respuesta.context['alertas_tecnica_total'], cuantas)
        self.assertContains(respuesta, f'Ver las {cuantas}')

    def test_el_enlace_lleva_al_reporte_de_alertas(self):
        for i in range(ALERTAS_EN_EL_RESUMEN + 3):
            self.activo(f'SE-TE{i:03d}')

        respuesta = self.resumen()

        self.assertContains(respuesta, reverse('reporte_alertas'))

    def test_sin_sobrantes_no_ofrece_el_enlace(self):
        """Un 'ver las 2' cuando ya se ven las 2 solo estorba."""
        self.activo('SE-TE001')
        self.activo('SE-TE002')

        respuesta = self.resumen()

        self.assertNotContains(respuesta, 'Ver las')

    def test_lo_mas_urgente_va_primero(self):
        """
        Con tope, el orden deja de ser cosmético: lo que no entre en los
        primeros no se ve. Lo crítico tiene que ganarle a lo de alerta.
        """
        self.activo('SE-ALERTA', existencia=4)
        for i in range(ALERTAS_EN_EL_RESUMEN):
            self.activo(f'SE-CERO{i}')

        respuesta = self.resumen()
        mostrados = [a.codigo_interno for a in respuesta.context['alertas_tecnica']]

        self.assertNotIn('SE-ALERTA', mostrados, 'lo crítico debe desplazar a lo de alerta')


class NoSeRompeLoQueYaHabiaTests(BaseResumen):
    def test_sigue_mostrando_la_valorizacion_de_las_dos_bodegas(self):
        respuesta = self.resumen()

        self.assertContains(respuesta, 'Valorización Bodega 1+2')
        self.assertContains(respuesta, 'Valorización Bodega Técnica')

    def test_sigue_mostrando_los_prestamos_abiertos(self):
        respuesta = self.resumen()

        self.assertContains(respuesta, 'Activos técnicos prestados')

    def test_el_practicante_sigue_yendo_al_catalogo(self):
        practicante = Usuario.objects.create_user(
            username='practicante_resumen', password='clave-de-prueba',
            rol=Usuario.Rol.PRACTICANTE,
        )
        self.client.force_login(practicante)

        self.assertRedirects(self.resumen(), reverse('catalogo_articulos'))

    def test_no_dispara_una_consulta_por_alerta(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for i in range(12):
            self.activo(f'SE-TE{i:03d}')
            self.articulo(f'BASCULA {i}', 0)

        with CaptureQueriesContext(connection) as consultas:
            self.resumen()

        self.assertLessEqual(
            len(consultas.captured_queries), 15,
            f'{len(consultas.captured_queries)} consultas: falta select_related/prefetch',
        )
