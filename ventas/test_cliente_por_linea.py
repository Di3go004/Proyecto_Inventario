"""
El cliente va en cada línea de la salida, no en el encabezado.

En el FO-SE-012 de papel "Nombre cliente" es una columna: el técnico sale
con una sola boleta y pasa por varios clientes —la 0000863 trae a Marco Cao
y a Comercializadora Santo Domingo—. Como dato del encabezado, el sistema le
ponía el mismo cliente a todas las líneas.

La columna ya existía en cada movimiento (cada línea es uno); lo que cambia
es que ahora cada línea trae el suyo desde la pantalla.
"""

import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.forms import LARGO_DEL_CLIENTE
from ventas.models import Articulo, MovimientoVenta, registrar_resultado
from ventas.test_salidas_abiertas import texto_del_pdf

TIPO = MovimientoVenta.TipoTransaccion


class BaseClientePorLinea(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.operador = Usuario.objects.create_user(
            username='operador_cl', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.patas = Articulo.objects.create(
            nombre_producto='Patas grandes para báscula', modelo='PG', bodega=cls.bodega,
            precio=Decimal('150'),
        )
        cls.adaptador = Articulo.objects.create(
            nombre_producto='Adaptador 9V', modelo='A9', bodega=cls.bodega, precio=Decimal('75'),
        )
        for articulo in (cls.patas, cls.adaptador):
            MovimientoVenta.objects.create(
                folio='ING-00001', articulo=articulo, cantidad=10,
                tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
                tipo_transaccion=TIPO.VENTA, usuario=cls.operador,
            )

    def setUp(self):
        self.client.force_login(self.operador)

    def salida(self, lineas, folio='0000863'):
        """lineas: [(articulo, cantidad, cliente)]; todas salen con el técnico."""
        return self.client.post(reverse('movimiento_salida'), {
            'folio': folio,
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'solicitado_por': 'Walter López', 'entregado_por': 'Karla Rosales',
            'envio_recibo': '', 'no_factura': '', 'observacion': '',
            'linea_articulo': [str(a.pk) for a, _c, _cl in lineas],
            'linea_cantidad': [str(c) for _a, c, _cl in lineas],
            'linea_texto': [a.codigo_interno for a, _c, _cl in lineas],
            'linea_seriales': ['' for _l in lineas],
            'linea_precio': ['' for _l in lineas],
            'linea_tipo': [TIPO.CON_TECNICO for _l in lineas],
            'linea_cliente': [cliente for _a, _c, cliente in lineas],
        })

    def la_0000863(self):
        """Tres líneas, dos clientes: como la boleta de papel."""
        return self.salida([
            (self.patas, 4, 'Marco Cao'),
            (self.patas, 6, 'Marco Cao'),
            (self.adaptador, 3, 'Comercializadora Santo Domingo'),
        ])

    def clientes_guardados(self, folio='0000863'):
        return list(
            MovimientoVenta.objects.filter(folio=folio).order_by('pk')
            .values_list('cliente_nombre', flat=True)
        )


class AlRegistrarTests(BaseClientePorLinea):
    def test_cada_linea_guarda_su_cliente(self):
        respuesta = self.la_0000863()

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            self.clientes_guardados(),
            ['Marco Cao', 'Marco Cao', 'Comercializadora Santo Domingo'],
        )

    def test_el_cliente_es_opcional(self):
        # Lo que se lleva el técnico a veces todavía no tiene cliente.
        self.salida([(self.patas, 1, ''), (self.adaptador, 1, 'Marco Cao')])
        self.assertEqual(self.clientes_guardados(), ['', 'Marco Cao'])

    def test_el_encabezado_ya_no_pide_cliente_y_cada_linea_si(self):
        respuesta = self.client.get(reverse('movimiento_salida'))

        self.assertNotIn('cliente_nombre', respuesta.context['form'].fields)
        # La pantalla llega sin líneas y el navegador agrega la primera desde
        # la plantilla, así que es ahí donde tiene que estar el campo.
        plantilla = respuesta.content.decode().split('id="plantilla-linea"')[1]
        self.assertIn('name="linea_cliente"', plantilla)

    def test_el_ingreso_no_lleva_cliente(self):
        respuesta = self.client.get(reverse('movimiento_ingreso'))
        self.assertNotContains(respuesta, 'name="linea_cliente"')

        # Aunque llegara uno, lo que entra viene de un proveedor, no de un cliente.
        self.client.post(reverse('movimiento_ingreso'), {
            'folio': 'ING-00099', 'tipo_transaccion': TIPO.VENTA,
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'solicitado_por': 'Bodega', 'no_factura': '', 'observacion': '',
            'linea_articulo': [str(self.patas.pk)], 'linea_cantidad': ['2'],
            'linea_texto': [self.patas.codigo_interno], 'linea_seriales': [''],
            'linea_precio': [''], 'linea_cliente': ['Alguien'],
        })
        self.assertEqual(self.clientes_guardados('ING-00099'), [''])

    def test_si_la_boleta_no_se_guarda_cada_linea_conserva_su_cliente(self):
        # La segunda línea pide más de lo que hay: no se guarda nada, y la
        # pantalla vuelve con lo escrito para no empezar de nuevo.
        respuesta = self.salida([
            (self.patas, 2, 'Marco Cao'),
            (self.adaptador, 99, 'Comercializadora Santo Domingo'),
        ])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.clientes_guardados(), [])
        self.assertContains(respuesta, 'value="Marco Cao"')
        self.assertContains(respuesta, 'value="Comercializadora Santo Domingo"')

    def test_un_cliente_demasiado_largo_se_avisa_en_su_linea(self):
        largo = 'x' * (LARGO_DEL_CLIENTE + 1)
        respuesta = self.salida([(self.patas, 1, largo)])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.clientes_guardados(), [])
        self.assertContains(respuesta, f'no puede pasar de {LARGO_DEL_CLIENTE} letras')


