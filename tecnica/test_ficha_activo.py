"""
Lo que dice la ficha de un activo cuando no queda existencia.

Un activo en 0 puede estarlo por dos razones distintas —se dio de baja todo, o
todavía nadie le registró el ingreso— y la ficha las mostraba iguales:
afirmaba que se había dado de baja todo incluso en activos sin un solo
movimiento. Recién cargado el catálogo eso era mentira en los 252.

Además la ficha nunca mostró **cuántas hay**, y la disponibilidad decía
"Disponible" con existencia 0 porque solo preguntaba si estaba prestado.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from usuarios.models import Usuario


class BaseFicha(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_ficha', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def activo(self, codigo='SE-TE800', **extra):
        return Activo.objects.create(
            codigo_interno=codigo, nombre_producto=f'Cosa {codigo}',
            bodega=self.bodega, precio=10, **extra,
        )

    def ingresar(self, activo, cantidad):
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=activo,
            cantidad=cantidad, usuario=self.admin, folio='A-1',
        )
        activo.refresh_from_db()
        return activo

    def dar_de_baja(self, activo, cantidad):
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.BAJA, activo=activo, cantidad=cantidad,
            usuario=self.admin, motivo=MovimientoActivo.Motivo.DANADO,
        )
        activo.refresh_from_db()
        return activo

    def ficha(self, activo):
        return self.client.get(reverse('activo_detalle', args=[activo.pk]))


class SinMovimientosTests(BaseFicha):
    def test_uno_recien_creado_no_tiene_movimientos(self):
        self.assertTrue(self.activo().sin_movimientos)

    def test_uno_con_ingreso_si_los_tiene(self):
        activo = self.ingresar(self.activo(), 5)

        self.assertFalse(activo.sin_movimientos)

    def test_uno_al_que_se_le_dio_de_baja_todo_los_conserva(self):
        """Es la diferencia: está en 0, pero sí pasó algo."""
        activo = self.dar_de_baja(self.ingresar(self.activo(), 5), 5)

        self.assertEqual(activo.existencia, 0)
        self.assertTrue(activo.agotado)
        self.assertFalse(activo.sin_movimientos)


class ElAvisoDiceLaVerdadTests(BaseFicha):
    def test_al_que_nunca_le_entro_nada_no_le_dice_que_se_dio_de_baja(self):
        respuesta = self.ficha(self.activo())

        self.assertNotContains(respuesta, 'Se dio de baja todo')
        self.assertContains(respuesta, 'Todavía no tiene existencia')

    def test_le_explica_de_dónde_sale_la_cantidad(self):
        respuesta = self.ficha(self.activo())

        self.assertContains(respuesta, 'FO-SE-013')

    def test_a_un_consumible_le_ofrece_tambien_editarlo(self):
        respuesta = self.ficha(self.activo(es_consumible=True))

        self.assertContains(respuesta, 'Editar')
        self.assertContains(respuesta, 'consumible')

    def test_al_que_si_se_le_dio_de_baja_todo_se_lo_dice(self):
        activo = self.dar_de_baja(self.ingresar(self.activo(), 5), 5)

        respuesta = self.ficha(activo)

        self.assertContains(respuesta, 'Se dio de baja todo')
        self.assertNotContains(respuesta, 'Todavía no tiene existencia')

    def test_con_existencia_no_avisa_nada_de_eso(self):
        activo = self.ingresar(self.activo(), 5)

        respuesta = self.ficha(activo)

        self.assertNotContains(respuesta, 'Se dio de baja todo')
        self.assertNotContains(respuesta, 'Todavía no tiene existencia')


class LaFichaMuestraLaExistenciaTests(BaseFicha):
    """No la mostraba en ningún lado: había precio, estado, nivel y umbrales,
    pero no cuántas hay. Era el dato que faltaba para entender la pantalla."""

    def test_la_muestra(self):
        activo = self.ingresar(self.activo(), 7)

        respuesta = self.ficha(activo)

        self.assertContains(respuesta, 'Existencia')
        self.assertContains(respuesta, '<strong>7</strong>', html=True)

    def test_tambien_cuando_esta_en_cero(self):
        respuesta = self.ficha(self.activo())

        self.assertContains(respuesta, 'Existencia')
        self.assertContains(respuesta, '<strong>0</strong>', html=True)

    def test_marca_los_consumibles(self):
        respuesta = self.ficha(self.activo(es_consumible=True))

        self.assertContains(respuesta, 'Consumible')


class LaDisponibilidadNoMienteTests(BaseFicha):
    def test_sin_existencia_dice_agotado_y_no_disponible(self):
        """
        Antes solo preguntaba si estaba prestado: como no lo estaba, decía
        "Disponible" aunque no hubiera ni una unidad — y contradecía al aviso
        que salía justo encima.
        """
        respuesta = self.ficha(self.activo())

        self.assertContains(respuesta, '<span class="chip chip-critical">Agotado</span>', html=True)
        self.assertNotContains(respuesta, '<span class="chip chip-good">Disponible</span>', html=True)

    def test_con_existencia_y_sin_prestamos_dice_disponible(self):
        activo = self.ingresar(self.activo(), 5)

        respuesta = self.ficha(activo)

        self.assertContains(respuesta, '<span class="chip chip-good">Disponible</span>', html=True)

    def test_con_algunas_prestadas_dice_cuantas_hay_de_cada(self):
        activo = self.ingresar(self.activo(), 5)
        PrestamoActivo.objects.create(
            activo=activo, cantidad=2, solicitante='Ivan Leiva',
            usuario=self.admin, estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        respuesta = self.ficha(activo)

        self.assertContains(respuesta, '2 afuera')
        self.assertContains(respuesta, '3 libre(s)')

    def test_dice_lo_mismo_que_el_catalogo(self):
        """
        La ficha se había quedado atrás: el catálogo ya distinguía agotado de
        disponible. Que las dos pantallas no vuelvan a discrepar.
        """
        self.activo('SE-VACIO')
        self.ingresar(self.activo('SE-LLENO'), 5)

        catalogo = self.client.get(reverse('catalogo_activos'))

        self.assertContains(catalogo, 'Agotado')
        self.assertContains(catalogo, 'Disponible')


class ElBotonDeDarDeBajaTests(BaseFicha):
    def test_no_se_ofrece_si_no_hay_nada_que_dar_de_baja(self):
        activo = self.activo()

        respuesta = self.ficha(activo)

        self.assertNotContains(respuesta, reverse('activo_baja', args=[activo.pk]))

    def test_si_se_ofrece_cuando_hay_existencia(self):
        activo = self.ingresar(self.activo(), 5)

        respuesta = self.ficha(activo)

        self.assertContains(respuesta, reverse('activo_baja', args=[activo.pk]))
