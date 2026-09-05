"""
Arreglos que salieron al usar el ingreso a Bodega Técnica de verdad.

Cada clase de acá defiende un error concreto que se vio en pantalla, no una
regla nueva del negocio: la idea es que ninguno vuelva sin que las pruebas
lo digan.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega, Proveedor
from tecnica.ayuda_pruebas import dar_existencia
from tecnica.models import Activo, MovimientoActivo
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta
from ventas.test_ingreso_compartido import BaseIngreso


class PantallaDelDocumentoTecnicoTests(BaseIngreso):
    """
    Un ingreso solo de Bodega Técnica se pintaba entero como salida:
    encabezado "SALIDA DE BODEGA · FO-SE-012", columnas de la boleta de venta
    y todo.

    La plantilla preguntaba `cabecera.tipo_documento`, y un movimiento de
    Bodega Técnica no tiene ese campo —a esa bodega solo entran cosas—, así
    que la comparación siempre daba falso. El PDF sí salía bien, que era lo
    más confuso de todo.
    """

    def setUp(self):
        super().setUp()
        self.ingresar([(f'act-{self.taladro.pk}', 4)], folio='ING-TEC-1')
        self.respuesta = self.client.get(reverse('documento_detalle', args=['ING-TEC-1']))

    def test_se_muestra_como_ingreso(self):
        self.assertTrue(self.respuesta.context['es_ingreso'])
        self.assertContains(self.respuesta, 'Ingreso a bodega')
        self.assertContains(self.respuesta, 'FO-SE-013')

    def test_no_se_muestra_como_salida(self):
        self.assertNotContains(self.respuesta, 'Salida de bodega')
        self.assertNotContains(self.respuesta, 'FO-SE-012')

    def test_no_pide_los_campos_de_la_boleta_de_venta(self):
        """Cliente y envío son del FO-SE-012; en un ingreso no aplican."""
        self.assertNotContains(self.respuesta, 'Envío / recibo')

    def test_un_ingreso_de_venta_sigue_saliendo_bien(self):
        self.ingresar([(f'art-{self.bascula.pk}', 1)], folio='ING-VENTA')

        respuesta = self.client.get(reverse('documento_detalle', args=['ING-VENTA']))

        self.assertTrue(respuesta.context['es_ingreso'])
        self.assertContains(respuesta, 'FO-SE-013')

    def test_una_salida_sigue_saliendo_como_salida(self):
        """El arreglo no puede convertir en ingreso a todo."""
        self.ingresar([(f'art-{self.bascula.pk}', 5)])
        MovimientoVenta.objects.create(
            folio='SAL-0001', tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.VENTA,
            articulo=self.bascula, cantidad=1, usuario=self.operador,
        )

        respuesta = self.client.get(reverse('documento_detalle', args=['SAL-0001']))

        self.assertFalse(respuesta.context['es_ingreso'])
        self.assertContains(respuesta, 'Salida de bodega')


class HistorialConLasTresBodegasTests(BaseIngreso):
    """
    El historial listaba solo MovimientoVenta, así que un ingreso a Bodega
    Técnica se guardaba bien pero no aparecía en ninguna pantalla. Como el
    FO-SE-013 es un solo talonario, tenerlo partido por bodega obligaría a
    buscar el mismo folio en dos lugares.
    """

    def test_aparecen_los_ingresos_a_bodega_tecnica(self):
        self.ingresar([(f'act-{self.taladro.pk}', 3)], folio='ING-TEC')

        respuesta = self.client.get(reverse('movimientos_ventas'))

        self.assertContains(respuesta, 'ING-TEC')
        self.assertContains(respuesta, 'Taladro percutor')

    def test_aparecen_los_de_las_dos_bodegas_juntos(self):
        self.ingresar([(f'art-{self.bascula.pk}', 1)], folio='ING-A')
        self.ingresar([(f'act-{self.taladro.pk}', 1)], folio='ING-B')

        respuesta = self.client.get(reverse('movimientos_ventas'))

        self.assertEqual(len(respuesta.context['movimientos']), 2)

    def test_aparecen_las_bajas(self):
        """Es el registro que pidieron: qué se dio de baja y cuánto."""
        self.ingresar([(f'act-{self.taladro.pk}', 5)])
        MovimientoActivo.objects.create(
            tipo=MovimientoActivo.Tipo.BAJA, activo=self.taladro, cantidad=2,
            motivo=MovimientoActivo.Motivo.DANADO, usuario=self.operador,
        )

        respuesta = self.client.get(reverse('movimientos_ventas'), {'tipo': 'baja'})
        filas = list(respuesta.context['movimientos'])

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].etiqueta, 'Baja')
        self.assertEqual(filas[0].signo, -1)

    def test_el_buscador_encuentra_por_folio_tecnico(self):
        self.ingresar([(f'act-{self.taladro.pk}', 1)], folio='ING-BUSCAME')

        respuesta = self.client.get(reverse('movimientos_ventas'), {'q': 'BUSCAME'})

        self.assertEqual(len(respuesta.context['movimientos']), 1)

    def test_filtrar_solo_salidas_deja_fuera_la_bodega_tecnica(self):
        """A Bodega Técnica solo entran cosas: no tiene salidas."""
        self.ingresar([(f'act-{self.taladro.pk}', 1)])

        respuesta = self.client.get(reverse('movimientos_ventas'), {'tipo': 'salida'})

        self.assertEqual(len(respuesta.context['movimientos']), 0)


class FormularioDeActivoTests(TestCase):
    """
    Los campos de existencia y de consumible se agregaron al formulario pero
    nunca se pintaron: la plantilla lista los campos uno por uno, así que
    quedaron invisibles y no había dónde marcar un consumible.
    """

    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_form', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_la_pantalla_de_nuevo_ofrece_los_dos_campos(self):
        respuesta = self.client.get(reverse('activo_nuevo'))

        self.assertContains(respuesta, 'id_existencia')
        self.assertContains(respuesta, 'id_es_consumible')

    def test_la_pantalla_de_editar_tambien(self):
        activo = Activo.objects.create(
            codigo_interno='SE-F1', nombre_producto='Bombillo', bodega=self.bodega,
        )
        dar_existencia(activo, 4, self.admin)

        respuesta = self.client.get(reverse('activo_editar', args=[activo.pk]))

        self.assertContains(respuesta, 'id_es_consumible')
        self.assertEqual(respuesta.context['form']['existencia'].value(), 4)


class ProveedorEscribibleTests(TestCase):
    """
    El proveedor era un desplegable cerrado: al comprarle a alguien nuevo
    había que salirse del formulario a darlo de alta, y no hay pantalla para
    eso.
    """

    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.admin = Usuario.objects.create_user(
            username='admin_prov', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.bascula = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=cls.bodega, precio=100,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            'codigo_interno': '', 'numero_serie': '', 'nombre_producto': 'Báscula nueva',
            'marca': '', 'modelo': 'BN-1', 'capacidad': '', 'bodega': self.bodega.pk,
            'precio': '100', 'imagen_url': '',
            'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2, 'activo': 'on',
        }
        datos.update(extra)
        return datos

    def test_un_proveedor_nuevo_se_crea_al_escribirlo(self):
        self.client.post(reverse('articulo_nuevo'), self.datos(proveedor='FERRETERIA NUEVA'))

        articulo = Articulo.objects.get(nombre_producto='Báscula nueva')
        self.assertEqual(articulo.proveedor.nombre, 'FERRETERIA NUEVA')

    def test_uno_que_ya_existe_no_se_duplica(self):
        """El Excel trae el mismo nombre con distinta capitalización."""
        Proveedor.objects.create(nombre='BRECKNELL')

        self.client.post(reverse('articulo_nuevo'), self.datos(proveedor='brecknell'))

        self.assertEqual(Proveedor.objects.filter(nombre__iexact='brecknell').count(), 1)

    def test_dejarlo_vacio_es_valido(self):
        self.client.post(reverse('articulo_nuevo'), self.datos(proveedor=''))

        self.assertIsNone(Articulo.objects.get(nombre_producto='Báscula nueva').proveedor)

    def test_al_editar_se_ve_el_nombre_y_no_el_numero(self):
        self.bascula.proveedor = Proveedor.objects.create(nombre='LOCOSC')
        self.bascula.save()

        respuesta = self.client.get(reverse('articulo_editar', args=[self.bascula.pk]))

        self.assertEqual(respuesta.context['form']['proveedor'].value(), 'LOCOSC')

    def test_la_caja_trae_las_sugerencias(self):
        Proveedor.objects.create(nombre='CELASA')

        respuesta = self.client.get(reverse('articulo_nuevo'))

        self.assertContains(respuesta, '<datalist')
        self.assertContains(respuesta, 'CELASA')

    def test_en_bodega_tecnica_tambien_se_puede_escribir(self):
        tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)

        self.client.post(reverse('activo_nuevo'), {
            'codigo_interno': 'SE-P1', 'nombre_producto': 'Taladro', 'marca': '', 'modelo': '',
            'bodega': tecnica.pk, 'precio': '900', 'imagen_url': '',
            'estado': Activo.Estado.BUEN_ESTADO, 'existencia': 1, 'proveedor': 'TRUPER',
            'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
        })

        self.assertEqual(Activo.objects.get(codigo_interno='SE-P1').proveedor.nombre, 'TRUPER')
