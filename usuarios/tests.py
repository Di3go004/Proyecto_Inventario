"""
Pruebas de roles y permisos (RF-01 a RF-04).

Verifican lo que hasta ahora solo estaba escrito en el plan: que
contabilidad de verdad no pueda modificar nada, que el operador no toque el
catálogo, y que sin sesión no se entre a ningún lado.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo


class BasePermisos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega_venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.bodega_tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)

        cls.admin = Usuario.objects.create_user(
            username='admin_prueba', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='operador_prueba', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contabilidad = Usuario.objects.create_user(
            username='contabilidad_prueba', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )

        cls.articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='BP-100', capacidad='300kg', bodega=cls.bodega_venta,
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-ET001', nombre_producto='Rotomartillo', bodega=cls.bodega_tecnica,
        )

    def entrar_como(self, usuario):
        self.client.force_login(usuario)


class RolesDelModeloTests(BasePermisos):
    """RF-01: cada usuario tiene exactamente un rol y sus atajos funcionan."""

    def test_atajos_de_rol(self):
        self.assertTrue(self.admin.es_administrador)
        self.assertFalse(self.admin.es_operador)
        self.assertTrue(self.operador.es_operador)
        self.assertTrue(self.contabilidad.es_contabilidad)

    def test_solo_contabilidad_es_de_solo_lectura(self):
        """RF-04: contabilidad no edita; los otros dos sí, cada uno en lo suyo."""
        self.assertTrue(self.admin.puede_editar)
        self.assertTrue(self.operador.puede_editar)
        self.assertFalse(self.contabilidad.puede_editar)

    def test_el_rol_por_defecto_es_el_menos_privilegiado(self):
        nuevo = Usuario.objects.create_user(username='sin_rol_explicito', password='clave-de-prueba')
        self.assertEqual(nuevo.rol, Usuario.Rol.OPERADOR)
        self.assertFalse(nuevo.es_administrador)


class AccesoSinSesionTests(BasePermisos):
    """RNF-03: ninguna pantalla del sistema es anónima."""

    def test_las_pantallas_piden_iniciar_sesion(self):
        for nombre in ['resumen', 'catalogo_articulos', 'catalogo_activos']:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn('/login/', respuesta.url)


class ContabilidadSoloLecturaTests(BasePermisos):
    """RF-04: el rol contabilidad ve todo pero no puede modificar nada."""

    def setUp(self):
        self.entrar_como(self.contabilidad)

    def test_puede_ver_los_catalogos(self):
        for nombre in ['resumen', 'catalogo_articulos', 'catalogo_activos']:
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_puede_ver_las_fichas_de_detalle(self):
        self.assertEqual(
            self.client.get(reverse('articulo_detalle', args=[self.articulo.pk])).status_code, 200,
        )
        self.assertEqual(
            self.client.get(reverse('activo_detalle', args=[self.activo.pk])).status_code, 200,
        )

    def test_no_puede_crear_editar_ni_eliminar(self):
        prohibidas = [
            reverse('articulo_nuevo'),
            reverse('articulo_editar', args=[self.articulo.pk]),
            reverse('articulo_eliminar', args=[self.articulo.pk]),
            reverse('activo_nuevo'),
            reverse('activo_editar', args=[self.activo.pk]),
            reverse('activo_eliminar', args=[self.activo.pk]),
        ]
        for url in prohibidas:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_no_puede_usar_la_carga_masiva(self):
        for nombre in ['carga_masiva_subir', 'carga_masiva_subir_tecnica']:
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_puede_eliminar_ni_mandando_el_formulario_directo(self):
        """El bloqueo no depende de que el botón esté oculto en la pantalla."""
        self.client.post(reverse('articulo_eliminar', args=[self.articulo.pk]))
        self.assertTrue(Articulo.objects.filter(pk=self.articulo.pk).exists())


class OperadorTests(BasePermisos):
    """RF-03: el operador registra movimientos, pero no administra el catálogo."""

    def setUp(self):
        self.entrar_como(self.operador)

    def test_puede_ver_los_catalogos(self):
        self.assertEqual(self.client.get(reverse('catalogo_articulos')).status_code, 200)
        self.assertEqual(self.client.get(reverse('catalogo_activos')).status_code, 200)

    def test_no_puede_administrar_el_catalogo(self):
        for url in [reverse('articulo_nuevo'), reverse('activo_nuevo')]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class AdministradorTests(BasePermisos):
    """RF-02: el administrador sí tiene acceso completo al catálogo."""

    def setUp(self):
        self.entrar_como(self.admin)

    def test_puede_abrir_las_pantallas_de_administracion(self):
        permitidas = [
            reverse('articulo_nuevo'),
            reverse('articulo_editar', args=[self.articulo.pk]),
            reverse('activo_nuevo'),
            reverse('carga_masiva_subir'),
            reverse('carga_masiva_subir_tecnica'),
        ]
        for url in permitidas:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_puede_eliminar_un_articulo_sin_movimientos(self):
        articulo = Articulo.objects.create(
            nombre_producto='Temporal', modelo='TMP-1', bodega=self.bodega_venta,
        )
        self.client.post(reverse('articulo_eliminar', args=[articulo.pk]))
        self.assertFalse(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_no_puede_eliminar_un_articulo_con_historial(self):
        """El historial de movimientos se protege: se descontinúa, no se borra."""
        from ventas.models import MovimientoVenta

        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL,
            cantidad=5, usuario=self.admin,
        )
        respuesta = self.client.post(reverse('articulo_eliminar', args=[self.articulo.pk]), follow=True)

        self.assertTrue(Articulo.objects.filter(pk=self.articulo.pk).exists())
        self.assertContains(respuesta, 'No se puede eliminar')


class EnlaceAlPanelDeAdminTests(BasePermisos):
    """
    El panel /admin/ de Django exige is_staff, que no es lo mismo que el rol
    de la aplicación. Si el enlace se muestra a quien no puede entrar, lo
    único que consigue es mandarlo a un login que nunca va a poder pasar.
    """

    ENLACE = 'panel de administración'

    def test_no_se_le_ofrece_a_quien_no_puede_entrar(self):
        for usuario in (self.operador, self.contabilidad):
            with self.subTest(rol=usuario.rol):
                self.assertFalse(usuario.is_staff)
                self.client.force_login(usuario)
                self.assertNotContains(self.client.get(reverse('resumen')), self.ENLACE)

    def test_se_le_ofrece_a_quien_si_puede(self):
        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('resumen')), self.ENLACE)
