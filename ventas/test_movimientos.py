"""
Pruebas de la Fase 3 en Bodega 1 y 2 (RF-05, RF-06, RF-13).

Lo que más importa acá es que un documento entre completo o no entre: una
boleta a medias (unas líneas guardadas y otras no) dejaría el stock
mintiendo, que es justo el problema que este sistema viene a resolver.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import Articulo, MovimientoVenta


class BaseMovimientos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.operador = Usuario.objects.create_user(
            username='operador_mov', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='contable_mov', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )
        cls.bascula = Articulo.objects.create(
            nombre_producto='Báscula de plataforma', modelo='BP-300',
            capacidad='300kg', bodega=cls.bodega, precio=1500,
        )
        cls.indicador = Articulo.objects.create(
            nombre_producto='Indicador digital', modelo='ID-100',
            capacidad='9V', bodega=cls.bodega, precio=400,
        )

    def setUp(self):
        self.client.login(username='operador_mov', password='clave-de-prueba')

    def cabecera(self, **extra):
        datos = {
            'folio': '',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'tipo_transaccion': MovimientoVenta.TipoTransaccion.VENTA,
            'solicitado_por': 'Ivan Leiva',
            'no_factura': '', 'no_boleta': '', 'observacion': '',
        }
        datos.update(extra)
        return datos

    def registrar_ingreso(self, lineas, **extra):
        """lineas: [(articulo, cantidad), ...]"""
        datos = self.cabecera(**extra)
        datos['linea_articulo'] = [str(a.pk) for a, _c in lineas]
        datos['linea_cantidad'] = [str(c) for _a, c in lineas]
        datos['linea_texto'] = [a.codigo_interno for a, _c in lineas]
        return self.client.post(reverse('movimiento_ingreso'), datos)

    def registrar_salida(self, lineas, **extra):
        datos = self.cabecera(**extra)
        datos.setdefault('entregado_por', 'Bodega')
        datos.setdefault('cliente_nombre', 'Cliente X')
        datos.setdefault('envio_recibo', '')
        datos['linea_articulo'] = [str(a.pk) for a, _c in lineas]
        datos['linea_cantidad'] = [str(c) for _a, c in lineas]
        datos['linea_texto'] = [a.codigo_interno for a, _c in lineas]
        return self.client.post(reverse('movimiento_salida'), datos)


class FolioTests(BaseMovimientos):
    def test_el_folio_es_correlativo_y_separado_por_tipo(self):
        """Igual que en el papel: FO-SE-013 y FO-SE-012 numeran aparte."""
        self.registrar_ingreso([(self.bascula, 5)])
        self.registrar_ingreso([(self.bascula, 3)])
        self.registrar_salida([(self.bascula, 1)])

        folios = list(MovimientoVenta.objects.order_by('id').values_list('folio', flat=True))
        self.assertEqual(folios, ['ING-00001', 'ING-00002', 'SAL-00001'])

    def test_el_administrador_puede_escribir_su_propio_folio(self):
        self.registrar_ingreso([(self.bascula, 5)], folio='ING-2025-077')
        self.assertEqual(MovimientoVenta.objects.get().folio, 'ING-2025-077')

    def test_un_folio_escrito_a_mano_no_rompe_el_correlativo(self):
        self.registrar_ingreso([(self.bascula, 1)], folio='ING-SIN-NUMERO')
        self.registrar_ingreso([(self.bascula, 1)])

        ultimo = MovimientoVenta.objects.order_by('id').last()
        self.assertTrue(ultimo.folio.startswith('ING-'))
        self.assertNotEqual(ultimo.folio, 'ING-SIN-NUMERO')


class DocumentoMultilineaTests(BaseMovimientos):
    def test_un_documento_guarda_todas_sus_lineas_bajo_el_mismo_folio(self):
        self.registrar_ingreso([(self.bascula, 5), (self.indicador, 12)])

        movimientos = MovimientoVenta.objects.all()
        self.assertEqual(movimientos.count(), 2)
        self.assertEqual(len({m.folio for m in movimientos}), 1, 'ambas líneas comparten folio')

        self.bascula.refresh_from_db()
        self.indicador.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 5)
        self.assertEqual(self.indicador.stock_actual, 12)

    def test_si_una_linea_no_tiene_stock_no_se_guarda_ninguna(self):
        """
        Lo importante de la prueba: la primera línea sí alcanzaba. Si el
        guardado no fuera atómico, quedaría a medias y el stock mentiría.
        """
        self.registrar_ingreso([(self.bascula, 10), (self.indicador, 10)])

        respuesta = self.registrar_salida([(self.bascula, 2), (self.indicador, 999)])

        self.assertEqual(respuesta.status_code, 200, 'se queda en el formulario')
        self.assertEqual(
            MovimientoVenta.objects.count(), 2,
            'no debe quedar guardada ni siquiera la línea que sí alcanzaba',
        )
        self.bascula.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 10)

    def test_el_mismo_articulo_dos_veces_se_acumula(self):
        self.registrar_ingreso([(self.bascula, 4), (self.bascula, 6)])
        self.bascula.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 10)

    def test_las_lineas_vacias_se_ignoran(self):
        datos = self.cabecera()
        datos['linea_articulo'] = [str(self.bascula.pk), '']
        datos['linea_cantidad'] = ['3', '']
        datos['linea_texto'] = [self.bascula.codigo_interno, '']
        self.client.post(reverse('movimiento_ingreso'), datos)

        self.assertEqual(MovimientoVenta.objects.count(), 1)

    def test_un_documento_sin_lineas_no_se_guarda(self):
        datos = self.cabecera()
        datos['linea_articulo'] = ['']
        datos['linea_cantidad'] = ['']
        datos['linea_texto'] = ['']
        respuesta = self.client.post(reverse('movimiento_ingreso'), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(MovimientoVenta.objects.count(), 0)

    def test_escribir_el_codigo_completo_alcanza_para_resolver_la_linea(self):
        """RF-13: en bodega se captura más rápido escribiendo el código y
        saltando al siguiente campo, sin bajar a la lista de sugerencias."""
        datos = self.cabecera()
        datos['linea_articulo'] = ['']  # no se eligió de la lista
        datos['linea_cantidad'] = ['7']
        datos['linea_texto'] = [self.bascula.codigo_interno]
        self.client.post(reverse('movimiento_ingreso'), datos)

        self.bascula.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 7)

    def test_una_cantidad_invalida_detiene_todo_el_documento(self):
        datos = self.cabecera()
        datos['linea_articulo'] = [str(self.bascula.pk)]
        datos['linea_cantidad'] = ['0']
        datos['linea_texto'] = [self.bascula.codigo_interno]
        respuesta = self.client.post(reverse('movimiento_ingreso'), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(MovimientoVenta.objects.count(), 0)

    def test_se_guarda_la_fecha_que_eligio_el_operador(self):
        """Las boletas de papel se digitan después, con su fecha real."""
        self.registrar_ingreso([(self.bascula, 2)], fecha='2026-08-01T09:15')

        movimiento = MovimientoVenta.objects.get()
        fecha_local = timezone.localtime(movimiento.fecha)
        self.assertEqual((fecha_local.year, fecha_local.month, fecha_local.day), (2026, 8, 1))
        self.assertEqual((fecha_local.hour, fecha_local.minute), (9, 15))


class DevolucionDemoTests(BaseMovimientos):
    def prestar(self, cantidad=2):
        self.registrar_ingreso([(self.bascula, 10)])
        self.registrar_salida(
            [(self.bascula, cantidad)],
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )
        return MovimientoVenta.objects.get(
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )

    def test_registrar_la_devolucion_regresa_el_stock(self):
        prestamo = self.prestar(cantidad=2)
        self.bascula.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 8)

        self.client.post(reverse('devolucion_demo', args=[prestamo.pk]), {
            'fecha_devolucion': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'devuelto_por': 'Ivan Leiva',
            'observacion': '',
        })

        self.bascula.refresh_from_db()
        prestamo.refresh_from_db()
        self.assertEqual(self.bascula.stock_actual, 10)
        self.assertIsNotNone(prestamo.fecha_devolucion)
        self.assertEqual(prestamo.devuelto_por, 'Ivan Leiva')

    def test_la_devolucion_no_puede_ser_anterior_a_la_salida(self):
        prestamo = self.prestar()

        respuesta = self.client.post(reverse('devolucion_demo', args=[prestamo.pk]), {
            'fecha_devolucion': '2020-01-01T08:00',
            'devuelto_por': 'Ivan Leiva',
            'observacion': '',
        })

        prestamo.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(prestamo.fecha_devolucion, 'el préstamo sigue abierto')

    def test_no_se_puede_cerrar_dos_veces_el_mismo_prestamo(self):
        prestamo = self.prestar()
        ahora = timezone.localtime().strftime('%Y-%m-%dT%H:%M')
        self.client.post(reverse('devolucion_demo', args=[prestamo.pk]), {
            'fecha_devolucion': ahora, 'devuelto_por': 'Ivan', 'observacion': '',
        })

        respuesta = self.client.post(reverse('devolucion_demo', args=[prestamo.pk]), {
            'fecha_devolucion': ahora, 'devuelto_por': 'Otro', 'observacion': '',
        })

        self.assertRedirects(respuesta, reverse('movimientos_ventas'))
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.devuelto_por, 'Ivan', 'el primer cierre es el que vale')

    def test_una_venta_normal_no_ofrece_devolucion(self):
        self.registrar_ingreso([(self.bascula, 5)])
        self.registrar_salida([(self.bascula, 1)])
        venta = MovimientoVenta.objects.get(tipo_documento=MovimientoVenta.TipoDocumento.SALIDA)

        respuesta = self.client.get(reverse('devolucion_demo', args=[venta.pk]))

        self.assertRedirects(respuesta, reverse('movimientos_ventas'))


class KardexYDocumentoTests(BaseMovimientos):
    def test_el_kardex_muestra_el_saldo_despues_de_cada_movimiento(self):
        self.registrar_ingreso([(self.bascula, 10)])
        self.registrar_salida([(self.bascula, 3)])
        self.registrar_ingreso([(self.bascula, 5)])

        respuesta = self.client.get(reverse('kardex_articulo', args=[self.bascula.pk]))
        saldos = [m.saldo for m in respuesta.context['movimientos']]

        # La vista los muestra del más nuevo al más viejo.
        self.assertEqual(saldos, [12, 7, 10])

    def test_el_documento_suma_unidades_y_quetzales(self):
        self.registrar_ingreso([(self.bascula, 2), (self.indicador, 3)])
        folio = MovimientoVenta.objects.first().folio

        respuesta = self.client.get(reverse('documento_detalle', args=[folio]))

        self.assertEqual(respuesta.context['total_unidades'], 5)
        # 2 × 1500 + 3 × 400 = 4200
        self.assertEqual(int(respuesta.context['total_quetzales']), 4200)

    def test_el_historial_filtra_solo_los_prestamos_afuera(self):
        self.registrar_ingreso([(self.bascula, 10)])
        self.registrar_salida([(self.bascula, 1)])
        self.registrar_salida(
            [(self.bascula, 2)],
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )

        respuesta = self.client.get(reverse('movimientos_ventas'), {'afuera': 'si'})
        movimientos = list(respuesta.context['movimientos'])

        self.assertEqual(len(movimientos), 1)
        self.assertTrue(movimientos[0].esta_afuera)


class BuscadorTests(BaseMovimientos):
    def test_sugiere_por_codigo_y_por_nombre(self):
        por_nombre = self.client.get(reverse('api_buscar_articulos'), {'q': 'plataforma'}).json()
        por_codigo = self.client.get(reverse('api_buscar_articulos'), {'q': 'BP-300'}).json()

        self.assertEqual(por_nombre['resultados'][0]['id'], self.bascula.pk)
        self.assertEqual(por_codigo['resultados'][0]['id'], self.bascula.pk)

    def test_no_busca_con_menos_de_dos_letras(self):
        """Con una sola letra saldría medio catálogo y no ayuda a nadie."""
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'b'}).json()
        self.assertEqual(respuesta['resultados'], [])

    def test_no_sugiere_articulos_inactivos(self):
        Articulo.objects.filter(pk=self.indicador.pk).update(activo=False)
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'Indicador'}).json()
        self.assertEqual(respuesta['resultados'], [])

    def test_pide_sesion_iniciada(self):
        self.client.logout()
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'bascula'})
        self.assertEqual(respuesta.status_code, 302, 'redirige al login')


class PermisosMovimientosTests(BaseMovimientos):
    """RF-04: contabilidad ve todo pero no registra nada."""

    def setUp(self):
        self.client.login(username='contable_mov', password='clave-de-prueba')

    def test_contabilidad_puede_ver_el_historial(self):
        self.assertEqual(self.client.get(reverse('movimientos_ventas')).status_code, 200)

    def test_contabilidad_no_puede_abrir_el_formulario_de_ingreso(self):
        self.assertEqual(self.client.get(reverse('movimiento_ingreso')).status_code, 403)

    def test_contabilidad_no_puede_registrar_una_salida(self):
        respuesta = self.registrar_salida([(self.bascula, 1)])
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(MovimientoVenta.objects.count(), 0)
