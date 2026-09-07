"""
Quién digitó una baja o un ajuste, en la lista de Entradas y salidas.

La columna "Solicitado por" sale del papel: es quién pidió el movimiento. Las
bajas y los ajustes de Bodega Técnica no llevan boleta, así que salían con una
raya y en esa pantalla no quedaba rastro de quién los hizo — que es justo lo
que hay que poder responder de una baja de inventario.

El dato siempre estuvo guardado (el usuario es obligatorio en los dos modelos
de movimiento); lo que faltaba era mostrarlo. Se muestra **solo** en esas
filas y con su propia etiqueta: si se mezclara con lo del papel en la misma
columna, esta significaría una cosa en unas filas y otra en otras.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas.documentos import filas_de_historial
from ventas.models import Articulo, MovimientoVenta


class BaseRegistradoPor(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_reg', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
            first_name='Karla', last_name='Méndez',
        )
        cls.operadora = Usuario.objects.create_user(
            username='operadora_reg', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
            first_name='Ana', last_name='Ruiz',
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='BASCULA', modelo='B-1', bodega=cls.venta, precio=100,
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-TE001', nombre_producto='GALON DE PINTURA',
            bodega=cls.tecnica, precio=100,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def ingreso_con_boleta(self, solicitado_por='Diego González'):
        return MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            cantidad=5, usuario=self.admin, folio='ING-00001',
            solicitado_por=solicitado_por,
        )

    def ajuste(self, usuario=None):
        return MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.AJUSTE, activo=self.activo, cantidad=10,
            usuario=usuario or self.admin, observacion='Saldo inicial al crear el activo.',
        )

    def baja(self, usuario=None):
        self.ajuste()
        return MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.BAJA, activo=self.activo, cantidad=1,
            usuario=usuario or self.operadora, motivo=MovimientoActivo.Motivo.CONSUMIDO,
            observacion='SE ACABO LA PINTURA',
        )

    def fila_de(self, movimiento):
        for fila in filas_de_historial():
            if fila.movimiento.pk == movimiento.pk and type(fila.movimiento) is type(movimiento):
                return fila
        self.fail('el movimiento no salió en el historial')


class ElDatoYaEstabaGuardadoTests(BaseRegistradoPor):
    """No hubo que agregar ningún campo: solo mostrarlo."""

    def test_el_usuario_es_obligatorio_en_los_dos_modelos(self):
        for modelo in (MovimientoVenta, MovimientoActivo):
            with self.subTest(modelo=modelo.__name__):
                self.assertFalse(modelo._meta.get_field('usuario').null)

    def test_una_baja_guarda_quien_la_hizo(self):
        self.assertEqual(self.baja().usuario, self.operadora)

    def test_un_ajuste_guarda_quien_lo_hizo(self):
        self.assertEqual(self.ajuste().usuario, self.admin)


class SoloEnLasFilasSinBoletaTests(BaseRegistradoPor):
    def test_una_baja_lo_trae(self):
        baja = self.baja()

        self.assertEqual(self.fila_de(baja).registrado_por, self.operadora)

    def test_un_ajuste_lo_trae(self):
        ajuste = self.ajuste()

        self.assertEqual(self.fila_de(ajuste).registrado_por, self.admin)

    def test_un_movimiento_con_boleta_NO_lo_trae(self):
        """
        Ahí el dato que importa es el del papel. Mostrar los dos en la misma
        columna la haría significar una cosa en unas filas y otra en otras.
        """
        ingreso = self.ingreso_con_boleta()

        fila = self.fila_de(ingreso)
        self.assertIsNone(fila.registrado_por)
        self.assertEqual(fila.solicitado_por, 'Diego González')

    def test_un_ingreso_de_tecnica_con_boleta_tampoco(self):
        ingreso = MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.INGRESO, activo=self.activo, cantidad=2,
            usuario=self.admin, folio='ING-00002', solicitado_por='Diego González',
        )

        self.assertIsNone(self.fila_de(ingreso).registrado_por)


class EnLaPantallaTests(BaseRegistradoPor):
    def pantalla(self):
        return self.client.get(reverse('movimientos_ventas'))

    def test_muestra_el_nombre_de_quien_dio_de_baja(self):
        self.baja()

        respuesta = self.pantalla()

        self.assertContains(respuesta, 'Ana Ruiz')

    def test_lo_muestra_con_su_etiqueta(self):
        """
        Sin la etiqueta, el nombre quedaría bajo "Solicitado por" y se leería
        como que esa persona pidió la baja, cuando lo que hizo fue digitarla.
        """
        self.baja()

        respuesta = self.pantalla()

        self.assertContains(respuesta, 'Registrado por')

    def test_en_las_filas_con_boleta_sigue_saliendo_lo_del_papel(self):
        self.ingreso_con_boleta()

        respuesta = self.pantalla()

        self.assertContains(respuesta, 'Diego González')
        self.assertNotContains(respuesta, 'Registrado por')

    def test_usa_el_nombre_completo_y_no_el_de_usuario(self):
        self.baja()

        respuesta = self.pantalla()

        self.assertContains(respuesta, 'Ana Ruiz')
        self.assertNotContains(respuesta, 'operadora_reg')

    def test_si_no_tiene_nombre_completo_usa_el_de_usuario(self):
        sin_nombre = Usuario.objects.create_user(
            username='sin_nombre', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        self.baja(usuario=sin_nombre)

        respuesta = self.pantalla()

        self.assertContains(respuesta, 'sin_nombre')


class SinConsultasDeMasTests(BaseRegistradoPor):
    def test_no_dispara_una_consulta_por_fila(self):
        """
        El usuario ya venía en el select_related del historial. Que se siga
        trayendo de ahí y no una vez por movimiento.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for _ in range(10):
            MovimientoActivo.objects.create(
                tipo=MovimientoActivo.Tipo.AJUSTE, activo=self.activo, cantidad=1,
                usuario=self.admin, observacion='ajuste',
            )

        with CaptureQueriesContext(connection) as consultas:
            for fila in filas_de_historial():
                _ = fila.registrado_por and fila.registrado_por.get_full_name()

        self.assertLessEqual(
            len(consultas.captured_queries), 4,
            f'{len(consultas.captured_queries)} consultas: falta el select_related',
        )
