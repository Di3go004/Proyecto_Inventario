"""
Pruebas de la pantalla de usuarios (RF-01).

Lo que más importa acá no es crear usuarios —eso es un formulario más— sino
las dos formas de romper el sistema desde esta pantalla: que un administrador
se quite a sí mismo el acceso y quede nadie adentro, y que se borre a alguien
que ya registró movimientos, dejando el historial sin autor.
"""

import re

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.models import Activo, PrestamoActivo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BaseGestion(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            username='jefe', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.otro_admin = Usuario.objects.create_user(
            username='jefe2', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='bodeguero', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='contable', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        base = {
            'username': 'nuevo', 'first_name': 'Ana', 'last_name': 'López',
            'rol': Usuario.Rol.OPERADOR, 'is_active': 'on',
            'generar': 'on', 'clave': '',
        }
        base.update(extra)
        return {k: v for k, v in base.items() if v is not None}

    def clave_del_mensaje(self, respuesta):
        """El sistema muestra la contraseña generada una sola vez, en un aviso."""
        avisos = [str(m) for m in respuesta.context['messages']]
        for aviso in avisos:
            encontrado = re.search(r'Contraseña de "[^"]+": (\S+) —', aviso)
            if encontrado:
                return encontrado.group(1)
        return None


class PermisosTests(BaseGestion):
    def test_solo_el_administrador_entra(self):
        for usuario in (self.operador, self.contable):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(reverse('lista_usuarios')).status_code, 403)
                self.assertEqual(self.client.get(reverse('usuario_nuevo')).status_code, 403)

    def test_el_operador_no_puede_crear_usuarios_por_post(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Usuario.objects.filter(username='nuevo').exists())

    def test_el_administrador_ve_el_enlace_en_el_menu(self):
        self.assertContains(self.client.get(reverse('resumen')), reverse('lista_usuarios'))

    def test_los_demas_no_ven_el_enlace(self):
        self.client.force_login(self.operador)
        self.assertNotContains(self.client.get(reverse('resumen')), reverse('lista_usuarios'))


class CrearTests(BaseGestion):
    def test_crea_con_clave_generada_y_esa_clave_sirve(self):
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos(), follow=True)

        creado = Usuario.objects.get(username='nuevo')
        clave = self.clave_del_mensaje(respuesta)
        self.assertIsNotNone(clave, 'la contraseña generada debe mostrarse una vez')
        self.assertTrue(creado.check_password(clave))
        self.assertEqual(creado.rol, Usuario.Rol.OPERADOR)
        self.assertEqual(creado.get_full_name(), 'Ana López')

    def test_crea_con_clave_escrita(self):
        self.client.post(reverse('usuario_nuevo'), self.datos(generar=None, clave='UnaClaveLarga.99'))

        self.assertTrue(Usuario.objects.get(username='nuevo').check_password('UnaClaveLarga.99'))

    def test_rechaza_una_clave_debil(self):
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos(generar=None, clave='12345'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username='nuevo').exists())

    def test_exige_alguna_clave(self):
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos(generar=None, clave=''))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username='nuevo').exists())

    def test_no_repite_un_nombre_de_usuario(self):
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos(username='bodeguero'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.filter(username='bodeguero').count(), 1)


class RolYPanelTests(BaseGestion):
    """El rol de la aplicación manda sobre el permiso del panel /admin/."""

    def test_el_administrador_recibe_acceso_al_panel(self):
        self.client.post(reverse('usuario_nuevo'), self.datos(rol=Usuario.Rol.ADMINISTRADOR))
        self.assertTrue(Usuario.objects.get(username='nuevo').is_staff)

    def test_los_demas_roles_no(self):
        for rol in (Usuario.Rol.OPERADOR, Usuario.Rol.CONTABILIDAD):
            with self.subTest(rol=rol):
                Usuario.objects.filter(username='nuevo').delete()
                self.client.post(reverse('usuario_nuevo'), self.datos(rol=rol))
                self.assertFalse(Usuario.objects.get(username='nuevo').is_staff)

    def test_bajarle_el_rol_le_quita_el_acceso_al_panel(self):
        self.client.post(reverse('usuario_editar', args=[self.otro_admin.pk]), {
            'username': 'jefe2', 'first_name': '', 'last_name': '',
            'rol': Usuario.Rol.OPERADOR, 'is_active': 'on',
        })

        self.otro_admin.refresh_from_db()
        self.assertEqual(self.otro_admin.rol, Usuario.Rol.OPERADOR)
        self.assertFalse(self.otro_admin.is_staff)