class AlVerLaBoletaTests(BaseClientePorLinea):
    def setUp(self):
        super().setUp()
        self.la_0000863()

    def test_el_encabezado_dice_los_clientes_sin_repetir(self):
        respuesta = self.client.get(reverse('documento_detalle', args=['0000863']))

        self.assertEqual(respuesta.context['clientes'], ['Marco Cao', 'Comercializadora Santo Domingo'])
        self.assertContains(respuesta, '<dt>Clientes</dt>', html=True)
        self.assertContains(respuesta, '<dd>Marco Cao, Comercializadora Santo Domingo</dd>', html=True)

    def test_cada_linea_dice_su_cliente(self):
        contenido = self.client.get(reverse('documento_detalle', args=['0000863'])).content.decode()

        # El texto que se ve en cada celda, no lo que diga en algún atributo:
        # el nombre también va en el title, y ahí taparía un error.
        visibles = [
            texto.strip()
            for texto in re.findall(r'<td data-etiqueta="Cliente"[^>]*>([^<]*)</td>', contenido)
        ]
        self.assertEqual(visibles, ['Marco Cao', 'Marco Cao', 'Comercializadora Santo Domingo'])

    def test_con_un_solo_cliente_dice_cliente(self):
        # Adaptadores: las patas ya salieron todas con la 0000863.
        self.salida([(self.adaptador, 1, 'Marco Cao'), (self.adaptador, 2, 'Marco Cao')], folio='0000864')
        self.assertEqual(self.clientes_guardados('0000864'), ['Marco Cao', 'Marco Cao'])
        respuesta = self.client.get(reverse('documento_detalle', args=['0000864']))
        self.assertContains(respuesta, '<dt>Cliente</dt>', html=True)
        self.assertContains(respuesta, '<dd>Marco Cao</dd>', html=True)

    def test_la_boleta_impresa_lleva_el_cliente_de_cada_renglon(self):
        texto = texto_del_pdf(self.client.get(reverse('documento_pdf', args=['0000863'])).content)
        self.assertIn('Marco Cao', texto)
        self.assertIn('Comercializadora Santo Domingo', texto)

    def test_lo_devuelto_queda_con_el_cliente_de_su_linea(self):
        linea = MovimientoVenta.objects.get(folio='0000863', articulo=self.adaptador)
        registrar_resultado(
            linea, usuario=self.operador, devueltas=3,
            fecha_regreso=timezone.now(), devuelto_por='Walter López',
        )
        devolucion = linea.devoluciones.get()
        self.assertEqual(devolucion.cliente_nombre, 'Comercializadora Santo Domingo')

    def test_el_historial_encuentra_la_boleta_por_cualquiera_de_sus_clientes(self):
        for cliente in ('Marco Cao', 'Santo Domingo'):
            with self.subTest(cliente=cliente):
                respuesta = self.client.get(reverse('movimientos_ventas'), {'q': cliente})
                self.assertContains(respuesta, '0000863')
