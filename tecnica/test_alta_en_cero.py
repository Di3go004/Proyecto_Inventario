"""
Un activo nace en 0, igual que un artículo de Bodega 1 y 2.

La cantidad entra con un ingreso (FO-SE-013), nunca escribiéndola en el
catálogo. Antes el formulario de alta traía el campo "Cantidad en bodega"
abierto, y por ahí entraron 218 cantidades que ninguna boleta respalda: en la
lista de movimientos salen como "Ajuste", sin folio ni solicitante.

La marca de consumible **no** es una excepción a la regla. Solo cambia una
cosa: permite corregir la cantidad DESPUÉS, sobre un activo que ya existe.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.forms import ActivoForm
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario


class BaseAlta(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_alta', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            'codigo_interno': 'SE-TE900', 'nombre_producto': 'TALADRO DE PRUEBA',
            'marca': '', 'modelo': 'T-900', 'bodega': self.bodega.pk,
            'categoria': '', 'proveedor': '', 'precio': '100',
            'estado': Activo.Estado.BUEN_ESTADO, 'imagen_url': '',
        }
        datos.update(extra)
        return datos

    def crear(self, **extra):
        respuesta = self.client.post(reverse('activo_nuevo'), self.datos(**extra))
        self.assertEqual(respuesta.status_code, 302, 'el alta no guardó')
        return Activo.objects.get(codigo_interno=self.datos(**extra)['codigo_interno'])


class ElCampoNoSeOfreceAlCrearTests(BaseAlta):
    def test_al_crear_la_cantidad_no_se_puede_escribir(self):
        self.assertTrue(ActivoForm().fields['existencia'].disabled)

    def test_la_pantalla_explica_de_dónde_sale_la_cantidad(self):
        respuesta = self.client.get(reverse('activo_nuevo'))

        self.assertContains(respuesta, 'Arranca en 0')
        self.assertContains(respuesta, 'FO-SE-013')

    def test_al_editar_un_consumible_si_se_puede_escribir(self):
        activo = self.crear(es_consumible='on')

        self.assertFalse(ActivoForm(instance=activo).fields['existencia'].disabled)

    def test_al_editar_uno_que_no_es_consumible_sigue_bloqueada(self):
        activo = self.crear()

        self.assertTrue(ActivoForm(instance=activo).fields['existencia'].disabled)


class NaceEnCeroTests(BaseAlta):
    def test_un_activo_nuevo_arranca_en_cero(self):
        self.assertEqual(self.crear().existencia, 0)

    def test_crear_no_genera_ningún_movimiento(self):
        """
        Es el origen de los 218 "Ajuste — Saldo inicial": el alta creaba un
        movimiento de cantidad que ninguna boleta respaldaba.
        """
        activo = self.crear()

        self.assertEqual(activo.movimientos.count(), 0)

    def test_mandar_una_cantidad_en_el_formulario_no_sirve_de_nada(self):
        """
        El campo va deshabilitado, pero eso es HTML: no impide que alguien
        arme el POST a mano. Django ignora lo que llegue en un campo
        deshabilitado, y esto lo deja fijado.
        """
        activo = self.crear(existencia='94')

        self.assertEqual(activo.existencia, 0)
        self.assertEqual(activo.movimientos.count(), 0)

    def test_marcarlo_consumible_tampoco_le_da_cantidad_al_crear(self):
        """La marca no es una excepción a la regla: solo abre la corrección."""
        activo = self.crear(es_consumible='on', existencia='43')

        self.assertTrue(activo.es_consumible)
        self.assertEqual(activo.existencia, 0)


class LaCantidadEntraDespuésTests(BaseAlta):
    def test_un_consumible_se_corrige_al_editarlo(self):
        activo = self.crear(es_consumible='on')

        self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(es_consumible='on', existencia='43'),
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 43)

    def test_esa_corrección_queda_registrada_en_el_historial(self):
        activo = self.crear(es_consumible='on')

        self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(es_consumible='on', existencia='43'),
        )

        movimiento = activo.movimientos.get()
        self.assertEqual(movimiento.tipo, MovimientoActivo.Tipo.AJUSTE)
        self.assertEqual(movimiento.cantidad, 43)
        self.assertEqual(movimiento.usuario, self.admin)

    def test_la_herramienta_recibe_su_cantidad_con_un_ingreso(self):
        """El camino que la regla deja para lo que no es consumible."""
        activo = self.crear()

        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=activo,
            cantidad=3, usuario=self.admin, folio='A-1234',
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 3)
