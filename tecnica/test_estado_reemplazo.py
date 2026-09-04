"""
El tercer estado de un activo: "Próximo a reemplazo".

Antes solo había bueno y malo, y no había dónde anotar el caso más común: la
herramienta todavía sirve y se sigue prestando, pero hay que ir comprando la
de repuesto. Eso quedaba en la cabeza de quien la usó.

Lo que más se prueba acá es que aparezca **en todas partes**. El chip de
estado se pintaba a mano en cinco plantillas, cada una con un `else` que
decía "Mal estado", así que un estado nuevo se habría mostrado mal en
silencio en la que se olvidara.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from tecnica.templatetags.tecnica_extras import clase_estado
from usuarios.models import Usuario

REEMPLAZO = Activo.Estado.PROXIMO_A_REEMPLAZO
# Lo que tiene que salir pintado. Se compara el chip entero y no solo el
# texto: es la forma de notar que se pintó con el color de otro estado.
CHIP = '<span class="chip chip-warn">Próximo a reemplazo</span>'


class BaseReemplazo(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_estado', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-TE500', nombre_producto='ESMERIL GASTADO',
            bodega=cls.bodega, precio=250, estado=REEMPLAZO,
        )
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=cls.activo,
            cantidad=4, usuario=cls.admin, folio='A-1',
        )
        cls.activo.refresh_from_db()

    def setUp(self):
        self.client.force_login(self.admin)


class ElEstadoExisteTests(BaseReemplazo):
    def test_esta_entre_las_opciones(self):
        self.assertIn(REEMPLAZO, Activo.Estado.values)

    def test_se_llama_proximo_a_reemplazo(self):
        self.assertEqual(self.activo.get_estado_display(), 'Próximo a reemplazo')

    def test_van_en_orden_de_desgaste(self):
        """Se leen como una escala en el desplegable, no alfabéticamente."""
        self.assertEqual(
            list(Activo.Estado.values),
            ['buen_estado', 'proximo_a_reemplazo', 'mal_estado'],
        )

    def test_cabe_con_margen_en_el_campo(self):
        """'proximo_a_reemplazo' son 19 caracteres y el campo tenía 20."""
        largo = Activo._meta.get_field('estado').max_length

        self.assertGreaterEqual(largo, len(REEMPLAZO) + 5, 'sin margen para otro estado')

    def test_se_guarda_y_se_lee_igual(self):
        self.activo.refresh_from_db()

        self.assertEqual(self.activo.estado, REEMPLAZO)


class SeVeEnLasPantallasTests(BaseReemplazo):
    def test_en_el_catalogo(self):
        respuesta = self.client.get(reverse('catalogo_activos'))

        self.assertContains(respuesta, CHIP, html=True)

    def test_en_la_ficha_del_activo(self):
        respuesta = self.client.get(reverse('activo_detalle', args=[self.activo.pk]))

        self.assertContains(respuesta, CHIP, html=True)

    def test_en_el_reporte_de_bodega_tecnica(self):
        respuesta = self.client.get(reverse('reporte_tecnica'))

        self.assertContains(respuesta, CHIP, html=True)

    def test_se_puede_elegir_en_el_formulario(self):
        respuesta = self.client.get(reverse('activo_nuevo'))

        self.assertContains(respuesta, 'proximo_a_reemplazo')
        self.assertContains(respuesta, 'Próximo a reemplazo')

    def test_se_puede_guardar_desde_el_formulario(self):
        self.client.post(reverse('activo_nuevo'), {
            'codigo_interno': 'SE-TE501', 'nombre_producto': 'BROCA GASTADA',
            'marca': '', 'modelo': 'B-1', 'bodega': self.bodega.pk,
            'categoria': '', 'proveedor': '', 'precio': '10',
            'estado': REEMPLAZO, 'imagen_url': '',
        })

        self.assertEqual(Activo.objects.get(codigo_interno='SE-TE501').estado, REEMPLAZO)


class SeCuentaYSeFiltraTests(BaseReemplazo):
    def test_el_resumen_lo_cuenta_aparte(self):
        from core import reportes

        resumen = reportes.valorizacion_tecnica()

        self.assertEqual(resumen['proximo_a_reemplazo'], 1)
        self.assertEqual(resumen['mal_estado'], 0)

    def test_la_tarjeta_del_resumen_lo_muestra(self):
        respuesta = self.client.get(reverse('reporte_existencias'))

        self.assertContains(respuesta, 'Próximas a reemplazo')
        self.assertContains(respuesta, 'En mal estado')

    def test_se_puede_filtrar_por_el_en_el_catalogo(self):
        Activo.objects.create(
            codigo_interno='SE-TE502', nombre_producto='TALADRO NUEVO',
            bodega=self.bodega, precio=100, estado=Activo.Estado.BUEN_ESTADO,
        )

        respuesta = self.client.get(reverse('catalogo_activos'), {'estado': REEMPLAZO})

        self.assertContains(respuesta, 'ESMERIL GASTADO')
        self.assertNotContains(respuesta, 'TALADRO NUEVO')

    def test_se_puede_filtrar_por_el_en_el_reporte(self):
        respuesta = self.client.get(reverse('reporte_tecnica'), {'estado': REEMPLAZO})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ESMERIL GASTADO')

    def test_sale_en_el_excel(self):
        respuesta = self.client.get(reverse('reporte_tecnica'), {'formato': 'excel'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheetml', respuesta['Content-Type'])


class EnLosPrestamosTests(BaseReemplazo):
    """
    Una herramienta puede salir ya gastada, y sobre todo puede **regresar**
    así: es el momento en que se nota que hay que ir comprando la de repuesto.
    """

    def test_esta_entre_las_opciones_de_salida(self):
        """Estaban escritas a mano en el modelo y solo tenían bueno y malo."""
        valores = [v for v, _ in PrestamoActivo._meta.get_field('estado_al_salir').choices]

        self.assertIn(REEMPLAZO, valores)

    def test_esta_entre_las_opciones_de_regreso(self):
        valores = [v for v, _ in PrestamoActivo._meta.get_field('estado_al_regresar').choices]

        self.assertIn(REEMPLAZO, valores)

    def test_puede_salir_con_ese_estado(self):
        prestamo = PrestamoActivo.objects.create(
            activo=self.activo, cantidad=1, solicitante='Ivan Leiva',
            usuario=self.admin, estado_al_salir=REEMPLAZO,
        )

        self.assertEqual(prestamo.get_estado_al_salir_display(), 'Próximo a reemplazo')

    def test_se_ve_en_la_lista_de_prestamos(self):
        PrestamoActivo.objects.create(
            activo=self.activo, cantidad=1, solicitante='Ivan Leiva',
            usuario=self.admin, estado_al_salir=REEMPLAZO,
        )

        respuesta = self.client.get(reverse('prestamos_tecnica'))

        self.assertContains(respuesta, CHIP, html=True)


class ColorDelChipTests(TestCase):
    """Los tres se leen como una escala: verde, ámbar, rojo."""

    def test_cada_estado_tiene_su_color(self):
        self.assertEqual(clase_estado(Activo.Estado.BUEN_ESTADO), 'chip-good')
        self.assertEqual(clase_estado(REEMPLAZO), 'chip-warn')
        self.assertEqual(clase_estado(Activo.Estado.MAL_ESTADO), 'chip-critical')

    def test_los_tres_colores_son_distintos(self):
        colores = {clase_estado(v) for v in Activo.Estado.values}

        self.assertEqual(len(colores), 3, 'dos estados comparten color')

    def test_uno_desconocido_no_se_disfraza_de_otro(self):
        """
        Mejor que se vea raro y se note, a que herede el color de otro estado
        y parezca correcto.
        """
        self.assertEqual(clase_estado('lo_que_sea'), 'chip-neutral')
        self.assertEqual(clase_estado(''), 'chip-neutral')
