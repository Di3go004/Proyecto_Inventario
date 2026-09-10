"""
Las unidades entran y salen por las boletas (Fase B).

La Fase A dejó los seriales entrando solo por el catálogo, en la carga
inicial. Faltaba lo demás, y ahí había un hoyo: un ingreso de un producto que
lleva serie subía la existencia sin crear ninguna unidad, así que el producto
quedaba con existencia 6 y cuatro seriales, sin que nadie se enterara.

Acá se cierra por los dos lados:

  - un ingreso de un producto con serie **exige** los seriales;
  - una salida **elige** cuáles de los que hay en bodega salen.

Y en los dos casos la cantidad no se escribe: es cuántos seriales trae la
línea. El descuadre no queda validado, queda imposible.

El caso que decidió el diseño está en `DemoQueVaYVuelveTests`: un equipo que
sale a demo, regresa y vuelve a salir. Con una sola llave de salida en la
unidad, la segunda salida le pisaba la primera y la boleta del demo se
quedaba sin sus seriales — un documento ya firmado cambiando solo.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas.models import (
    Articulo, MovimientoUnidad, MovimientoVenta, UnidadArticulo, ingresar_unidades,
)


class BaseUnidadesEnMovimientos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.admin = Usuario.objects.create_user(
            username='admin_uxm', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.equipo = Articulo.objects.create(
            nombre_producto='INDICADOR SE7581P', modelo='SE7581P',
            bodega=cls.bodega, precio=5500, lleva_serie=True,
        )
        cls.repuesto = Articulo.objects.create(
            nombre_producto='CONECTOR RJ45', modelo='C-1', bodega=cls.bodega, precio=25,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def cabecera(self, **extra):
        datos = {
            'folio': '',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'tipo_transaccion': MovimientoVenta.TipoTransaccion.VENTA,
            'solicitado_por': 'Ivan Leiva',
            'no_factura': '', 'observacion': '',
        }
        datos.update(extra)
        return datos

    def ingresar(self, lineas, **extra):
        """lineas: [(articulo, cantidad, 'A-1\nA-2'), ...]"""
        datos = self.cabecera(**extra)
        datos['linea_articulo'] = [str(a.pk) for a, _c, _s in lineas]
        datos['linea_cantidad'] = [str(c) for _a, c, _s in lineas]
        datos['linea_texto'] = [a.codigo_interno for a, _c, _s in lineas]
        datos['linea_seriales'] = [s for _a, _c, s in lineas]
        datos['linea_precio'] = ['' for _l in lineas]
        return self.client.post(reverse('movimiento_ingreso'), datos)

    def sacar(self, lineas, **extra):
        datos = self.cabecera(**extra)
        datos.setdefault('entregado_por', 'Bodega')
        datos.setdefault('cliente_nombre', 'Cliente X')
        datos.setdefault('envio_recibo', '')
        datos['linea_articulo'] = [str(a.pk) for a, _c, _s in lineas]
        datos['linea_cantidad'] = [str(c) for _a, c, _s in lineas]
        datos['linea_texto'] = [a.codigo_interno for a, _c, _s in lineas]
        datos['linea_seriales'] = [s for _a, _c, s in lineas]
        datos['linea_precio'] = ['' for _l in lineas]
        return self.client.post(reverse('movimiento_salida'), datos)

    def con_unidades(self, *seriales):
        """Deja el equipo con esas unidades en bodega, por la puerta normal."""
        movimiento = MovimientoVenta.objects.create(
            articulo=self.equipo,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL,
            cantidad=len(seriales), usuario=self.admin, folio='ING-INICIAL',
        )
        ingresar_unidades(movimiento, seriales)
        self.equipo.refresh_from_db()
        return movimiento


class IngresoConSerialesTests(BaseUnidadesEnMovimientos):
    def test_los_seriales_de_la_boleta_se_vuelven_unidades(self):
        self.ingresar([(self.equipo, 2, 'A-1001\nA-1002')])

        self.assertEqual(
            sorted(self.equipo.unidades.values_list('numero_serie', flat=True)),
            ['A-1001', 'A-1002'],
        )

    def test_las_unidades_quedan_atadas_a_esa_boleta(self):
        self.ingresar([(self.equipo, 2, 'A-1001\nA-1002')])

        movimiento = MovimientoVenta.objects.get(articulo=self.equipo)
        self.assertEqual(movimiento.unidades.count(), 2)

    def test_existencia_y_unidades_dicen_lo_mismo(self):
        """
        Es la razón de todo esto: antes el ingreso subía la existencia sin
        crear unidades, y el producto quedaba diciendo 6 de existencia con
        cuatro seriales.
        """
        self.con_unidades('A-1001', 'A-1002', 'A-1003', 'A-1004')

        self.ingresar([(self.equipo, 2, 'A-2001\nA-2002')])

        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.stock_actual, 6)
        self.assertEqual(self.equipo.unidades_en_bodega, 6)

    def test_sin_seriales_no_se_guarda(self):
        """El hoyo que se está cerrando."""
        respuesta = self.ingresar([(self.equipo, 2, '')])

        self.assertEqual(respuesta.status_code, 200, 'debió volver al formulario')
        self.assertFalse(MovimientoVenta.objects.filter(articulo=self.equipo).exists())
        self.assertContains(respuesta, 'número de serie')

    def test_la_cantidad_sale_de_los_seriales(self):
        """Escribir 9 y traer 2 seriales guarda 2, no 9."""
        self.ingresar([(self.equipo, 9, 'A-1001\nA-1002')])

        movimiento = MovimientoVenta.objects.get(articulo=self.equipo)
        self.assertEqual(movimiento.cantidad, 2)
        self.assertEqual(self.equipo.unidades.count(), 2)

    def test_un_serial_que_ya_existe_se_rechaza(self):
        self.con_unidades('A-1001')

        respuesta = self.ingresar([(self.equipo, 1, 'A-1001')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrado')
        self.assertEqual(UnidadArticulo.objects.count(), 1)

    def test_el_mismo_serial_en_dos_lineas_se_rechaza(self):
        respuesta = self.ingresar([
            (self.equipo, 1, 'A-1001'),
            (self.equipo, 1, 'A-1001'),
        ])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'repetido en este documento')
        self.assertEqual(UnidadArticulo.objects.count(), 0)

    def test_un_repuesto_no_acepta_seriales(self):
        respuesta = self.ingresar([(self.repuesto, 500, 'A-1001')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no se controla por número de serie')

    def test_un_repuesto_sigue_entrando_por_cantidad(self):
        """Lo que no lleva serie no cambió en nada."""
        self.ingresar([(self.repuesto, 500, '')])

        self.repuesto.refresh_from_db()
        self.assertEqual(self.repuesto.stock_actual, 500)
        self.assertEqual(self.repuesto.unidades.count(), 0)


class SalidaEligeElSerialTests(BaseUnidadesEnMovimientos):
    def setUp(self):
        super().setUp()
        self.con_unidades('A-1001', 'A-1002', 'A-1003', 'A-1004')

    def test_el_serial_elegido_deja_de_estar_en_bodega(self):
        self.sacar([(self.equipo, 1, 'A-1002')])

        unidad = UnidadArticulo.objects.get(numero_serie='A-1002')
        self.assertFalse(unidad.en_bodega)

    def test_los_demas_siguen_en_bodega(self):
        self.sacar([(self.equipo, 1, 'A-1002')])

        quedan = UnidadArticulo.objects.en_bodega().values_list('numero_serie', flat=True)
        self.assertEqual(sorted(quedan), ['A-1001', 'A-1003', 'A-1004'])

    def test_existencia_y_unidades_bajan_juntas(self):
        self.sacar([(self.equipo, 2, 'A-1001\nA-1002')])

        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.stock_actual, 2)
        self.assertEqual(self.equipo.unidades_en_bodega, 2)

    def test_la_cantidad_sale_de_cuantos_se_eligieron(self):
        self.sacar([(self.equipo, 1, 'A-1001\nA-1002\nA-1003')])

        movimiento = MovimientoVenta.objects.get(
            tipo_documento=MovimientoVenta.TipoDocumento.SALIDA,
        )
        self.assertEqual(movimiento.cantidad, 3)

    def test_no_se_puede_sacar_un_serial_inventado(self):
        respuesta = self.sacar([(self.equipo, 1, 'A-9999')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no está en bodega')
        self.assertEqual(self.equipo.unidades.en_bodega().count(), 4)

    def test_no_se_puede_sacar_uno_que_ya_salio(self):
        self.sacar([(self.equipo, 1, 'A-1002')], folio='SAL-00001')

        respuesta = self.sacar([(self.equipo, 1, 'A-1002')], folio='SAL-00002')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no está en bodega')

    def test_no_se_puede_sacar_el_serial_de_otro_producto(self):
        otro = Articulo.objects.create(
            nombre_producto='OTRO INDICADOR', modelo='X-9',
            bodega=self.bodega, precio=100, lleva_serie=True,
        )

        respuesta = self.sacar([(otro, 1, 'A-1001')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no es de')

    def test_sin_elegir_ninguno_no_se_guarda(self):
        respuesta = self.sacar([(self.equipo, 1, '')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'número de serie')

    def test_la_pantalla_ofrece_los_que_hay_en_bodega(self):
        """
        El operador no teclea el serial de memoria: la línea le muestra los
        que ese producto tiene en bodega.
        """
        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'INDICADOR'})

        resultado = respuesta.json()['resultados'][0]
        self.assertTrue(resultado['lleva_serie'])
        self.assertEqual(sorted(resultado['seriales']),
                         ['A-1001', 'A-1002', 'A-1003', 'A-1004'])

    def test_los_que_ya_salieron_no_se_ofrecen(self):
        self.sacar([(self.equipo, 1, 'A-1001')])

        respuesta = self.client.get(reverse('api_buscar_articulos'), {'q': 'INDICADOR'})

        resultado = respuesta.json()['resultados'][0]
        self.assertNotIn('A-1001', resultado['seriales'])


class DemoQueVaYVuelveTests(BaseUnidadesEnMovimientos):
    """
    El caso que decidió el diseño.

    Un indicador sale a demostración, regresa, y meses después se vende. Con
    una sola llave `movimiento_salida` en la unidad, la venta le pisaba el
    demo: la boleta del demo dejaba de decir qué equipo había salido. Un
    documento firmado no puede cambiar solo, así que el paradero de la unidad
    se deriva de sus movimientos, igual que la existencia del producto.
    """

    def setUp(self):
        super().setUp()
        self.con_unidades('A-1001', 'A-1002')

    def prestar(self, serial, folio):
        return self.sacar(
            [(self.equipo, 1, serial)], folio=folio,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )

    def devolver(self, movimiento):
        return self.client.post(reverse('devolucion_demo', args=[movimiento.pk]), {
            'fecha_devolucion': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'devuelto_por': 'Ivan Leiva', 'observacion': '',
        })

    def test_mientras_esta_afuera_no_esta_en_bodega(self):
        self.prestar('A-1001', 'SAL-00001')

        self.assertFalse(UnidadArticulo.objects.get(numero_serie='A-1001').en_bodega)
        self.assertEqual(self.equipo.unidades_en_bodega, 1)

    def test_al_devolverlo_vuelve_a_bodega_solo(self):
        """
        Nadie destilda nada: la devolución vuelve el movimiento neto cero, y
        con eso la unidad vuelve a contar. Es la misma regla que ya devolvía
        la existencia del producto.
        """
        self.prestar('A-1001', 'SAL-00001')
        movimiento = MovimientoVenta.objects.get(folio='SAL-00001')

        self.devolver(movimiento)

        self.assertTrue(UnidadArticulo.objects.get(numero_serie='A-1001').en_bodega)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.stock_actual, 2)
        self.assertEqual(self.equipo.unidades_en_bodega, 2)

    def test_devuelto_se_puede_volver_a_sacar(self):
        self.prestar('A-1001', 'SAL-00001')
        self.devolver(MovimientoVenta.objects.get(folio='SAL-00001'))

        respuesta = self.sacar([(self.equipo, 1, 'A-1001')], folio='SAL-00002')

        self.assertEqual(respuesta.status_code, 302, 'debió poder salir otra vez')
        self.assertFalse(UnidadArticulo.objects.get(numero_serie='A-1001').en_bodega)

    def test_la_boleta_del_demo_sigue_diciendo_su_serial(self):
        """La que motivó el rediseño: un documento firmado no cambia solo."""
        self.prestar('A-1001', 'SAL-00001')
        self.devolver(MovimientoVenta.objects.get(folio='SAL-00001'))
        self.sacar([(self.equipo, 1, 'A-1001')], folio='SAL-00002')

        from ventas import documentos
        demo = documentos.lineas_del_documento('SAL-00001')[0]
        venta = documentos.lineas_del_documento('SAL-00002')[0]

        self.assertEqual(demo.seriales, ['A-1001'])
        self.assertEqual(venta.seriales, ['A-1001'])


class BorrarUnMovimientoDevuelveLaUnidadTests(BaseUnidadesEnMovimientos):
    def test_borrar_la_salida_la_regresa_a_bodega(self):
        """
        Igual que con la existencia: borrar una salida la devuelve. Si el
        vínculo fuera protegido, la existencia volvería y la unidad no, y las
        dos cuentas quedarían diciendo cosas distintas.
        """
        self.con_unidades('A-1001')
        self.sacar([(self.equipo, 1, 'A-1001')], folio='SAL-00001')

        MovimientoVenta.objects.get(folio='SAL-00001').delete()

        self.assertTrue(UnidadArticulo.objects.get(numero_serie='A-1001').en_bodega)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.stock_actual, 1)
        self.assertEqual(self.equipo.unidades_en_bodega, 1)

    def test_la_unidad_no_se_borra_con_el_movimiento(self):
        self.con_unidades('A-1001')
        self.sacar([(self.equipo, 1, 'A-1001')], folio='SAL-00001')

        MovimientoVenta.objects.get(folio='SAL-00001').delete()

        self.assertTrue(UnidadArticulo.objects.filter(numero_serie='A-1001').exists())
        self.assertEqual(MovimientoUnidad.objects.count(), 1, 'queda solo el ingreso')


class LaBoletaLlevaLosSerialesTests(BaseUnidadesEnMovimientos):
    def test_la_pantalla_del_documento_los_muestra(self):
        self.ingresar([(self.equipo, 2, 'A-1001\nA-1002')], folio='ING-00050')

        respuesta = self.client.get(reverse('documento_detalle', args=['ING-00050']))

        self.assertContains(respuesta, 'A-1001')
        self.assertContains(respuesta, 'A-1002')

    def test_el_pdf_los_imprime(self):
        self.ingresar([(self.equipo, 2, 'A-1001\nA-1002')], folio='ING-00050')

        from ventas import boletas
        texto = boletas.boleta_documento('ING-00050').decode('latin-1', 'ignore')

        # Los seriales viajan dentro de los flujos comprimidos del PDF, así que
        # se comprueba sobre los renglones que se le mandan a armar.
        from ventas import documentos
        renglones = boletas.renglones_de(documentos.lineas_del_documento('ING-00050'))
        self.assertEqual([r.serial for r in renglones], ['A-1001', 'A-1002'])
        self.assertTrue(texto.startswith('%PDF'))

    def test_un_renglon_por_unidad(self):
        """
        Cuatro indicadores del mismo modelo son cuatro renglones, cada uno con
        su serial. En un solo renglón de cantidad 4 los seriales no caben en la
        columna del papel, y recortarlos deja la boleta sin el dato.
        """
        self.ingresar([(self.equipo, 4, 'A-1\nA-2\nA-3\nA-4')], folio='ING-00051')

        from ventas import boletas, documentos
        renglones = boletas.renglones_de(documentos.lineas_del_documento('ING-00051'))

        self.assertEqual(len(renglones), 4)
        self.assertEqual([r.cantidad for r in renglones], [1, 1, 1, 1])

    def test_un_repuesto_sigue_siendo_un_solo_renglon(self):
        self.ingresar([(self.repuesto, 500, '')], folio='ING-00052')

        from ventas import boletas, documentos
        renglones = boletas.renglones_de(documentos.lineas_del_documento('ING-00052'))

        self.assertEqual(len(renglones), 1)
        self.assertEqual(renglones[0].cantidad, 500)
        self.assertEqual(renglones[0].serial, '')


class BorrarElArticuloTests(BaseUnidadesEnMovimientos):
    def test_se_puede_borrar_uno_recien_creado_con_sus_unidades(self):
        """
        Las unidades protegen al artículo, así que borrar un producto con
        seriales reventaba con un error de servidor. El ajuste inicial y sus
        unidades son el conteo de arranque, no historial: se van con él.
        """
        self.con_unidades('A-1001', 'A-1002')

        respuesta = self.client.post(reverse('articulo_eliminar', args=[self.equipo.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Articulo.objects.filter(pk=self.equipo.pk).exists())
        self.assertEqual(UnidadArticulo.objects.count(), 0)

    def test_con_movimientos_de_verdad_sigue_sin_poder_borrarse(self):
        self.con_unidades('A-1001')
        self.sacar([(self.equipo, 1, 'A-1001')])

        self.client.post(reverse('articulo_eliminar', args=[self.equipo.pk]))

        self.assertTrue(Articulo.objects.filter(pk=self.equipo.pk).exists())


class LaCajaSoloSaleDondeCorrespondeTests(BaseUnidadesEnMovimientos):
    """
    El campo de seriales no debe verse en un producto que no lleva serie: no
    hay nada que escribir ahí, y verlo hace dudar de si falta llenarlo.

    Se rompió una vez de una forma que ninguna prueba de servidor agarraba: el
    HTML traía bien el atributo `hidden`, pero la regla de CSS `.seriales
    { display: flex }` le gana, y la caja se veía en todos los productos.
    """

    def caja_de_la_linea(self, respuesta):
        import re
        html = respuesta.content.decode()
        return re.findall(r'<div class="seriales linea-seriales"[^>]*>', html)

    def test_una_linea_nueva_arranca_escondida(self):
        """La plantilla de la que se clonan las líneas del documento."""
        respuesta = self.client.get(reverse('movimiento_ingreso'))

        cajas = self.caja_de_la_linea(respuesta)
        self.assertEqual(len(cajas), 1)
        self.assertIn('hidden', cajas[0])

    def test_al_repintar_un_producto_sin_serie_va_escondida(self):
        # cantidad 0 hace rebotar el documento y repintar la línea
        respuesta = self.sacar([(self.repuesto, 0, '')])

        de_la_fila = self.caja_de_la_linea(respuesta)[0]
        self.assertIn('hidden', de_la_fila)

    def test_al_repintar_un_producto_con_serie_va_visible(self):
        respuesta = self.sacar([(self.equipo, 0, '')])

        de_la_fila = self.caja_de_la_linea(respuesta)[0]
        self.assertNotIn('hidden', de_la_fila)

    def test_la_hoja_de_estilo_deja_que_hidden_gane(self):
        """
        Guardia de esa regresión. `display: flex` en `.seriales` anula el
        `hidden` del HTML, y desde el servidor todo se ve correcto.
        """
        from pathlib import Path

        from django.conf import settings

        hoja = Path(settings.BASE_DIR) / 'static' / 'css' / 'app.css'
        self.assertIn('.seriales[hidden]', hoja.read_text(encoding='utf-8'))


class LaFichaLlevaALaBoletaTests(BaseUnidadesEnMovimientos):
    def test_la_fila_entera_del_movimiento_es_el_enlace(self):
        """
        Como en el catálogo y en Entradas y salidas: se hace clic en cualquier
        parte de la fila. Antes solo el número de boleta era enlace y había
        que apuntarle, que es lo único del sistema que se comportaba así.
        """
        self.ingresar([(self.equipo, 1, 'A-1001')], folio='ING-00080')

        respuesta = self.client.get(reverse('articulo_detalle', args=[self.equipo.pk]))

        self.assertContains(
            respuesta,
            f'data-href="{reverse("documento_detalle", args=["ING-00080"])}"',
        )


class ElSerialRepetidoSeAvisaATiempoTests(BaseUnidadesEnMovimientos):
    """
    La restricción son el índice único y la validación del formulario. Lo que
    faltaba era decirlo **mientras se escribe**: con doscientos seriales
    cargados, enterarse al guardar obliga a buscar cuál de todos era.
    """

    def consultar(self, texto):
        return self.client.get(
            reverse('api_seriales_ocupados'), {'seriales': texto},
        ).json()['ocupados']

    def test_dice_cuales_ya_estan_y_en_que_producto(self):
        self.con_unidades('A-1001', 'A-1002')

        ocupados = self.consultar('A-1001\nA-9999\nA-1002')

        self.assertEqual(
            ocupados, {'A-1001': 'INDICADOR SE7581P', 'A-1002': 'INDICADOR SE7581P'},
        )

    def test_uno_libre_no_sale(self):
        self.con_unidades('A-1001')

        self.assertEqual(self.consultar('A-9999'), {})

    def test_acepta_la_lista_pegada_con_comas_o_tabuladores(self):
        self.con_unidades('A-1001', 'A-1002')

        self.assertEqual(len(self.consultar('A-1001,A-1002')), 2)
        self.assertEqual(len(self.consultar('A-1001\tA-1002')), 2)

    def test_no_distingue_mayusculas(self):
        """
        Un aparato es el mismo se escriba como se escriba. Si acá distinguiera,
        el aviso diría que "abc-1" está libre teniendo ya "ABC-1".
        """
        self.con_unidades('ABC-1')

        self.assertEqual(list(self.consultar('abc-1')), ['ABC-1'])

    def test_hay_que_haber_iniciado_sesion(self):
        self.client.logout()

        respuesta = self.client.get(reverse('api_seriales_ocupados'), {'seriales': 'A-1'})

        self.assertNotEqual(respuesta.status_code, 200)


class LasTresPantallasComparanIgualTests(BaseUnidadesEnMovimientos):
    """
    El alta comparaba sin distinguir mayúsculas y el ingreso sí. Con "ABC-1"
    ya registrado, el alta rechazaba "abc-1" pero la boleta de ingreso lo
    dejaba pasar, y quedaban dos unidades para el mismo aparato físico.
    """

    def test_el_ingreso_rechaza_el_mismo_serial_en_otras_mayusculas(self):
        self.con_unidades('ABC-1')

        respuesta = self.ingresar([(self.equipo, 1, 'abc-1')])

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrado')
        self.assertEqual(UnidadArticulo.objects.count(), 1)

    def test_el_alta_del_producto_tambien(self):
        self.con_unidades('ABC-1')

        respuesta = self.client.post(reverse('articulo_nuevo'), {
            'codigo_interno': '', 'nombre_producto': 'OTRO EQUIPO', 'marca': '',
            'modelo': 'X-9', 'capacidad': '', 'bodega': self.bodega.pk,
            'categoria': '', 'proveedor': '', 'precio': '100', 'imagen_url': '',
            'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2,
            'activo': 'on', 'lleva_serie': 'on', 'seriales': 'abc-1',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya está registrado')


class LaFilaDeLaUnidadLlevaASuBoletaTests(BaseUnidadesEnMovimientos):
    """
    Una unidad tiene dos boletas —con cuál entró y con cuál salió— y la fila
    un solo destino. Se toma la que contesta la pregunta con la que uno abre
    esta tabla: dónde está hoy.
    """

    def fila_de(self, serial):
        from ventas.models import UnidadArticulo
        return UnidadArticulo.objects.get(numero_serie=serial)

    def test_en_bodega_lleva_a_la_boleta_de_ingreso(self):
        self.ingresar([(self.equipo, 1, 'A-1001')], folio='ING-00070')

        self.assertEqual(self.fila_de('A-1001').boleta_de_referencia, 'ING-00070')

    def test_si_ya_salio_lleva_a_la_de_salida(self):
        """La que interesa de una unidad que no está es a dónde se fue."""
        self.ingresar([(self.equipo, 1, 'A-1001')], folio='ING-00070')
        self.sacar([(self.equipo, 1, 'A-1001')], folio='SAL-00070')

        self.assertEqual(self.fila_de('A-1001').boleta_de_referencia, 'SAL-00070')

    def test_un_demo_devuelto_vuelve_a_apuntar_al_ingreso(self):
        """Está de vuelta en bodega, así que su salida ya no la explica."""
        self.ingresar([(self.equipo, 1, 'A-1001')], folio='ING-00070')
        self.sacar(
            [(self.equipo, 1, 'A-1001')], folio='SAL-00070',
            tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        )
        movimiento = MovimientoVenta.objects.get(folio='SAL-00070')
        self.client.post(reverse('devolucion_demo', args=[movimiento.pk]), {
            'fecha_devolucion': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'devuelto_por': 'Ivan Leiva', 'observacion': '',
        })

        self.assertEqual(self.fila_de('A-1001').boleta_de_referencia, 'ING-00070')

    def test_la_carga_inicial_no_tiene_boleta_y_la_fila_no_enlaza(self):
        """El ajuste de saldo del alta no lleva folio: no hubo papel."""
        inicial = MovimientoVenta.objects.create(
            articulo=self.equipo, cantidad=1,
            tipo_documento=MovimientoVenta.TipoDocumento.INGRESO,
            tipo_transaccion=MovimientoVenta.TipoTransaccion.AJUSTE_INICIAL,
            usuario=self.admin,
        )
        ingresar_unidades(inicial, ['A-2001'])

        self.assertEqual(self.fila_de('A-2001').boleta_de_referencia, '')

    def test_la_ficha_pinta_el_enlace_en_la_fila(self):
        self.ingresar([(self.equipo, 1, 'A-1001')], folio='ING-00070')

        respuesta = self.client.get(reverse('articulo_detalle', args=[self.equipo.pk]))

        self.assertContains(
            respuesta,
            f'data-href="{reverse("documento_detalle", args=["ING-00070"])}"',
        )
