"""
Pruebas de roles y permisos (RF-01 a RF-04).

Verifican lo que hasta ahora solo estaba escrito en el plan: que
contabilidad de verdad no pueda modificar nada, que el operador no toque el
catálogo, y que sin sesión no se entre a ningún lado.
"""

import re

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo

# Códigos ANSI de color, para poder leer la salida de un comando venga
# coloreada o no.
ESCAPES_DE_COLOR = re.compile(chr(27) + r'\[[0-9;]*m')


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
        """
        El historial de movimientos se protege: se descontinúa, no se borra.

        Ojo con el tipo de movimiento: el "ajuste / saldo inicial" que crea la
        carga masiva sí permite borrar (no es historial, es el conteo de
        arranque). Lo que bloquea es un movimiento real, como este ingreso.
        Ver ventas/test_eliminar.py para esa distinción en detalle.
        """
        from ventas.models import MovimientoVenta

        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.REPUESTOS,
            cantidad=5, usuario=self.admin,
        )
        respuesta = self.client.post(reverse('articulo_eliminar', args=[self.articulo.pk]), follow=True)

        self.assertTrue(Articulo.objects.filter(pk=self.articulo.pk).exists())
        self.assertContains(respuesta, 'No se puede eliminar')


class CambiarClaveTests(BasePermisos):
    """
    El comando `cambiar_clave` es la única forma de rotar una contraseña sin
    entrar al panel /admin/, al que solo llega el administrador.
    """

    def ejecutar(self, *args, **opciones):
        from io import StringIO
        from django.core.management import call_command
        salida = StringIO()
        call_command('cambiar_clave', *args, stdout=salida, **opciones)
        return salida.getvalue()

    def clave_impresa(self, salida):
        """
        Saca del texto del comando la contraseña que imprimió.

        Se busca por la FORMA de la contraseña, no por la sangría. Antes se
        tomaba "la primera línea que empieza con cuatro espacios", y eso
        ataba la prueba al formato exacto del mensaje: cualquier cambio de
        estilo —o un código de color delante— la rompía con un StopIteration
        pelado, que no dice qué salió mal ni deja ver la salida real.
        """
        from usuarios.claves import ALFABETO, LARGO_POR_DEFECTO

        # Se quitan los códigos de color por si el comando corre con ellos.
        limpio = re.sub(ESCAPES_DE_COLOR, "", salida)
        patron = re.compile("^[" + re.escape(ALFABETO) + "]{" + str(LARGO_POR_DEFECTO) + ",}$")
        candidatas = [l.strip() for l in limpio.splitlines() if patron.match(l.strip())]

        self.assertEqual(
            len(candidatas), 1,
            "El comando tiene que imprimir la contraseña generada exactamente "
            "una vez. Esto fue lo que imprimió: " + repr(salida),
        )
        return candidatas[0]

    def test_la_clave_generada_sirve_para_entrar(self):
        salida = self.ejecutar(self.operador.username, generar=True)

        # El comando la imprime una sola vez; es la única copia que queda.
        generada = self.clave_impresa(salida)
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password(generada))
        self.assertGreaterEqual(len(generada), 16)

    def test_la_clave_anterior_deja_de_servir(self):
        self.operador.set_password('la-vieja-de-antes')
        self.operador.save()

        self.ejecutar(self.operador.username, generar=True)

        self.operador.refresh_from_db()
        self.assertFalse(self.operador.check_password('la-vieja-de-antes'))

    def test_rechaza_una_clave_debil(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as caso:
            self.ejecutar(self.operador.username, password='12345')

        self.assertIn('Contraseña rechazada', str(caso.exception))

    def test_avisa_si_el_usuario_no_existe(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as caso:
            self.ejecutar('nadie', generar=True)

        self.assertIn('No existe', str(caso.exception))

    def test_no_acepta_generar_y_password_a_la_vez(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.ejecutar(self.operador.username, password='UnaClaveLarga123', generar=True)
