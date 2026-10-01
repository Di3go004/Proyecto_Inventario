"""
Buscar un serial en el catálogo dice dónde está cada unidad que lo lleva.

Lo pidió la bodega por los juegos de indicador y plataforma: traen el mismo
serial en las dos cajas —el indicador lo lleva tal cual y la plataforma con
"-P"— y muchas veces se venden por separado. Buscando el del indicador tiene
que verse en el mismo vistazo si su plataforma sigue en bodega, si salió y
todavía puede volver, o si ya se vendió.

El paradero no se guarda en ningún lado: sale de los movimientos, igual que
la existencia. Por eso estas pruebas mueven las unidades solo por las puertas
del modelo y miran qué contesta.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import (
    Articulo, MovimientoVenta, UnidadArticulo, ingresar_unidades, registrar_resultado,
    sacar_unidades,
)
from ventas.templatetags.catalogo_extras import clase_paradero
from ventas.views import LIMITE_UNIDADES_EN_BUSQUEDA

TIPO = MovimientoVenta.TipoTransaccion
PARADERO = UnidadArticulo.Paradero


class BaseParadero(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.bodega_2 = Bodega.objects.create(nombre='Bodega 2', tipo=Bodega.Tipo.VENTA)
        clave = 'clave-de-prueba'
        cls.admin = Usuario.objects.create_user(
            username='admin_pa', password=clave, rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='operador_pa', password=clave, rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='contable_pa', password=clave, rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.practicante = Usuario.objects.create_user(
            username='practicante_pa', password=clave, rol=Usuario.Rol.PRACTICANTE,
        )
        cls.indicador = Articulo.objects.create(
            nombre_producto='Indicador 7628A', modelo='7628A', capacidad='',
            bodega=cls.bodega, precio=Decimal('2500'), lleva_serie=True,
        )
        # Umbrales a la medida para que su nivel no sea el del indicador: la
        # prueba del filtro por nivel necesita que los dos se distingan.
        cls.plataforma = Articulo.objects.create(
            nombre_producto='Plataforma 7628A 1215 2T', modelo='7628A', capacidad='2T',
            bodega=cls.bodega, precio=Decimal('9000'), lleva_serie=True,
            stock_critico=0, stock_alerta=1, stock_optimo=2,
        )

    def setUp(self):
        self.hace_una_semana = timezone.now() - timedelta(days=7)

    # --- ayudantes -------------------------------------------------------

    def ingresar(self, articulo, *seriales, folio='ING-00001'):
        movimiento = MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=TIPO.VENTA, cantidad=len(seriales), usuario=self.admin,
            folio=folio, fecha=self.hace_una_semana - timedelta(days=1),
        )
        ingresar_unidades(movimiento, list(seriales))
        return movimiento

    def sacar(self, *seriales, tipo=TIPO.CON_TECNICO, folio='SAL-00031',
              cliente='Granja El Cerdito', fecha=None):
        """Una línea de salida por las puertas del modelo, como la guarda la boleta."""
        unidades = list(UnidadArticulo.objects.filter(numero_serie__in=seriales))
        movimiento = MovimientoVenta.objects.create(
            articulo=unidades[0].articulo, tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=tipo, cantidad=len(unidades),
            cantidad_vendida=len(unidades) if tipo == TIPO.VENTA else 0,
            usuario=self.operador, folio=folio, cliente_nombre=cliente,
            fecha=fecha or self.hace_una_semana,
        )
        sacar_unidades(movimiento, unidades, vendidas=tipo == TIPO.VENTA)
        return movimiento

    def unidades(self, *seriales):
        return UnidadArticulo.objects.filter(numero_serie__in=seriales)

    def paradero(self, serial):
        return UnidadArticulo.objects.get(numero_serie=serial).paradero

    def buscar(self, q, usuario=None, **filtros):
        self.client.force_login(usuario or self.operador)
        return self.client.get(reverse('catalogo_articulos'), {'q': q, **filtros})

    def encontradas(self, respuesta):
        return [u.numero_serie for u in respuesta.context['unidades_encontradas']]


class ParaderoTests(BaseParadero):
    """Lo que dice `paradero` en cada momento de la vida de una unidad."""

    def setUp(self):
        super().setUp()
        self.ingresar(self.indicador, '0250721019', '0250721020')

    def test_la_que_entro_esta_en_bodega(self):
        self.assertEqual(self.paradero('0250721019'), PARADERO.EN_BODEGA)

    def test_la_que_se_llevo_el_tecnico(self):
        self.sacar('0250721019')
        self.assertEqual(self.paradero('0250721019'), PARADERO.CON_TECNICO)

    def test_un_demo_no_es_lo_mismo_que_con_el_tecnico(self):
        self.sacar('0250721019', tipo=TIPO.PRESTAMO_DEMO)
        self.assertEqual(self.paradero('0250721019'), PARADERO.DEMO)

    def test_la_que_sale_vendida(self):
        self.sacar('0250721019', tipo=TIPO.VENTA)
        self.assertEqual(self.paradero('0250721019'), PARADERO.VENDIDA)

    def test_la_que_se_confirma_vendida_cuando_regresa_el_tecnico(self):
        salida = self.sacar('0250721019', '0250721020')
        registrar_resultado(
            salida, usuario=self.admin, unidades_vendidas=self.unidades('0250721019'),
        )
        self.assertEqual(self.paradero('0250721019'), PARADERO.VENDIDA)
        # La otra sigue con el técnico: vender una no resuelve la línea entera.
        self.assertEqual(self.paradero('0250721020'), PARADERO.CON_TECNICO)

    def test_la_que_regresa_vuelve_a_estar_en_bodega_sola(self):
        salida = self.sacar('0250721019', tipo=TIPO.PRESTAMO_DEMO)
        registrar_resultado(
            salida, usuario=self.admin, unidades_devueltas=self.unidades('0250721019'),
            fecha_regreso=timezone.now(), devuelto_por='Ivan Leiva',
        )
        self.assertEqual(self.paradero('0250721019'), PARADERO.EN_BODEGA)

    def test_si_vuelve_a_salir_manda_la_ultima_salida(self):
        demo = self.sacar('0250721019', tipo=TIPO.PRESTAMO_DEMO, folio='SAL-00031')
        registrar_resultado(
            demo, usuario=self.admin, unidades_devueltas=self.unidades('0250721019'),
            fecha_regreso=self.hace_una_semana + timedelta(days=1), devuelto_por='Ivan Leiva',
        )
        self.sacar('0250721019', folio='SAL-00040', fecha=self.hace_una_semana + timedelta(days=2))

        unidad = UnidadArticulo.objects.get(numero_serie='0250721019')
        self.assertEqual(unidad.paradero, PARADERO.CON_TECNICO)
        self.assertEqual(unidad.movimiento_salida.folio, 'SAL-00040')

    def test_una_venta_a_la_que_se_le_quito_lo_vendido_queda_pendiente(self):
        venta = self.sacar('0250721019', tipo=TIPO.VENTA)
        registrar_resultado(venta, usuario=self.admin, unidades_vendidas=())
        self.assertEqual(self.paradero('0250721019'), PARADERO.PENDIENTE)

    def test_la_que_se_quedo_sin_movimientos(self):
        # Borrar la boleta con la que entró deja la unidad sin nada detrás. No
        # está en bodega, pero tampoco salió: no se le puede decir "vendida".
        ingreso = MovimientoVenta.objects.get(folio='ING-00001')
        MovimientoVenta.objects.filter(pk=ingreso.pk).delete()
        self.assertEqual(self.paradero('0250721019'), PARADERO.SIN_MOVIMIENTOS)

    def test_verde_en_bodega_ambar_lo_que_puede_volver_gris_lo_que_no(self):
        puede_volver = {PARADERO.CON_TECNICO, PARADERO.DEMO, PARADERO.PENDIENTE}
        for paradero in PARADERO:
            with self.subTest(paradero=paradero):
                if paradero == PARADERO.EN_BODEGA:
                    esperada = 'chip-good'
                elif paradero in puede_volver:
                    esperada = 'chip-warn'
                else:
                    esperada = 'chip-neutral'
                self.assertEqual(clase_paradero(paradero), esperada)


class CuadroDelBuscadorTests(BaseParadero):
    """
    El caso de la bodega: tres plataformas 7628A con sus indicadores, que se
    venden por separado. El 0250721019 se quedó sin indicador.
    """

    def setUp(self):
        super().setUp()
        self.ingresar(self.indicador, '0250721020', '0250721021', folio='ING-00001')
        self.ingresar(
            self.plataforma, '0250721019-P', '0250721020-P', '0250721021-P', folio='ING-00002',
        )
        self.con_el_tecnico = self.sacar('0250721020-P', folio='SAL-00031')
        self.sacar('0250721021', tipo=TIPO.VENTA, folio='SAL-00032', cliente='Agropecuaria Sur')

    def test_buscando_el_indicador_aparece_su_plataforma(self):
        respuesta = self.buscar('0250721020')

        self.assertEqual(self.encontradas(respuesta), ['0250721020', '0250721020-P'])
        self.assertContains(respuesta, 'Dónde está cada unidad')
        self.assertContains(respuesta, '<span class="chip chip-good">En bodega</span>', html=True)
        # En cuál de las dos bodegas: la del producto, que es donde se guarda.
        self.assertContains(respuesta, '<span class="paradero-detalle">Bodega 1</span>', html=True)
        self.assertContains(respuesta, '<span class="chip chip-warn">Con el técnico</span>', html=True)
        self.assertContains(respuesta, reverse('documento_detalle', args=['SAL-00031']))
        self.assertContains(respuesta, 'Granja El Cerdito')

    def test_la_vendida_dice_vendida_y_su_plataforma_sigue_en_bodega(self):
        respuesta = self.buscar('0250721021')

        paraderos = {u.numero_serie: u.paradero for u in respuesta.context['unidades_encontradas']}
        self.assertEqual(paraderos, {
            '0250721021': PARADERO.VENDIDA, '0250721021-P': PARADERO.EN_BODEGA,
        })
        self.assertContains(respuesta, '<span class="chip chip-neutral">Vendida</span>', html=True)

    def test_la_plataforma_que_regresa_vuelve_a_decir_en_bodega(self):
        registrar_resultado(
            self.con_el_tecnico, usuario=self.admin,
            unidades_devueltas=self.unidades('0250721020-P'),
            fecha_regreso=timezone.now(), devuelto_por='Ivan Leiva',
        )
        respuesta = self.buscar('0250721020')

        paraderos = {u.numero_serie: u.paradero for u in respuesta.context['unidades_encontradas']}
        self.assertEqual(paraderos['0250721020-P'], PARADERO.EN_BODEGA)
        self.assertNotContains(respuesta, reverse('documento_detalle', args=['SAL-00031']))

    def test_la_existencia_cuenta_solo_lo_que_esta_en_bodega(self):
        # De tres plataformas una anda con el técnico: en bodega hay dos, y eso
        # es lo que dice el catálogo, no las tres que se compraron.
        self.plataforma.refresh_from_db()
        self.assertEqual(self.plataforma.stock_actual, 2)

    def test_por_lote_salen_todas_las_piezas(self):
        respuesta = self.buscar('02507210')
        self.assertEqual(self.encontradas(respuesta), [
            '0250721019-P', '0250721020', '0250721020-P', '0250721021', '0250721021-P',
        ])

    def test_si_ningun_serial_coincide_no_hay_cuadro(self):
        respuesta = self.buscar('Plataforma')

        self.assertEqual(respuesta.context['unidades_encontradas'], [])
        self.assertNotContains(respuesta, 'Dónde está cada unidad')
        # La tabla de productos sigue funcionando como siempre.
        self.assertContains(respuesta, 'Plataforma 7628A 1215 2T')

    def test_sin_busqueda_no_hay_cuadro(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse('catalogo_articulos'))
        self.assertNotContains(respuesta, 'Dónde está cada unidad')
        self.assertContains(respuesta, 'Buscar por código, nombre o serial')

    def test_respeta_los_filtros_igual_que_la_tabla(self):
        otro = Articulo.objects.create(
            nombre_producto='Indicador de Bodega 2', modelo='X', capacidad='',
            bodega=self.bodega_2, precio=Decimal('100'), lleva_serie=True,
        )
        self.ingresar(otro, '0250721099', folio='ING-00003')

        solo_bodega_2 = self.buscar('02507210', bodega=self.bodega_2.pk)
        self.assertEqual(self.encontradas(solo_bodega_2), ['0250721099'])

        solo_bodega_1 = self.buscar('02507210', bodega=self.bodega.pk)
        self.assertNotIn('0250721099', self.encontradas(solo_bodega_1))

    def test_respeta_tambien_el_filtro_por_nivel(self):
        # El nivel se filtra en Python, no en la base: es el otro camino.
        self.indicador.refresh_from_db()
        self.plataforma.refresh_from_db()
        self.assertNotEqual(self.indicador.nivel_alerta, self.plataforma.nivel_alerta)

        respuesta = self.buscar('02507210', nivel=self.plataforma.nivel_alerta)
        self.assertEqual(
            self.encontradas(respuesta), ['0250721019-P', '0250721020-P', '0250721021-P'],
        )

    def test_la_que_coincide_completa_va_primero(self):
        # Dos aparatos distintos que solo se diferencian por el cero de adelante.
        self.ingresar(self.indicador, '0260105009', '260105009', folio='ING-00004')
        respuesta = self.buscar('260105009')
        self.assertEqual(self.encontradas(respuesta), ['260105009', '0260105009'])

    def test_con_demasiadas_enseña_las_primeras_y_dice_cuantas_son(self):
        seriales = [f'LOTE-{n:03d}' for n in range(LIMITE_UNIDADES_EN_BUSQUEDA + 3)]
        self.ingresar(self.indicador, *seriales, folio='ING-00005')

        respuesta = self.buscar('LOTE-')

        self.assertEqual(len(respuesta.context['unidades_encontradas']), LIMITE_UNIDADES_EN_BUSQUEDA)
        self.assertEqual(respuesta.context['total_unidades_encontradas'], len(seriales))
        self.assertContains(
            respuesta,
            f'Se muestran las primeras {LIMITE_UNIDADES_EN_BUSQUEDA} de {len(seriales)}.',
        )

    def test_el_practicante_ve_donde_esta_pero_la_boleta_no_es_enlace(self):
        respuesta = self.buscar('0250721020', usuario=self.practicante)

        self.assertContains(respuesta, '<span class="chip chip-warn">Con el técnico</span>', html=True)
        self.assertContains(respuesta, 'SAL-00031')
        # A la boleta no llega (403), así que no se le ofrece.
        self.assertNotContains(respuesta, reverse('documento_detalle', args=['SAL-00031']))

    def test_los_demas_roles_si_tienen_el_enlace_a_la_boleta(self):
        for usuario in (self.admin, self.operador, self.contable):
            with self.subTest(rol=usuario.rol):
                respuesta = self.buscar('0250721020', usuario=usuario)
                self.assertContains(respuesta, reverse('documento_detalle', args=['SAL-00031']))

    def test_no_hace_una_consulta_por_unidad(self):
        self.client.force_login(self.operador)

        def consultas_y_unidades(q):
            with CaptureQueriesContext(connection) as capturadas:
                respuesta = self.client.get(reverse('catalogo_articulos'), {'q': q})
            return len(capturadas.captured_queries), len(self.encontradas(respuesta))

        # La primera visita arma cosas que las siguientes reutilizan: no cuenta.
        consultas_y_unidades('0250721020')
        con_dos, dos = consultas_y_unidades('0250721020')
        con_cinco, cinco = consultas_y_unidades('02507210')

        self.assertEqual((dos, cinco), (2, 5))
        self.assertEqual(con_dos, con_cinco)
