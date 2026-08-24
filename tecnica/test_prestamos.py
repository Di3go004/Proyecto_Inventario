"""
Pruebas de la Fase 3 en Bodega Técnica (RF-07, RF-12, RF-13).

El punto del módulo es responder lo que el Excel no puede: quién tiene cada
herramienta ahora mismo y en qué estado salió y volvió.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.models import Activo, PrestamoActivo
from usuarios.models import Usuario


class BasePrestamos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.operador = Usuario.objects.create_user(
            username='operador_tec', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='contable_tec', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.taladro = Activo.objects.create(
            codigo_interno='SE-TEC-001', nombre_producto='Taladro percutor',
            marca='Bosch', modelo='GSB-550', bodega=cls.bodega, precio=900,
        )
        cls.rotomartillo = Activo.objects.create(
            codigo_interno='SE-TEC-002', nombre_producto='Rotomartillo',
            bodega=cls.bodega, precio=1800,
        )

    def setUp(self):
        self.client.login(username='operador_tec', password='clave-de-prueba')

    def prestar(self, activo=None, **extra):
        datos = {
            'activo': (activo or self.taladro).pk,
            'cantidad': 1,
            'solicitante': 'Ivan Leiva',
            'fecha_salida': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'entregado_por': 'Bodega',
            'estado_al_salir': Activo.Estado.BUEN_ESTADO,
            'observacion': '',
        }
        datos.update(extra)
        return self.client.post(reverse('prestamo_nuevo'), datos)


class SalidaTests(BasePrestamos):
    def test_registrar_la_salida_deja_el_activo_afuera(self):
        respuesta = self.prestar()

        self.assertRedirects(respuesta, reverse('prestamos_tecnica'))
        prestamo = PrestamoActivo.objects.get()
        self.assertEqual(prestamo.solicitante, 'Ivan Leiva')
        self.assertIsNone(prestamo.fecha_regreso)
        self.taladro.refresh_from_db()
        self.assertTrue(self.taladro.esta_prestado)

    def test_no_se_puede_prestar_algo_que_ya_esta_afuera(self):
        """RF-07: un mismo activo no puede tener dos préstamos abiertos."""
        self.prestar()

        respuesta = self.prestar(solicitante='Otra persona')

        self.assertEqual(respuesta.status_code, 200, 'se queda en el formulario')
        self.assertEqual(PrestamoActivo.objects.count(), 1)
        self.assertContains(respuesta, 'ya está prestado')

    def test_no_se_puede_prestar_un_activo_dado_de_baja(self):
        """RF-12: si está de baja, deja de ofrecerse para préstamo."""
        Activo.objects.filter(pk=self.rotomartillo.pk).update(estado=Activo.Estado.DE_BAJA)

        respuesta = self.prestar(activo=self.rotomartillo)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PrestamoActivo.objects.count(), 0)

    def test_el_formulario_llega_con_el_estado_de_salida_ya_propuesto(self):
        """
        Regresión: el campo salía vacío con la opción "---------" y el
        formulario se rechazaba por algo que el operador no tenía motivo
        para tocar. Una herramienta siempre sale en algún estado.
        """
        respuesta = self.client.get(reverse('prestamo_nuevo'))
        campo = respuesta.context['form']['estado_al_salir']

        self.assertEqual(campo.value(), Activo.Estado.BUEN_ESTADO)
        self.assertNotIn(
            '', [valor for valor, _etiqueta in campo.field.choices],
            'no debe quedar la opción vacía',
        )

    def test_se_guarda_la_fecha_de_salida_que_puso_el_operador(self):
        self.prestar(fecha_salida='2026-07-15T14:30')

        salida = timezone.localtime(PrestamoActivo.objects.get().fecha_salida)
        self.assertEqual((salida.year, salida.month, salida.day), (2026, 7, 15))
        self.assertEqual((salida.hour, salida.minute), (14, 30))


class RegresoTests(BasePrestamos):
    def registrar_regreso(self, prestamo, estado, **extra):
        datos = {
            'fecha_regreso': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'recibido_por': 'Bodega',
            'estado_al_regresar': estado,
            'observacion': '',
        }
        datos.update(extra)
        return self.client.post(reverse('prestamo_regreso', args=[prestamo.pk]), datos)

    def test_el_formulario_de_regreso_llega_con_fecha_y_estado_propuestos(self):
        """
        Regresión: en un ModelForm los valores de la instancia pisan el
        initial del campo. Como el préstamo abierto tiene fecha_regreso y
        estado_al_regresar vacíos, el formulario salía en blanco y no se
        podía guardar sin llenar a mano algo que el sistema ya sabía.
        """
        self.prestar(estado_al_salir=Activo.Estado.MAL_ESTADO)
        prestamo = PrestamoActivo.objects.get()

        form = self.client.get(reverse('prestamo_regreso', args=[prestamo.pk])).context['form']

        self.assertIsNotNone(form['fecha_regreso'].value())
        self.assertEqual(
            form['estado_al_regresar'].value(), Activo.Estado.MAL_ESTADO,
            'se propone el mismo estado con el que salió',
        )

    def test_el_regreso_cierra_el_prestamo(self):
        self.prestar()
        prestamo = PrestamoActivo.objects.get()

        self.registrar_regreso(prestamo, Activo.Estado.BUEN_ESTADO)

        prestamo.refresh_from_db()
        self.taladro.refresh_from_db()
        self.assertIsNotNone(prestamo.fecha_regreso)
        self.assertFalse(self.taladro.esta_prestado)

    def test_si_vuelve_dañado_el_catalogo_se_entera_solo(self):
        """
        Es lo que hoy se pierde en el Excel: la herramienta regresa mal y
        nadie se acuerda de actualizar el listado.
        """
        self.prestar()
        prestamo = PrestamoActivo.objects.get()

        self.registrar_regreso(prestamo, Activo.Estado.MAL_ESTADO)

        self.taladro.refresh_from_db()
        self.assertEqual(self.taladro.estado, Activo.Estado.MAL_ESTADO)

    def test_si_vuelve_para_dar_de_baja_deja_de_prestarse(self):
        self.prestar()
        prestamo = PrestamoActivo.objects.get()
        self.registrar_regreso(prestamo, Activo.Estado.DE_BAJA)

        respuesta = self.prestar()

        self.taladro.refresh_from_db()
        self.assertEqual(self.taladro.estado, Activo.Estado.DE_BAJA)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PrestamoActivo.objects.count(), 1, 'no se creó un préstamo nuevo')

    def test_el_regreso_no_puede_ser_anterior_a_la_salida(self):
        self.prestar()
        prestamo = PrestamoActivo.objects.get()

        respuesta = self.registrar_regreso(
            prestamo, Activo.Estado.BUEN_ESTADO, fecha_regreso='2020-01-01T08:00',
        )

        prestamo.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(prestamo.fecha_regreso)

    def test_un_prestamo_ya_cerrado_no_se_puede_volver_a_cerrar(self):
        self.prestar()
        prestamo = PrestamoActivo.objects.get()
        self.registrar_regreso(prestamo, Activo.Estado.BUEN_ESTADO)

        respuesta = self.client.get(reverse('prestamo_regreso', args=[prestamo.pk]))

        self.assertRedirects(respuesta, reverse('prestamos_tecnica'))

    def test_al_prestarlo_de_nuevo_el_ciclo_vuelve_a_empezar(self):
        self.prestar()
        self.registrar_regreso(PrestamoActivo.objects.get(), Activo.Estado.BUEN_ESTADO)

        self.prestar(solicitante='Segunda persona')

        self.assertEqual(PrestamoActivo.objects.count(), 2)
        self.taladro.refresh_from_db()
        self.assertTrue(self.taladro.esta_prestado)


class ListadoPrestamosTests(BasePrestamos):
    def test_por_defecto_muestra_solo_lo_que_esta_afuera(self):
        self.prestar()
        self.prestar(activo=self.rotomartillo, solicitante='Otra persona')
        devuelto = PrestamoActivo.objects.get(activo=self.rotomartillo)
        self.client.post(reverse('prestamo_regreso', args=[devuelto.pk]), {
            'fecha_regreso': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'recibido_por': 'Bodega',
            'estado_al_regresar': Activo.Estado.BUEN_ESTADO,
            'observacion': '',
        })

        respuesta = self.client.get(reverse('prestamos_tecnica'))
        prestamos = list(respuesta.context['prestamos'])

        self.assertEqual(len(prestamos), 1)
        self.assertEqual(prestamos[0].activo, self.taladro)

    def test_se_puede_ver_todo_el_historial(self):
        self.prestar()
        self.prestar(activo=self.rotomartillo, solicitante='Otra persona')

        respuesta = self.client.get(reverse('prestamos_tecnica'), {'estado': 'todos'})

        self.assertEqual(len(respuesta.context['prestamos']), 2)

    def test_busca_por_persona(self):
        self.prestar(solicitante='Marisol Pérez')
        self.prestar(activo=self.rotomartillo, solicitante='Otra persona')

        respuesta = self.client.get(reverse('prestamos_tecnica'), {'q': 'Marisol'})

        self.assertEqual(len(respuesta.context['prestamos']), 1)


class BuscadorActivosTests(BasePrestamos):
    def test_marca_los_que_ya_estan_prestados(self):
        self.prestar()

        resultados = self.client.get(reverse('api_buscar_activos'), {'q': 'Taladro'}).json()['resultados']

        self.assertEqual(len(resultados), 1)
        self.assertTrue(resultados[0]['prestado'])

    def test_no_sugiere_los_dados_de_baja(self):
        Activo.objects.filter(pk=self.rotomartillo.pk).update(estado=Activo.Estado.DE_BAJA)

        resultados = self.client.get(reverse('api_buscar_activos'), {'q': 'Rotomartillo'}).json()['resultados']

        self.assertEqual(resultados, [])


class PermisosPrestamosTests(BasePrestamos):
    """RF-04: contabilidad consulta, no registra."""

    def setUp(self):
        self.client.login(username='contable_tec', password='clave-de-prueba')

    def test_contabilidad_puede_ver_los_prestamos(self):
        self.assertEqual(self.client.get(reverse('prestamos_tecnica')).status_code, 200)

    def test_contabilidad_no_puede_registrar_una_salida(self):
        respuesta = self.prestar()
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(PrestamoActivo.objects.count(), 0)
