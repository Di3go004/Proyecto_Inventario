"""
Las salidas nacen abiertas y se resuelven cuando regresa el técnico.

Cuando alguien se lleva equipo no sabe todavía si lo va a instalar o si lo va
a traer de regreso. Por eso cada línea de una boleta FO-SE-012 sale
pendiente —con el técnico, o como demo con un cliente— y después se le
registra su resultado: cuántas se vendieron y cuántas regresaron. Un repuesto
que se usó cuenta como vendido. Cuando ya no le falta nada a ninguna línea,
el administrador cierra la boleta y desde ahí no se toca.

Lo que regresa es su propio movimiento —un ingreso de devolución amarrado a
la línea—, no una marca en la salida. Antes era una marca, y eso reescribía el
pasado: el kardex pasaba a decir que el equipo nunca había salido.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas import boletas, documentos
from ventas.models import (
    Articulo, MovimientoVenta, UnidadArticulo, cerrar_boleta, ingresar_unidades,
    registrar_resultado, sacar_unidades,
)

TIPO = MovimientoVenta.TipoTransaccion
CON_TECNICO, DEMO, VENTA = TIPO.CON_TECNICO, TIPO.PRESTAMO_DEMO, TIPO.VENTA


class BaseSalidasAbiertas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        clave = 'clave-de-prueba'
        cls.operador = Usuario.objects.create_user(
            username='operador_sa', password=clave, rol=Usuario.Rol.OPERADOR,
        )
        cls.admin = Usuario.objects.create_user(
            username='admin_sa', password=clave, rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='contable_sa', password=clave, rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.practicante = Usuario.objects.create_user(
            username='practicante_sa', password=clave, rol=Usuario.Rol.PRACTICANTE,
        )
        cls.celda = Articulo.objects.create(
            nombre_producto='Celda de carga', modelo='CC-500', capacidad='500kg',
            bodega=cls.bodega, precio=Decimal('800'),
        )
        cls.equipo = Articulo.objects.create(
            nombre_producto='Indicador ZM405', modelo='ZM405', capacidad='',
            bodega=cls.bodega, precio=Decimal('1500'), lleva_serie=True,
        )

    def setUp(self):
        self.client.force_login(self.operador)
        self.hace_una_semana = timezone.now() - timedelta(days=7)
        entrada = MovimientoVenta.objects.create(
            articulo=self.celda, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=TIPO.VENTA, cantidad=10, usuario=self.admin,
            folio='ING-00001', fecha=self.hace_una_semana - timedelta(days=1),
        )
        self.assertEqual(self.existencia(self.celda), 10)
        entrada_equipo = MovimientoVenta.objects.create(
            articulo=self.equipo, tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=TIPO.VENTA, cantidad=4, usuario=self.admin,
            folio='ING-00002', fecha=self.hace_una_semana - timedelta(days=1),
        )
        ingresar_unidades(entrada_equipo, ['A-1', 'A-2', 'A-3', 'A-4'])

    # --- ayudantes -------------------------------------------------------

    def salida(self, articulo, cantidad, tipo=CON_TECNICO, folio='SAL-00001',
               unidades=(), fecha=None):
        """Una línea de salida por la puerta del modelo, con fecha a elección."""
        movimiento = MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
            tipo_transaccion=tipo, cantidad=cantidad,
            cantidad_vendida=cantidad if tipo == VENTA else 0,
            usuario=self.operador, folio=folio, cliente_nombre='Cliente X',
            fecha=fecha or self.hace_una_semana,
        )
        if unidades:
            sacar_unidades(
                movimiento, UnidadArticulo.objects.filter(numero_serie__in=unidades),
                vendidas=tipo == VENTA,
            )
        return movimiento

    def post_salida(self, lineas, folio=''):
        """lineas: [(articulo, cantidad, 'seriales', tipo)]; el tipo puede ir vacío."""
        datos = {
            'folio': folio,
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'solicitado_por': 'Ivan Leiva', 'entregado_por': 'Bodega',
            'cliente_nombre': 'Cliente X', 'envio_recibo': '',
            'no_factura': '', 'observacion': '',
            'linea_articulo': [str(a.pk) for a, _c, _s, _t in lineas],
            'linea_cantidad': [str(c) for _a, c, _s, _t in lineas],
            'linea_texto': [a.codigo_interno for a, _c, _s, _t in lineas],
            'linea_seriales': [s for _a, _c, s, _t in lineas],
            'linea_precio': ['' for _l in lineas],
            'linea_tipo': [t for _a, _c, _s, t in lineas],
        }
        return self.client.post(reverse('movimiento_salida'), datos)

    def resultado(self, salida, **datos):
        datos.setdefault('fecha_regreso', timezone.localtime().strftime('%Y-%m-%dT%H:%M'))
        datos.setdefault('devuelto_por', 'Ivan Leiva')
        datos.setdefault('observacion', '')
        return self.client.post(reverse('salida_resultado', args=[salida.pk]), datos)

    def resultado_por_serial(self, salida, **estados):
        """estados: A_1='vendida' → el radio de la unidad A-1."""
        datos = {}
        for serial_con_guion_bajo, estado in estados.items():
            unidad = UnidadArticulo.objects.get(numero_serie=serial_con_guion_bajo.replace('_', '-'))
            datos[f'unidad_{unidad.pk}'] = estado
        for unidad in salida.unidades.all():
            datos.setdefault(f'unidad_{unidad.pk}', 'pendiente')
        return self.resultado(salida, **datos)

    def existencia(self, articulo):
        articulo.refresh_from_db()
        return articulo.stock_actual

    def en_bodega(self, serial):
        return UnidadArticulo.objects.get(numero_serie=serial).en_bodega


class AlRegistrarLaSalidaTests(BaseSalidasAbiertas):
    def test_cada_linea_trae_su_tipo(self):
        """Una misma boleta lleva lo del técnico, un demo y una venta."""
        respuesta = self.post_salida([
            (self.celda, 2, '', CON_TECNICO),
            (self.celda, 1, '', DEMO),
            (self.celda, 3, '', VENTA),
        ], folio='SAL-00050')

        self.assertEqual(respuesta.status_code, 302)
        tipos = list(
            MovimientoVenta.objects.filter(folio='SAL-00050')
            .order_by('id').values_list('tipo_transaccion', flat=True)
        )
        self.assertEqual(tipos, [CON_TECNICO, DEMO, VENTA])

    def test_sin_tipo_queda_con_el_tecnico(self):
        """El olvido menos dañino: queda pendiente, a la vista."""
        self.post_salida([(self.celda, 2, '', '')], folio='SAL-00051')

        salida = MovimientoVenta.objects.get(folio='SAL-00051')
        self.assertEqual(salida.tipo_transaccion, CON_TECNICO)
        self.assertEqual(salida.pendientes, 2)

    def test_un_tipo_que_no_es_de_salida_se_rechaza(self):
        respuesta = self.post_salida([(self.celda, 2, '', TIPO.REPUESTOS)], folio='SAL-00052')

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MovimientoVenta.objects.filter(folio='SAL-00052').exists())
        self.assertContains(respuesta, 'Elegí cómo sale')

    def test_lo_pendiente_ya_salio_de_la_existencia(self):
        """Mientras el técnico lo tiene, no está en bodega."""
        self.post_salida([(self.celda, 4, '', CON_TECNICO)])

        self.assertEqual(self.existencia(self.celda), 6)

    def test_la_venta_nace_resuelta(self):
        self.post_salida([(self.celda, 3, '', VENTA)], folio='SAL-00053')

        salida = MovimientoVenta.objects.get(folio='SAL-00053')
        self.assertEqual(salida.cantidad_vendida, 3)
        self.assertFalse(salida.tiene_pendientes)
        self.assertEqual(
            documentos.estado_de_boleta(documentos.lineas_del_documento('SAL-00053')),
            'por_cerrar',
        )

    def test_la_venta_con_seriales_los_marca_vendidos(self):
        self.post_salida([(self.equipo, 2, 'A-1\nA-2', VENTA)], folio='SAL-00054')

        salida = MovimientoVenta.objects.get(folio='SAL-00054')
        estados = {u.numero_serie: e for u, e in salida.estado_de_unidades()}
        self.assertEqual(estados, {'A-1': 'vendida', 'A-2': 'vendida'})

    def test_la_salida_pide_el_tipo_por_linea_y_no_en_el_encabezado(self):
        respuesta = self.client.get(reverse('movimiento_salida'))

        self.assertContains(respuesta, 'name="linea_tipo"')
        self.assertNotContains(respuesta, 'name="tipo_transaccion"')
        self.assertContains(respuesta, 'Con el técnico')

    def test_el_ingreso_no_ofrece_los_tipos_de_la_salida(self):
        """
        Un regreso no se registra como ingreso: se registra en su salida. Si
        el ingreso ofreciera "Préstamo / Demo", sería fácil hacerlo por ahí y
        el equipo contaría dos veces.
        """
        respuesta = self.client.get(reverse('movimiento_ingreso'))
        opciones = [valor for valor, _e in respuesta.context['form'].fields['tipo_transaccion'].choices]

        for tipo in (CON_TECNICO, DEMO, TIPO.DEVOLUCION):
            with self.subTest(tipo=tipo):
                self.assertNotIn(tipo, opciones)
        self.assertIn(VENTA, opciones)

    def test_no_se_puede_repetir_el_numero_de_una_salida(self):
        """Repetirlo le agregaría líneas a una boleta, aunque ya esté cerrada."""
        self.salida(self.celda, 1, folio='SAL-00060')

        respuesta = self.post_salida([(self.celda, 1, '', VENTA)], folio='sal-00060')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrada')
        self.assertEqual(MovimientoVenta.objects.filter(folio__iexact='SAL-00060').count(), 1)


class ResultadoPorCantidadTests(BaseSalidasAbiertas):
    def test_regreso_parcial(self):
        """De 4 celdas se instalan 3 y regresa 1: lo que hoy no se podía."""
        salida = self.salida(self.celda, 4)
        self.assertEqual(self.existencia(self.celda), 6)

        self.resultado(salida, vendidas='3', devueltas='1')

        salida.refresh_from_db()
        self.assertEqual(salida.cantidad_vendida, 3)
        self.assertEqual(salida.devueltas, 1)
        self.assertFalse(salida.tiene_pendientes)
        self.assertEqual(self.existencia(self.celda), 7)

    def test_por_partes_y_sin_duplicar(self):
        """Hoy regresa una; días después se sabe que las otras se vendieron."""
        salida = self.salida(self.celda, 4)

        self.resultado(salida, vendidas='0', devueltas='1')
        salida.refresh_from_db()
        self.assertEqual(salida.pendientes, 3)

        self.resultado(salida, vendidas='3', devueltas='1')
        salida.refresh_from_db()
        self.assertEqual(salida.pendientes, 0)
        self.assertEqual(salida.devoluciones.count(), 1, 'el regreso no se duplicó')
        self.assertEqual(self.existencia(self.celda), 7)

    def test_el_regreso_lleva_su_fecha_y_quien_lo_trajo(self):
        salida = self.salida(self.celda, 2)

        self.resultado(salida, vendidas='0', devueltas='2',
                       fecha_regreso='2031-01-15T10:30', devuelto_por='Pedro')

        devolucion = salida.devoluciones.get()
        fecha = timezone.localtime(devolucion.fecha)
        self.assertEqual((fecha.year, fecha.month, fecha.day, fecha.hour), (2031, 1, 15, 10))
        self.assertEqual(devolucion.devuelto_por, 'Pedro')
        self.assertEqual(devolucion.folio, salida.folio)
        salida.refresh_from_db()
        self.assertEqual(salida.fecha, self.hace_una_semana, 'la salida conserva su día')

    def test_corregir_a_menos_deshace_parte_del_regreso(self):
        salida = self.salida(self.celda, 4)
        self.resultado(salida, vendidas='0', devueltas='3')
        self.assertEqual(self.existencia(self.celda), 9)

        self.resultado(salida, vendidas='0', devueltas='1')

        self.assertEqual(salida.devoluciones.get().cantidad, 1)
        self.assertEqual(self.existencia(self.celda), 7)

    def test_corregir_a_cero_borra_el_regreso(self):
        salida = self.salida(self.celda, 2)
        self.resultado(salida, vendidas='0', devueltas='2')

        self.resultado(salida, vendidas='2', devueltas='0')

        self.assertFalse(salida.devoluciones.exists())
        self.assertEqual(self.existencia(self.celda), 8)

    def test_no_pueden_sumar_mas_de_lo_que_salio(self):
        salida = self.salida(self.celda, 4)

        respuesta = self.resultado(salida, vendidas='3', devueltas='2')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Salieron 4')
        salida.refresh_from_db()
        self.assertEqual((salida.cantidad_vendida, salida.devueltas), (0, 0))

    def test_un_regreso_nuevo_pide_quien_lo_devolvio(self):
        salida = self.salida(self.celda, 2)

        respuesta = self.resultado(salida, vendidas='0', devueltas='1', devuelto_por='')

        self.assertContains(respuesta, 'Falta quién lo devolvió')
        self.assertFalse(salida.devoluciones.exists())

    def test_vender_no_pide_datos_de_regreso(self):
        salida = self.salida(self.celda, 2)

        respuesta = self.resultado(salida, vendidas='2', devueltas='0',
                                   devuelto_por='', fecha_regreso='')

        self.assertEqual(respuesta.status_code, 302)
        salida.refresh_from_db()
        self.assertEqual(salida.cantidad_vendida, 2)

    def test_el_regreso_no_puede_ser_anterior_a_la_salida(self):
        salida = self.salida(self.celda, 2)

        respuesta = self.resultado(salida, vendidas='0', devueltas='2',
                                   fecha_regreso='2020-01-01T08:00')

        self.assertContains(respuesta, 'no puede ser anterior')
        self.assertFalse(salida.devoluciones.exists())

    def test_no_se_deshace_el_regreso_de_algo_que_volvio_a_salir(self):
        """Dejaría la existencia en negativo: se cancela todo."""
        salida = self.salida(self.celda, 4)
        self.resultado(salida, vendidas='0', devueltas='4')
        self.salida(self.celda, 10, tipo=VENTA, folio='SAL-00099', fecha=timezone.now())
        self.assertEqual(self.existencia(self.celda), 0)

        respuesta = self.resultado(salida, vendidas='0', devueltas='0')

        self.assertContains(respuesta, 'ya volvió a salir')
        self.assertEqual(salida.devoluciones.get().cantidad, 4)
        self.assertEqual(self.existencia(self.celda), 0)

    def test_un_ingreso_no_tiene_resultado(self):
        ingreso = MovimientoVenta.objects.get(folio='ING-00001')

        respuesta = self.client.get(reverse('salida_resultado', args=[ingreso.pk]))

        self.assertEqual(respuesta.status_code, 404)


class ResultadoPorSerialTests(BaseSalidasAbiertas):
    def test_cada_aparato_con_su_resultado(self):
        salida = self.salida(self.equipo, 3, unidades=['A-1', 'A-2', 'A-3'])

        self.resultado_por_serial(salida, A_1='vendida', A_2='devuelta', A_3='pendiente')

        estados = {u.numero_serie: e for u, e in salida.estado_de_unidades()}
        self.assertEqual(estados, {'A-1': 'vendida', 'A-2': 'devuelta', 'A-3': 'pendiente'})
        self.assertTrue(self.en_bodega('A-2'))
        self.assertFalse(self.en_bodega('A-1'))
        self.assertFalse(self.en_bodega('A-3'))
        salida.refresh_from_db()
        self.assertEqual((salida.cantidad_vendida, salida.devueltas, salida.pendientes), (1, 1, 1))
        self.assertEqual(self.existencia(self.equipo), 2)

    def test_existencia_y_unidades_siguen_diciendo_lo_mismo(self):
        salida = self.salida(self.equipo, 3, unidades=['A-1', 'A-2', 'A-3'])
        self.resultado_por_serial(salida, A_1='vendida', A_2='devuelta')

        self.assertEqual(self.existencia(self.equipo), self.equipo.unidades_en_bodega)

    def test_el_que_regreso_puede_volver_a_salir(self):
        salida = self.salida(self.equipo, 1, unidades=['A-1'])
        self.resultado_por_serial(salida, A_1='devuelta')

        otra = self.salida(self.equipo, 1, tipo=VENTA, folio='SAL-00002',
                           unidades=['A-1'], fecha=timezone.now())

        self.assertFalse(self.en_bodega('A-1'))
        self.assertEqual(
            [s for s, _e in documentos.lineas_del_documento('SAL-00002')[0].unidades_con_estado],
            ['A-1'],
        )
        self.assertIsNotNone(otra.pk)

    def test_deshacer_el_regreso_de_un_serial(self):
        salida = self.salida(self.equipo, 2, unidades=['A-1', 'A-2'])
        self.resultado_por_serial(salida, A_2='devuelta')
        self.assertTrue(self.en_bodega('A-2'))

        self.resultado_por_serial(salida, A_2='pendiente')

        self.assertFalse(self.en_bodega('A-2'))
        self.assertFalse(salida.devoluciones.exists())
        self.assertEqual(self.existencia(self.equipo), 2)

    def test_no_se_deshace_si_ese_serial_volvio_a_salir(self):
        salida = self.salida(self.equipo, 2, unidades=['A-1', 'A-2'])
        self.resultado_por_serial(salida, A_2='devuelta')
        self.salida(self.equipo, 1, tipo=VENTA, folio='SAL-00077',
                    unidades=['A-2'], fecha=timezone.now())

        respuesta = self.resultado_por_serial(salida, A_2='pendiente')

        self.assertContains(respuesta, 'SAL-00077')
        self.assertTrue(salida.devoluciones.exists(), 'el regreso sigue registrado')

    def test_la_boleta_sigue_diciendo_sus_seriales(self):
        """Un documento firmado no cambia solo, aunque el aparato regrese."""
        salida = self.salida(self.equipo, 2, unidades=['A-1', 'A-2'])
        self.resultado_por_serial(salida, A_1='devuelta', A_2='vendida')

        linea = documentos.lineas_del_documento('SAL-00001')[0]
        self.assertEqual(sorted(linea.seriales), ['A-1', 'A-2'])


class CierreTests(BaseSalidasAbiertas):
    def cerrar_como(self, usuario, folio='SAL-00001'):
        self.client.force_login(usuario)
        return self.client.post(reverse('cerrar_boleta_salida', args=[folio]))

    def test_con_algo_pendiente_no_se_cierra(self):
        self.salida(self.celda, 2)

        self.cerrar_como(self.admin)

        self.assertFalse(MovimientoVenta.objects.filter(fecha_cierre__isnull=False).exists())

    def test_el_administrador_la_cierra_entera(self):
        primera = self.salida(self.celda, 2, tipo=VENTA)
        segunda = self.salida(self.celda, 1)
        registrar_resultado(segunda, usuario=self.operador, vendidas=1)

        self.cerrar_como(self.admin)

        for linea in (primera, segunda):
            linea.refresh_from_db()
            self.assertIsNotNone(linea.fecha_cierre)
            self.assertEqual(linea.cerrada_por, self.admin)

    def test_el_operador_no_puede_cerrar(self):
        self.salida(self.celda, 2, tipo=VENTA)

        respuesta = self.cerrar_como(self.operador)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(MovimientoVenta.objects.filter(fecha_cierre__isnull=False).exists())

    def test_cerrada_ya_no_acepta_resultados(self):
        salida = self.salida(self.celda, 2)
        registrar_resultado(salida, usuario=self.operador, vendidas=2)
        cerrar_boleta('SAL-00001', self.admin)

        with self.assertRaisesMessage(ValidationError, 'ya está cerrada'):
            registrar_resultado(salida, usuario=self.operador, vendidas=0, devueltas=2,
                                fecha_regreso=timezone.now(), devuelto_por='X')
        respuesta = self.client.get(reverse('salida_resultado', args=[salida.pk]))
        self.assertRedirects(respuesta, reverse('documento_detalle', args=['SAL-00001']))

    def test_no_se_cierra_dos_veces(self):
        self.salida(self.celda, 2, tipo=VENTA)
        cerrar_boleta('SAL-00001', self.admin)

        with self.assertRaisesMessage(ValidationError, 'ya estaba cerrada'):
            cerrar_boleta('SAL-00001', self.admin)

    def test_el_boton_de_cerrar_es_del_administrador_y_solo_cuando_toca(self):
        salida = self.salida(self.celda, 2)
        url = reverse('documento_detalle', args=['SAL-00001'])

        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(url), 'Cerrar boleta', msg_prefix='abierta')

        registrar_resultado(salida, usuario=self.operador, vendidas=2)
        self.assertContains(self.client.get(url), 'Cerrar boleta')

        self.client.force_login(self.operador)
        self.assertNotContains(self.client.get(url), 'Cerrar boleta', msg_prefix='operador')


class QuienPuedeTests(BaseSalidasAbiertas):
    def test_registrar_el_resultado_es_de_quien_registra_salidas(self):
        salida = self.salida(self.celda, 2)
        url = reverse('salida_resultado', args=[salida.pk])
        esperado = {
            self.admin: 200, self.operador: 200,
            self.contable: 403, self.practicante: 403,
        }
        for usuario, codigo in esperado.items():
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(url).status_code, codigo)


class KardexTests(BaseSalidasAbiertas):
    def test_el_regreso_aparece_en_su_dia_y_la_salida_no_cambia(self):
        """
        El error que motivó el cambio: al registrar el regreso, el kardex
        pasaba a decir que el equipo nunca había salido.
        """
        salida = self.salida(self.celda, 4)
        registrar_resultado(
            salida, usuario=self.operador, devueltas=1,
            fecha_regreso=self.hace_una_semana + timedelta(days=5), devuelto_por='Pedro',
        )

        respuesta = self.client.get(reverse('kardex_articulo', args=[self.celda.pk]))
        filas = [(m.tipo_transaccion, m.signo * m.cantidad, m.saldo)
                 for m in reversed(list(respuesta.context['movimientos']))]

        self.assertEqual(filas, [
            (VENTA, 10, 10),                 # el ingreso
            (CON_TECNICO, -4, 6),            # salieron 4, y así se queda
            (TIPO.DEVOLUCION, 1, 7),         # regresó 1, en su propio día
        ])

    def test_la_existencia_es_ingresos_menos_salidas(self):
        salida = self.salida(self.celda, 3, tipo=DEMO)
        registrar_resultado(salida, usuario=self.operador, devueltas=3,
                            fecha_regreso=timezone.now(), devuelto_por='X')

        self.assertEqual(self.celda.calcular_stock_desde_movimientos(), 10)
        self.assertEqual(self.existencia(self.celda), 10)


class BoletaYListasTests(BaseSalidasAbiertas):
    def boleta_mezclada(self):
        """Una celda: 3 vendidas y 1 regresó. Un demo: pendiente."""
        celdas = self.salida(self.celda, 4)
        self.salida(self.celda, 1, tipo=DEMO)
        registrar_resultado(celdas, usuario=self.operador, vendidas=3, devueltas=1,
                            fecha_regreso=timezone.now(), devuelto_por='Pedro')
        return documentos.lineas_del_documento('SAL-00001')

    def test_la_devolucion_no_es_una_linea_mas_del_papel(self):
        lineas = self.boleta_mezclada()

        self.assertEqual(len(lineas), 2)
        self.assertEqual(documentos.totales(lineas)[0], 5, 'salieron 5, no 6')

    def test_la_pantalla_dice_tipos_y_resultado(self):
        self.boleta_mezclada()

        respuesta = self.client.get(reverse('documento_detalle', args=['SAL-00001']))

        self.assertContains(respuesta, 'Con el técnico')
        self.assertContains(respuesta, 'Préstamo / Demo')
        self.assertContains(respuesta, '3 vendidas')
        self.assertContains(respuesta, '1 regresó')
        self.assertContains(respuesta, '1 pendiente')
        self.assertContains(respuesta, 'Boleta abierta')

    def test_el_historial_separa_lo_pendiente_de_lo_por_cerrar(self):
        self.boleta_mezclada()
        self.salida(self.celda, 1, tipo=VENTA, folio='SAL-00002')

        pendientes = self.client.get(reverse('movimientos_ventas'), {'estado': 'pendientes'})
        por_cerrar = self.client.get(reverse('movimientos_ventas'), {'estado': 'por_cerrar'})

        self.assertEqual([m.folio for m in pendientes.context['movimientos']], ['SAL-00001'])
        self.assertEqual(
            sorted(m.folio for m in por_cerrar.context['movimientos']),
            ['SAL-00001', 'SAL-00002'],
            'la línea de celdas ya está resuelta aunque su boleta siga abierta',
        )

    def test_el_resumen_cuenta_boletas_abiertas(self):
        self.boleta_mezclada()
        self.salida(self.celda, 1, folio='SAL-00002')
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('resumen'))

        self.assertEqual(respuesta.context['boletas_abiertas'], 2)

    def test_fuera_de_bodega_trae_lo_que_falta_resolver(self):
        from core.reportes import prestamos_abiertos
        salida = self.salida(self.celda, 4)
        registrar_resultado(salida, usuario=self.operador, devueltas=1,
                            fecha_regreso=timezone.now(), devuelto_por='X')

        fila = [f for f in prestamos_abiertos() if f['origen'] == 'Bodega 1 y 2'][0]

        self.assertEqual(fila['cantidad'], 3, 'lo que falta, no lo que salió')
        self.assertEqual(fila['url'], reverse('salida_resultado', args=[salida.pk]))


class BoletaImpresaTests(BaseSalidasAbiertas):
    def test_las_casillas_marcan_todo_lo_que_trae(self):
        self.salida(self.celda, 1, tipo=DEMO)
        self.salida(self.celda, 1, tipo=VENTA)
        lineas = documentos.lineas_del_documento('SAL-00001')

        marcadas = boletas.casillas_marcadas(lineas, es_ingreso=False)

        self.assertEqual(marcadas & {c for c, _e in boletas.OPCIONES_TIPO}, {DEMO, VENTA})

    def test_lo_del_tecnico_marca_venta_cuando_se_vende(self):
        salida = self.salida(self.celda, 2)
        lineas = documentos.lineas_del_documento('SAL-00001')
        casillas = {c for c, _e in boletas.OPCIONES_TIPO}
        self.assertEqual(boletas.casillas_marcadas(lineas, False) & casillas, set())

        registrar_resultado(salida, usuario=self.operador, vendidas=2)
        lineas = documentos.lineas_del_documento('SAL-00001')

        self.assertEqual(boletas.casillas_marcadas(lineas, False) & casillas, {VENTA})

    def test_los_renglones_se_parten_por_resultado(self):
        salida = self.salida(self.celda, 4)
        registrar_resultado(salida, usuario=self.operador, vendidas=3, devueltas=1,
                            fecha_regreso=timezone.now(), devuelto_por='Pedro')

        renglones = boletas.renglones_de(documentos.lineas_del_documento('SAL-00001'))

        self.assertEqual([(r.cantidad, r.etiqueta) for r in renglones],
                         [(3, 'VENDIDO'), (1, 'REGRESÓ')])

    def test_si_todo_va_igual_no_lleva_etiquetas(self):
        """Lo dice la casilla de arriba; los renglones quedan como en el papel."""
        self.salida(self.celda, 2, tipo=VENTA)
        self.salida(self.celda, 1, tipo=VENTA)

        renglones = boletas.renglones_de(documentos.lineas_del_documento('SAL-00001'))

        self.assertEqual({r.etiqueta for r in renglones}, {''})

    def test_los_seriales_llevan_cada_uno_su_resultado(self):
        salida = self.salida(self.equipo, 2, unidades=['A-1', 'A-2'])
        registrar_resultado(
            salida, usuario=self.operador,
            unidades_vendidas=UnidadArticulo.objects.filter(numero_serie='A-1'),
        )

        renglones = boletas.renglones_de(documentos.lineas_del_documento('SAL-00001'))

        self.assertEqual(sorted((r.serial, r.etiqueta) for r in renglones),
                         [('A-1', 'VENDIDO'), ('A-2', 'PENDIENTE')])

    def test_el_devuelto_por_sale_de_los_regresos(self):
        salida = self.salida(self.celda, 4)
        registrar_resultado(salida, usuario=self.operador, devueltas=1,
                            fecha_regreso=timezone.now(), devuelto_por='Pedro')

        self.assertEqual(boletas.devuelto_por(documentos.lineas_del_documento('SAL-00001')), 'Pedro')

    def test_el_pdf_de_una_boleta_mezclada_se_genera(self):
        salida = self.salida(self.celda, 4)
        self.salida(self.equipo, 2, tipo=DEMO, unidades=['A-1', 'A-2'])
        registrar_resultado(salida, usuario=self.operador, vendidas=3, devueltas=1,
                            fecha_regreso=timezone.now(), devuelto_por='Pedro')

        respuesta = self.client.get(reverse('documento_pdf', args=['SAL-00001']))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
