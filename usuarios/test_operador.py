"""
Qué alcanza el operador de bodega.

Su trabajo es mover inventario: registrar entradas, salidas, préstamos y
devoluciones. Para eso no necesita saber cuánto vale la bodega, y esa es
información de la empresa que no le toca — así que los reportes y las
tarjetas de valorización del Resumen quedan para el administrador y
contabilidad (RF-04).

Sí entra al Resumen: ahí ve qué hay que reponer y qué está prestado, que es
justo lo que su trabajo necesita.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo

REPORTES = (
    'indice_reportes', 'reporte_existencias', 'reporte_tecnica',
    'reporte_alertas', 'reporte_movimientos', 'reporte_prestamos',
)


class BaseOperador(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.operador = Usuario.objects.create_user(
            username='operador_permisos', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='BASCULA', modelo='B-1', bodega=cls.venta, precio=100,
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-TE001', nombre_producto='TALADRO',
            bodega=cls.tecnica, precio=100,
        )

    def setUp(self):
        self.client.force_login(self.operador)


class ElPermisoTests(TestCase):
    def test_lo_tienen_administrador_y_contabilidad(self):
        for rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.CONTABILIDAD):
            with self.subTest(rol=rol):
                self.assertTrue(Usuario(rol=rol).puede_ver_reportes)

    def test_no_lo_tienen_operador_ni_practicante(self):
        for rol in (Usuario.Rol.OPERADOR, Usuario.Rol.PRACTICANTE):
            with self.subTest(rol=rol):
                self.assertFalse(Usuario(rol=rol).puede_ver_reportes)


class NoEntraALosReportesTests(BaseOperador):
    def test_ninguno_de_los_seis(self):
        for nombre in REPORTES:
            with self.subTest(reporte=nombre):
                self.assertEqual(
                    self.client.get(reverse(nombre)).status_code, 403,
                    f'{nombre} quedó abierta al operador',
                )

    def test_tampoco_por_la_descarga_de_excel(self):
        """Cerrar la pantalla y dejar abierta su exportación no cierra nada."""
        for nombre in REPORTES[1:]:
            with self.subTest(reporte=nombre):
                respuesta = self.client.get(reverse(nombre), {'formato': 'excel'})
                self.assertEqual(respuesta.status_code, 403)

    def test_la_navegacion_no_le_ofrece_reportes(self):
        respuesta = self.client.get(reverse('resumen'))

        self.assertNotContains(respuesta, reverse('indice_reportes'))

    def test_al_administrador_si_se_la_ofrece(self):
        admin = Usuario.objects.create_user(
            username='admin_permisos', password='clave-de-prueba',
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.client.force_login(admin)

        respuesta = self.client.get(reverse('resumen'))

        self.assertContains(respuesta, reverse('indice_reportes'))

    def test_contabilidad_si_entra(self):
        contable = Usuario.objects.create_user(
            username='contable_permisos', password='clave-de-prueba',
            rol=Usuario.Rol.CONTABILIDAD,
        )
        self.client.force_login(contable)

        for nombre in REPORTES:
            with self.subTest(reporte=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class NoVeCuantoValeElInventarioTests(BaseOperador):
    def test_el_resumen_no_le_muestra_la_valorizacion(self):
        respuesta = self.client.get(reverse('resumen'))

        self.assertNotContains(respuesta, 'Valorización')

    def test_en_su_lugar_ve_el_tamaño_de_bodega_tecnica(self):
        respuesta = self.client.get(reverse('resumen'))

        self.assertContains(respuesta, 'Activos en Bodega Técnica')
        self.assertContains(respuesta, respuesta.context['total_activos'])

    def test_al_administrador_si_se_la_muestra(self):
        admin = Usuario.objects.create_user(
            username='admin_valor', password='clave-de-prueba',
            rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.client.force_login(admin)

        respuesta = self.client.get(reverse('resumen'))

        self.assertContains(respuesta, 'Valorización Bodega 1+2')
        self.assertContains(respuesta, 'Valorización Bodega Técnica')

    def test_no_le_ofrece_un_enlace_a_donde_no_puede_entrar(self):
        """
        El pie "Ver las 185 →" del panel de alertas lleva al reporte. Al
        operador le daría un 403, así que no se le ofrece.
        """
        for i in range(15):
            Articulo.objects.create(
                nombre_producto=f'EN ALERTA {i}', modelo=f'A-{i}',
                bodega=self.venta, precio=10, stock_actual=0,
            )

        respuesta = self.client.get(reverse('resumen'))

        self.assertNotContains(respuesta, 'Ver las')
        self.assertNotContains(respuesta, reverse('reporte_alertas'))


class SigueHaciendoSuTrabajoTests(BaseOperador):
    """Lo que el cambio NO debía romper."""

    def test_entra_al_resumen(self):
        self.assertEqual(self.client.get(reverse('resumen')).status_code, 200)

    def test_ve_que_hay_que_reponer(self):
        respuesta = self.client.get(reverse('resumen'))

        self.assertContains(respuesta, 'Alertas de stock — Bodega 1 y 2')
        self.assertContains(respuesta, 'Alertas de stock — Bodega Técnica')

    def test_ve_que_esta_prestado(self):
        respuesta = self.client.get(reverse('resumen'))

        self.assertContains(respuesta, 'Activos técnicos prestados')

    def test_sigue_moviendo_inventario(self):
        for nombre in ('movimientos_ventas', 'movimiento_ingreso', 'movimiento_salida',
                       'prestamos_tecnica', 'prestamo_nuevo'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_sigue_viendo_los_catalogos(self):
        for nombre in ('catalogo_articulos', 'catalogo_activos'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class AlcanceCompletoTests(BaseOperador):
    """
    Recorre TODAS las urls y comprueba una por una a cuáles llega el operador.

    Es la misma red que protege al practicante: acá está la lista de lo que sí
    debe alcanzar, y cualquier pantalla nueva que se le abra por descuido hace
    fallar esto.
    """

    PROHIBIDAS = set(REPORTES) | {
        # Administración: usuarios, categorías y proveedores son del admin.
        'lista_usuarios', 'usuario_nuevo', 'usuario_editar', 'usuario_eliminar',
        'lista_categorias', 'categoria_nueva', 'categoria_editar', 'categoria_eliminar',
        'lista_proveedores', 'proveedor_nuevo', 'proveedor_editar', 'proveedor_eliminar',
        # El catálogo lo captura el practicante o el admin, no el operador.
        'articulo_nuevo', 'articulo_editar', 'articulo_eliminar',
        'activo_nuevo', 'activo_editar', 'activo_eliminar',
        # 'activo_baja' NO va aquí: dar de baja es un movimiento, no editar
        # el catálogo, y es lo único que baja la existencia de Bodega
        # Técnica. La vista lo dice con @rol_requerido(ADMINISTRADOR, OPERADOR).
        'carga_masiva_subir', 'carga_masiva_mapear', 'carga_masiva_cancelar',
        'carga_masiva_subir_tecnica', 'carga_masiva_mapear_tecnica',
        'carga_masiva_cancelar_tecnica',
    }

    def urls_a_probar(self):
        from django.urls import get_resolver

        argumentos = {'pk': self.articulo.pk, 'folio': 'ING-0001'}
        for patron in get_resolver().url_patterns:
            for sub in getattr(patron, 'url_patterns', [patron]):
                nombre = getattr(sub, 'name', None)
                if not nombre or nombre in ('login', 'logout'):
                    continue
                try:
                    yield nombre, reverse(nombre)
                except Exception:
                    for valor in argumentos.values():
                        try:
                            yield nombre, reverse(nombre, args=[valor])
                            break
                        except Exception:
                            continue

    def test_no_alcanza_ninguna_de_las_prohibidas(self):
        alcanzadas = set()

        for nombre, url in self.urls_a_probar():
            if self.client.get(url).status_code != 403:
                alcanzadas.add(nombre)

        de_mas = alcanzadas & self.PROHIBIDAS
        self.assertEqual(
            de_mas, set(),
            'El operador llega a pantallas que no le tocan. Si es a propósito, '
            'sacalas de PROHIBIDAS; si no, les falta el decorador de rol: '
            f'{sorted(de_mas)}',
        )
        self.assertTrue(alcanzadas, 'la prueba no está probando nada')