class NoQuedarseFueraTests(BaseGestion):
    """Las dos formas de dejarse a uno mismo sin acceso al sistema."""

    def editar_al_admin(self, **cambios):
        datos = {
            'username': 'jefe', 'first_name': '', 'last_name': '',
            'rol': Usuario.Rol.ADMINISTRADOR, 'is_active': 'on',
        }
        datos.update(cambios)
        # Una casilla desmarcada no se envía: se quita la clave, no se manda
        # vacía, que es como lo hace el navegador de verdad.
        datos = {clave: valor for clave, valor in datos.items() if valor is not None}
        return self.client.post(reverse('usuario_editar', args=[self.admin.pk]), datos)

    def test_no_puede_quitarse_a_si_mismo_el_rol(self):
        respuesta = self.editar_al_admin(rol=Usuario.Rol.OPERADOR)

        self.admin.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.admin.rol, Usuario.Rol.ADMINISTRADOR)
        self.assertContains(respuesta, 'No puedes quitarte a ti mismo')

    def test_no_puede_desactivarse_a_si_mismo(self):
        respuesta = self.editar_al_admin(is_active=None)

        self.admin.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self.admin.is_active)

    def test_no_puede_eliminarse_a_si_mismo(self):
        respuesta = self.client.post(reverse('usuario_eliminar', args=[self.admin.pk]))

        self.assertRedirects(respuesta, reverse('lista_usuarios'))
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())

    def test_no_deja_el_sistema_sin_ningun_administrador(self):
        """Con un solo admin activo, no se le puede bajar el rol al otro."""
        self.otro_admin.delete()
        self.client.force_login(self.admin)

        # Otro administrador intentaría bajarle el rol al único que queda.
        tercero = Usuario.objects.create_user(
            username='jefe3', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        self.client.force_login(tercero)
        respuesta = self.client.post(reverse('usuario_editar', args=[tercero.pk]), {
            'username': 'jefe3', 'first_name': '', 'last_name': '',
            'rol': Usuario.Rol.OPERADOR, 'is_active': 'on',
        })

        tercero.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(tercero.rol, Usuario.Rol.ADMINISTRADOR)


class QuitarAccesoTests(BaseGestion):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='BP-1', capacidad='1kg', bodega=bodega,
        )
        MovimientoVenta.objects.create(
            folio='ING-00001', tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            articulo=articulo, cantidad=5, fecha=timezone.now(), usuario=cls.operador,
        )

    def test_no_borra_a_quien_ya_registro_movimientos(self):
        respuesta = self.client.post(reverse('usuario_eliminar', args=[self.operador.pk]), follow=True)

        self.assertTrue(Usuario.objects.filter(pk=self.operador.pk).exists())
        self.assertContains(respuesta, 'tiene registros a su nombre')

    def test_la_pantalla_explica_por_que_y_ofrece_desactivar(self):
        pantalla = self.client.get(reverse('usuario_eliminar', args=[self.operador.pk]))

        self.assertContains(pantalla, '1 registro(s)')
        self.assertContains(pantalla, 'Desactivar el acceso')

    def test_desactivar_conserva_el_historial(self):
        self.client.post(
            reverse('usuario_eliminar', args=[self.operador.pk]), {'accion': 'desactivar'},
        )

        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)
        self.assertEqual(MovimientoVenta.objects.filter(usuario=self.operador).count(), 1)

    def test_un_usuario_desactivado_ya_no_entra(self):
        self.client.post(
            reverse('usuario_eliminar', args=[self.operador.pk]), {'accion': 'desactivar'},
        )
        self.client.logout()

        entro = self.client.login(username='bodeguero', password='clave-de-prueba')
        self.assertFalse(entro)

    def test_si_nunca_registro_nada_si_se_borra(self):
        self.client.post(reverse('usuario_eliminar', args=[self.contable.pk]))
        self.assertFalse(Usuario.objects.filter(pk=self.contable.pk).exists())


class RestablecerClaveTests(BaseGestion):
    def test_cambia_la_clave_y_la_muestra_una_vez(self):
        respuesta = self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]),
            {'generar': 'on', 'clave': ''}, follow=True,
        )

        clave = self.clave_del_mensaje(respuesta)
        self.operador.refresh_from_db()
        self.assertIsNotNone(clave)
        self.assertTrue(self.operador.check_password(clave))

    def test_la_clave_anterior_deja_de_servir(self):
        self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]), {'generar': 'on', 'clave': ''},
        )

        self.operador.refresh_from_db()
        self.assertFalse(self.operador.check_password('clave-de-prueba'))

    def test_no_cambia_el_rol_por_accidente(self):
        self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]), {'generar': 'on', 'clave': ''},
        )

        self.operador.refresh_from_db()
        self.assertEqual(self.operador.rol, Usuario.Rol.OPERADOR)


