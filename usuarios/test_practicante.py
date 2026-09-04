"""
Pruebas del rol practicante (RF-01/RF-04).

Se encarga de dejar el catálogo bien capturado —producto por producto— y de
nada más: no mueve inventario, no ve reportes y no ve la valorización de las
bodegas.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega, Categoria, Proveedor
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BasePracticante(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.practicante = Usuario.objects.create_user(
            username='practicante_prueba', password='clave-de-prueba',
            rol=Usuario.Rol.PRACTICANTE,
        )
        cls.admin = Usuario.objects.create_user(
            username='admin_prac', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=cls.bodega,
        )
        cls.activo = Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='Taladro', bodega=cls.tecnica,
        )

    def setUp(self):
        self.client.force_login(self.practicante)


class PermisosDelModeloTests(BasePracticante):
    def test_puede_editar_el_catalogo(self):
        self.assertTrue(self.practicante.puede_editar_catalogo)

    def test_no_puede_mover_inventario(self):
        """
        `puede_editar` decide los botones de entradas, salidas, préstamos y
        devoluciones. Antes significaba "cualquiera menos contabilidad", y el
        practicante habría entrado por ahí.
        """
        self.assertFalse(self.practicante.puede_editar)

    def test_los_otros_roles_no_cambiaron(self):
        operador = Usuario.objects.create_user(
            username='op_prac', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        contable = Usuario.objects.create_user(
            username='cont_prac', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )

        self.assertTrue(operador.puede_editar)
        self.assertFalse(operador.puede_editar_catalogo)
        self.assertFalse(contable.puede_editar)
        self.assertFalse(contable.puede_editar_catalogo)
        self.assertTrue(self.admin.puede_editar)
        self.assertTrue(self.admin.puede_editar_catalogo)

    def test_no_entra_al_panel_de_django(self):
        self.assertFalse(self.practicante.is_staff)


class AlcanceCompletoTests(BasePracticante):
    """
    Recorre TODAS las urls del sistema y comprueba una por una a cuáles llega
    el practicante.

    Es la prueba que de verdad protege el rol: las pantallas se cierran con
    una lista de roles bloqueados, así que una vista nueva queda abierta por
    descuido. Acá está la lista de lo que sí puede alcanzar, y cualquier otra
    cosa que se le abra hace fallar esto.
    """

    # Lo único que el practicante debe alcanzar: los dos catálogos y el
    # crear/editar/eliminar de cada uno.
    PERMITIDAS = {
        'catalogo_articulos', 'articulo_detalle', 'articulo_nuevo',
        'articulo_editar', 'articulo_eliminar',
        'catalogo_activos', 'activo_detalle', 'activo_nuevo',
        'activo_editar', 'activo_eliminar',
        # El resumen no se le niega: se le redirige al catálogo, porque es la
        # pantalla a la que cae todo el mundo al iniciar sesión.
        'resumen',
        # Sugerencias del buscador: no son una pantalla y solo devuelven lo
        # que ya ve en el catálogo.
        'api_buscar_articulos', 'api_buscar_activos',
    }

    def urls_a_probar(self):
        """(nombre, url) de cada vista con GET, resolviendo los parámetros."""
        from django.urls import get_resolver

        argumentos = {
            'pk': self.articulo.pk,
            'folio': 'ING-0001',
        }
        for patron in get_resolver().url_patterns:
            for sub in getattr(patron, 'url_patterns', [patron]):
                nombre = getattr(sub, 'name', None)
                if not nombre or nombre in ('login', 'logout'):
                    continue
                try:
                    yield nombre, reverse(nombre)
                except Exception:
                    for clave, valor in argumentos.items():
                        try:
                            yield nombre, reverse(nombre, args=[valor])
                            break
                        except Exception:
                            continue

    def test_solo_alcanza_el_catalogo(self):
        alcanzadas, negadas = set(), set()

        for nombre, url in self.urls_a_probar():
            respuesta = self.client.get(url)
            if respuesta.status_code == 403:
                negadas.add(nombre)
            else:
                alcanzadas.add(nombre)

        de_mas = alcanzadas - self.PERMITIDAS
        self.assertEqual(
            de_mas, set(),
            'El practicante llega a pantallas que no le tocan. Si es a '
            'propósito, agregalas a PERMITIDAS; si no, les falta '
            f'@rol_excluido(Usuario.Rol.PRACTICANTE): {sorted(de_mas)}',
        )
        self.assertTrue(negadas, 'la prueba no está probando nada')


class PantallasCerradasTests(BasePracticante):
    """Las que explícitamente no debe ver, una por una."""

    def test_no_ve_los_reportes(self):
        for nombre in ('indice_reportes', 'reporte_existencias', 'reporte_tecnica',
                       'reporte_alertas', 'reporte_movimientos', 'reporte_prestamos'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_ve_los_movimientos(self):
        for nombre in ('movimientos_ventas', 'prestamos_tecnica'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_puede_registrar_movimientos_ni_prestamos(self):
        for nombre in ('movimiento_ingreso', 'movimiento_salida', 'prestamo_nuevo'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_puede_usar_la_carga_masiva(self):
        """Una importación mal mapeada mete cientos de filas malas de un golpe."""
        for nombre in ('carga_masiva_subir', 'carga_masiva_subir_tecnica'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_ve_la_administracion(self):
        for nombre in ('lista_usuarios', 'lista_categorias', 'lista_proveedores'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)

    def test_no_ve_el_kardex(self):
        respuesta = self.client.get(reverse('kardex_articulo', args=[self.articulo.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_el_resumen_lo_manda_al_catalogo(self):
        """
        Es la pantalla a la que cae al iniciar sesión, y enseña la
        valorización de las dos bodegas. Se redirige en vez de dar un 403.
        """
        respuesta = self.client.get(reverse('resumen'))

        self.assertRedirects(respuesta, reverse('catalogo_articulos'))


class TrabajoDelPracticanteTests(BasePracticante):
    """Lo que sí tiene que poder hacer: dejar el catálogo capturado."""

    def test_crea_un_articulo(self):
        proveedor = Proveedor.objects.create(nombre='CEMACO')
        categoria = Categoria.objects.get(nombre='Básculas', modulo=Categoria.Modulo.VENTAS)

        self.client.post(reverse('articulo_nuevo'), {
            'codigo_interno': '', 'numero_serie': '', 'nombre_producto': 'Báscula nueva',
            'marca': 'LOCOSC', 'modelo': 'BN-1', 'capacidad': '300kg',
            'bodega': self.bodega.pk, 'categoria': categoria.pk, 'proveedor': proveedor.nombre,
            'precio': '1500', 'imagen_url': '',
            'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2, 'activo': 'on',
        })

        self.assertTrue(Articulo.objects.filter(nombre_producto='Báscula nueva').exists())

    def test_edita_un_articulo(self):
        self.client.post(reverse('articulo_editar', args=[self.articulo.pk]), {
            'codigo_interno': self.articulo.codigo_interno, 'numero_serie': '',
            'nombre_producto': 'Báscula corregida', 'marca': '', 'modelo': 'B-1',
            'capacidad': '', 'bodega': self.bodega.pk, 'proveedor': '', 'precio': '0',
            'imagen_url': '', 'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2,
            'activo': 'on',
        })

        self.articulo.refresh_from_db()
        self.assertEqual(self.articulo.nombre_producto, 'Báscula corregida')

    def test_elimina_un_articulo_sin_historial(self):
        articulo = Articulo.objects.create(
            nombre_producto='Capturado por error', modelo='ERR-1', bodega=self.bodega,
        )

        self.client.post(reverse('articulo_eliminar', args=[articulo.pk]))

        self.assertFalse(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_no_puede_borrar_uno_con_historial(self):
        """La protección del historial vale para todos los roles."""
        MovimientoVenta.objects.create(
            articulo=self.articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.REPUESTOS,
            cantidad=5, usuario=self.admin,
        )

        self.client.post(reverse('articulo_eliminar', args=[self.articulo.pk]))

        self.assertTrue(Articulo.objects.filter(pk=self.articulo.pk).exists())

    def test_crea_y_elimina_un_activo_tecnico(self):
        self.client.post(reverse('activo_nuevo'), {
            'codigo_interno': 'SE-NUEVO', 'nombre_producto': 'Llave de tubo',
            'marca': '', 'modelo': '', 'bodega': self.tecnica.pk, 'proveedor': '',
            'precio': '300', 'imagen_url': '', 'estado': Activo.Estado.BUEN_ESTADO,
        })
        nuevo = Activo.objects.get(codigo_interno='SE-NUEVO')
        # Nace en 0: la cantidad entra con un ingreso, no al darlo de alta.
        self.assertEqual(nuevo.existencia, 0)

        self.client.post(reverse('activo_eliminar', args=[nuevo.pk]))
        self.assertFalse(Activo.objects.filter(pk=nuevo.pk).exists())


class NavegacionTests(BasePracticante):
    def test_la_navegacion_solo_le_ofrece_los_catalogos(self):
        respuesta = self.client.get(reverse('catalogo_articulos'))

        self.assertContains(respuesta, 'Bodega 1 y 2')
        self.assertContains(respuesta, 'Bodega Técnica')
        for fuera in ('Resumen', 'Reportes', 'Entradas y salidas',
                      'Préstamos de herramienta', 'Usuarios', 'Categorías'):
            with self.subTest(seccion=fuera):
                self.assertNotContains(respuesta, f'>{fuera}</a>')

    def test_ve_los_botones_de_capturar(self):
        respuesta = self.client.get(reverse('catalogo_articulos'))

        self.assertContains(respuesta, '+ Nuevo artículo')
        self.assertContains(respuesta, 'Editar')

    def test_no_ve_el_boton_de_carga_masiva(self):
        respuesta = self.client.get(reverse('catalogo_articulos'))

        self.assertNotContains(respuesta, 'Carga masiva desde Excel')

    def test_no_ve_el_kardex_ni_los_movimientos_del_articulo(self):
        respuesta = self.client.get(reverse('articulo_detalle', args=[self.articulo.pk]))

        self.assertNotContains(respuesta, 'Ver kardex completo')
        self.assertNotContains(respuesta, 'Últimos movimientos')

    def test_el_administrador_si_los_sigue_viendo(self):
        """El rol nuevo no puede haberle quitado nada al administrador."""
        self.client.force_login(self.admin)

        catalogo = self.client.get(reverse('catalogo_articulos'))
        ficha = self.client.get(reverse('articulo_detalle', args=[self.articulo.pk]))

        self.assertContains(catalogo, 'Carga masiva desde Excel')
        self.assertContains(ficha, 'Ver kardex completo')
        self.assertContains(ficha, 'Últimos movimientos')


class PantallaDeUsuariosTests(BasePracticante):
    """El rol nuevo tiene que verse bien donde se administran los usuarios."""

    def setUp(self):
        self.client.force_login(self.admin)

    def test_se_puede_crear_un_practicante(self):
        self.client.post(reverse('usuario_nuevo'), {
            'username': 'nuevo_practicante', 'first_name': 'Ana', 'last_name': 'López',
            'rol': Usuario.Rol.PRACTICANTE, 'is_active': 'on',
            'clave': '', 'generar': 'on',
        })

        creado = Usuario.objects.get(username='nuevo_practicante')
        self.assertEqual(creado.rol, Usuario.Rol.PRACTICANTE)

    def test_la_lista_lo_muestra_como_practicante(self):
        """
        Antes caía en el "else" de la plantilla y salía como Contabilidad.

        Se cuentan dos apariciones: la fila del usuario y la leyenda de roles
        que va al pie de la pantalla. Contar es lo que distingue el arreglo:
        con una sola —la de la leyenda— la fila seguiría mal.
        """
        respuesta = self.client.get(reverse('lista_usuarios'))

        self.assertContains(respuesta, self.practicante.username)
        self.assertContains(
            respuesta, '<span class="chip chip-neutral">Practicante</span>', count=2,
        )
