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
from tecnica.models import Activo, PrestamoActivo
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
    def test_un_activo_no_puede_tener_dos_prestamos_abiertos(self):
        """RF-07: lo garantiza la base de datos, no solo la pantalla."""
        activo = self.crear_activo()
        self.prestar(activo)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.prestar(activo, solicitante='Otra persona')

    def test_se_puede_volver_a_prestar_despues_de_devolver(self):
        activo = self.crear_activo()
        primero = self.prestar(activo)
        primero.fecha_regreso = timezone.now()
        primero.estado_al_regresar = Activo.Estado.BUEN_ESTADO
        primero.save()

        segundo = self.prestar(activo, solicitante='Jesus Lorenzana')
        self.assertIsNone(segundo.fecha_regreso)
        self.assertTrue(activo.esta_prestado)

    def test_un_activo_de_baja_no_se_puede_prestar(self):
        """RF-12: 'de baja' lo saca de circulación."""
        activo = self.crear_activo(estado=Activo.Estado.DE_BAJA)
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
    En Bodega Técnica la carga masiva no crea préstamos, así que lo único que
    puede bloquear el borrado son préstamos de verdad.
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

    def test_darlo_de_baja_tampoco_lo_habilita(self):
        activo = self.crear()
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.admin,
        )
        Activo.objects.filter(pk=activo.pk).update(estado=Activo.Estado.DE_BAJA)

        self.client.post(reverse('activo_eliminar', args=[activo.pk]))

        self.assertTrue(Activo.objects.filter(pk=activo.pk).exists())

    def test_la_pantalla_manda_a_darlo_de_baja(self):
        activo = self.crear()
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien',
            estado_al_salir=Activo.Estado.BUEN_ESTADO, usuario=self.admin,
        )

        pantalla = self.client.get(reverse('activo_eliminar', args=[activo.pk]))

        self.assertContains(pantalla, 'De baja')
        self.assertNotContains(pantalla, 'Sí, eliminar')