class ListadoTests(BaseGestion):
    def test_muestra_cuantos_registros_tiene_cada_quien(self):
        bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        activo = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='Taladro', bodega=bodega,
        )
        PrestamoActivo.objects.create(
            activo=activo, solicitante='Alguien', estado_al_salir=Activo.Estado.BUEN_ESTADO,
            usuario=self.operador,
        )

        respuesta = self.client.get(reverse('lista_usuarios'))
        fila = next(u for u in respuesta.context['usuarios'] if u.pk == self.operador.pk)

        self.assertEqual(fila.prestamos, 1)

    def test_filtra_por_rol(self):
        respuesta = self.client.get(reverse('lista_usuarios'), {'rol': Usuario.Rol.ADMINISTRADOR})
        roles = {u.rol for u in respuesta.context['usuarios']}

        self.assertEqual(roles, {Usuario.Rol.ADMINISTRADOR})

    def test_busca_por_nombre(self):
        Usuario.objects.filter(pk=self.operador.pk).update(first_name='Marisol')

        respuesta = self.client.get(reverse('lista_usuarios'), {'q': 'Marisol'})

        self.assertEqual([u.pk for u in respuesta.context['usuarios']], [self.operador.pk])


class ClaveEscritaTests(BaseGestion):
    """
    Regresión del bloqueo real: la casilla "Generar" viene marcada, y antes
    pisaba en silencio la contraseña que la persona hubiera escrito. El
    resultado era que ponías la tuya, se guardaba otra al azar, y te quedabas
    sin poder entrar sin entender por qué.
    """

    ESCRITA = 'LaQueYoEscribi.2026'

    def test_al_crear_gana_la_escrita_aunque_generar_siga_marcado(self):
        self.client.post(reverse('usuario_nuevo'), self.datos(generar='on', clave=self.ESCRITA))

        creado = Usuario.objects.get(username='nuevo')
        self.assertTrue(
            creado.check_password(self.ESCRITA),
            'lo que la persona escribió es lo que tiene que quedar guardado',
        )

    def test_al_restablecer_gana_la_escrita_aunque_generar_siga_marcado(self):
        self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]),
            {'generar': 'on', 'clave': self.ESCRITA},
        )

        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password(self.ESCRITA))

    def test_con_el_campo_vacio_si_se_genera(self):
        respuesta = self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]),
            {'generar': 'on', 'clave': ''}, follow=True,
        )

        clave = self.clave_del_mensaje(respuesta)
        self.operador.refresh_from_db()
        self.assertIsNotNone(clave)
        self.assertTrue(self.operador.check_password(clave))

    def test_la_escrita_no_se_anuncia_en_pantalla(self):
        """Solo la generada se muestra; la que la persona eligió ya la sabe."""
        respuesta = self.client.post(
            reverse('usuario_clave', args=[self.operador.pk]),
            {'generar': 'on', 'clave': self.ESCRITA}, follow=True,
        )

        avisos = ' '.join(str(m) for m in respuesta.context['messages'])
        self.assertNotIn(self.ESCRITA, avisos)


class NombreDeUsuarioTests(BaseGestion):
    """
    En tablets el teclado capitaliza la primera letra, y así se creó un
    "Karla" que después nadie lograba escribir igual para entrar.
    """

    def test_se_guarda_en_minusculas(self):
        self.client.post(reverse('usuario_nuevo'), self.datos(username='Karla'))

        self.assertTrue(Usuario.objects.filter(username='karla').exists())
        self.assertFalse(Usuario.objects.filter(username='Karla').exists())

    def test_no_deja_dos_que_solo_difieran_en_mayusculas(self):
        respuesta = self.client.post(reverse('usuario_nuevo'), self.datos(username='BODEGUERO'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.filter(username__iexact='bodeguero').count(), 1)

    def test_se_le_quitan_los_espacios_de_los_lados(self):
        self.client.post(reverse('usuario_nuevo'), self.datos(username='  ana  '))

        self.assertTrue(Usuario.objects.filter(username='ana').exists())


class EntrarSinDistinguirMayusculasTests(TestCase):
    """El nombre de usuario da igual cómo se escriba; la contraseña no."""

    @classmethod
    def setUpTestData(cls):
        cls.clave = 'UnaClaveLarga.2026'
        cls.usuario = Usuario.objects.create_user(
            username='karla', password=cls.clave, rol=Usuario.Rol.OPERADOR,
        )

    def test_entra_escribiendo_el_usuario_de_cualquier_forma(self):
        for escrito in ('karla', 'Karla', 'KARLA', 'kArLa'):
            with self.subTest(escrito=escrito):
                self.assertTrue(self.client.login(username=escrito, password=self.clave))
                self.client.logout()

    def test_la_contrasena_si_distingue_mayusculas(self):
        self.assertFalse(self.client.login(username='karla', password=self.clave.upper()))

    def test_un_usuario_que_no_existe_no_entra(self):
        self.assertFalse(self.client.login(username='nadie', password=self.clave))

    def test_un_usuario_desactivado_no_entra_ni_con_la_clave_correcta(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertFalse(self.client.login(username='KARLA', password=self.clave))
