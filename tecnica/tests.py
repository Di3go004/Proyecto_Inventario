"""
Pruebas de Bodega Técnica: préstamo y devolución de activos (RF-07, RF-12).

A diferencia de Ventas, aquí cada activo es una unidad física: no se cuenta
stock, se rastrea quién lo tiene y en qué estado va y vuelve.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.ayuda_pruebas import dar_de_baja, dar_existencia
from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from usuarios.models import Usuario


class BaseTecnica(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.usuario = Usuario.objects.create_user(
            username='operador', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )

    def crear_activo(self, **extra):
        datos = dict(
            codigo_interno='SE-ET001', nombre_producto='Rotomartillo',
            bodega=self.bodega,
        )
        datos.update(extra)
        return Activo.objects.create(**datos)

    def prestar(self, activo, solicitante='Ivan Leiva', **extra):
        datos = dict(
            activo=activo, solicitante=solicitante, usuario=self.usuario,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )
        datos.update(extra)
        return PrestamoActivo.objects.create(**datos)


class DisponibilidadTests(BaseTecnica):
    def test_un_activo_sin_prestamos_esta_disponible(self):
        activo = self.crear_activo()
        self.assertFalse(activo.esta_prestado)

    def test_un_activo_con_prestamo_abierto_aparece_prestado(self):
        activo = self.crear_activo()
        self.prestar(activo)
        self.assertTrue(activo.esta_prestado)

    def test_al_registrar_el_regreso_vuelve_a_estar_disponible(self):
        activo = self.crear_activo()
        prestamo = self.prestar(activo)

        prestamo.fecha_regreso = timezone.now()
        prestamo.recibido_por = 'Bodeguero'
        prestamo.estado_al_regresar = Activo.Estado.BUEN_ESTADO
        prestamo.save()

        activo.refresh_from_db()
        self.assertFalse(activo.esta_prestado)

    def test_esta_prestado_no_dispara_consultas_extra_con_prefetch(self):
        """Regresión de rendimiento: el catálogo hacía una consulta por cada
        activo (N+1). Con prefetch debe resolverse en 2 consultas en total."""
        for i in range(5):
            self.crear_activo(codigo_interno=f'SE-ET{i:03d}', nombre_producto=f'Herramienta {i}')

        with self.assertNumQueries(2):
            activos = list(Activo.objects.prefetch_related('prestamos'))
            for activo in activos:
                _ = activo.esta_prestado


class ReglasDePrestamoTests(BaseTecnica):
    def test_no_se_puede_prestar_mas_de_lo_que_hay(self):
        """
        RF-07. Antes la base de datos lo impedía con una restricción de "un
        solo préstamo abierto por activo", pensada para cuando cada registro
        era una unidad física. Con existencia por cantidad esa restricción
        estorbaba —dos personas sí pueden llevar unidades del mismo
        producto— y la regla real es no pasarse de lo disponible.
        """
        activo = dar_existencia(self.crear_activo(), 1, self.usuario)
        self.prestar(activo)

        segundo = PrestamoActivo(
            activo=activo, cantidad=1, solicitante='Otra persona',
            usuario=self.usuario, estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )
        with self.assertRaises(ValidationError):
            segundo.clean()

    def test_varias_unidades_del_mismo_producto_se_pueden_prestar_a_la_vez(self):
        activo = dar_existencia(self.crear_activo(), 10, self.usuario)

        self.prestar(activo, cantidad=4)
        self.prestar(activo, solicitante='Otra persona', cantidad=3)

        activo.refresh_from_db()
        self.assertEqual(activo.cantidad_afuera, 7)
        self.assertEqual(activo.disponibles, 3)

    def test_se_puede_volver_a_prestar_despues_de_devolver(self):
        activo = dar_existencia(self.crear_activo(), 1, self.usuario)
        primero = self.prestar(activo)
        primero.fecha_regreso = timezone.now()
        primero.estado_al_regresar = Activo.Estado.BUEN_ESTADO
        primero.save()

        segundo = self.prestar(activo, solicitante='Jesus Lorenzana')
        self.assertIsNone(segundo.fecha_regreso)
        self.assertTrue(activo.esta_prestado)

    def test_lo_dado_de_baja_por_completo_no_se_puede_prestar(self):
        """RF-12: sin existencia queda fuera de circulación."""
        activo = dar_existencia(self.crear_activo(), 1, self.usuario)
        dar_de_baja(activo, 1, self.usuario)
        prestamo = PrestamoActivo(
            activo=activo, solicitante='Ivan Leiva', usuario=self.usuario,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )
        with self.assertRaises(ValidationError):
            prestamo.clean()

    def test_el_estado_puede_cambiar_al_regresar(self):
        """Si la herramienta vuelve dañada, queda registrado."""
        activo = self.crear_activo()
        prestamo = self.prestar(activo)

        prestamo.fecha_regreso = timezone.now()
        prestamo.estado_al_regresar = Activo.Estado.MAL_ESTADO
        prestamo.save()

        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado_al_salir, Activo.Estado.BUEN_ESTADO)
        self.assertEqual(prestamo.estado_al_regresar, Activo.Estado.MAL_ESTADO)


class EliminarActivoTests(TestCase):
    """
    Qué bloquea el borrado de un activo: los préstamos y los movimientos de
    verdad (un ingreso del FO-SE-013, una baja). El ajuste de conteo NO —es
    el saldo con el que se capturó, no historial— y se borra con él.

    Sin esa distinción, desde que la bodega lleva existencia por cantidad
    ningún activo se podía borrar: al crearlo con su cantidad ya nacía con un
    movimiento que lo protegía, y la pantalla reventaba con un error.
    """

    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_act', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def crear(self, codigo='SE-T1'):
        return Activo.objects.create(
            codigo_interno=codigo, nombre_producto='Taladro', bodega=self.bodega,
        )

    def ajuste_de_conteo(self, activo, cantidad):
        """
        El saldo con el que se capturó el activo: es lo que crea el formulario
        del catálogo al ponerle cantidad, y lo que deja la carga masiva del
        FO-SE-065. No es historial.
        """
        return MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.AJUSTE, activo=activo,
            cantidad=cantidad, usuario=self.admin,
        )

    def test_uno_con_solo_su_ajuste_de_conteo_se_borra(self):
        """Regresión: el saldo inicial hacía imposible borrar cualquier activo."""
        activo = self.crear('SE-CONTEO')
        self.ajuste_de_conteo(activo, 5)

        self.client.post(reverse('activo_eliminar', args=[activo.pk]))

        self.assertFalse(Activo.objects.filter(pk=activo.pk).exists())
        self.assertFalse(MovimientoActivo.objects.filter(activo_id=activo.pk).exists())

    def test_uno_con_un_ingreso_de_boleta_no_se_borra(self):
        activo = self.crear('SE-INGRESO')
        MovimientoActivo.objects.create(
            folio='ING-00007', tipo=MovimientoActivo.Tipo.INGRESO,
            activo=activo, cantidad=3, usuario=self.admin,
        )

        respuesta = self.client.post(
            reverse('activo_eliminar', args=[activo.pk]), follow=True,
        )

        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())
        self.assertContains(respuesta, 'No se puede eliminar')

    def test_uno_con_una_baja_no_se_borra(self):
        """
        La baja es el registro de lo que se descartó y no se puede perder.
        Se parte de un ajuste de conteo —que por sí solo no bloquearía— para
        que lo único que impida borrar sea la baja.
        """
        activo = self.crear('SE-BAJA')
        self.ajuste_de_conteo(activo, 4)
        dar_de_baja(activo, 2, self.admin)

        self.client.post(reverse('activo_eliminar', args=[activo.pk]))

        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())

    def test_uno_sin_prestamos_se_borra(self):
        activo = self.crear()

        self.client.post(reverse('activo_eliminar', args=[activo.pk]))

        self.assertFalse(Activo.objects.filter(pk=activo.pk).exists())

    def test_uno_con_prestamos_no_se_borra(self):
        activo = self.crear()
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.admin,
        )

        respuesta = self.client.post(reverse('activo_eliminar', args=[activo.pk]), follow=True)

        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())
        self.assertContains(respuesta, '1 préstamo(s)')

    def test_darlo_de_baja_tampoco_lo_habilita_para_borrar(self):
        """
        Descartarlo no borra su historial: los préstamos siguen ahí y siguen
        protegiendo el registro.
        """
        activo = dar_existencia(self.crear(), 1, self.admin)
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.admin,
            fecha_regreso=timezone.now(), estado_al_regresar=Activo.Estado.MAL_ESTADO,
        )
        dar_de_baja(activo, 1, self.admin)

        self.client.post(reverse('activo_eliminar', args=[activo.pk]))

        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())

    def test_la_pantalla_manda_a_darlo_de_baja(self):
        activo = self.crear()
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.admin,
        )

        pantalla = self.client.get(reverse('activo_eliminar', args=[activo.pk]))

        self.assertContains(pantalla, 'Dar de baja')
        self.assertNotContains(pantalla, 'Sí, eliminar')
