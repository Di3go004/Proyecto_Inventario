"""
Administración → Correcciones: los errores de tipeo al cargar seriales.

Nació en la carga inicial, con dos errores en dos días: un serial que no era
de ese indicador y otro con un dígito cambiado (…342 en vez de …344). Sin
pantalla, cada uno necesitaba consola, un respaldo y alguien que supiera.

Dos correcciones, solo para el administrador:

- **Corregir el número de serie**: solo el texto. La unidad sigue siendo la
  misma, con sus boletas, y la existencia no se mueve.
- **Quitar una unidad** que no era de ese producto, como si nunca hubiera
  entrado: su línea y la existencia bajan en uno. Solo lo que nunca salió de
  bodega y no es la única unidad de su línea.

Sin rastro, por decisión de la empresa: la corrección deja el dato bien.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from usuarios.models import Usuario
from ventas import documentos
from ventas.models import (
    Articulo, MovimientoVenta, UnidadArticulo, ingresar_unidades, quitar_unidad,
    registrar_resultado, sacar_unidades, unidades_con_serial,
)

TIPO = MovimientoVenta.TipoTransaccion
INGRESO = MovimientoVenta.TipoDocumento.INGRESO
SALIDA = MovimientoVenta.TipoDocumento.SALIDA


class BaseCorrecciones(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        clave = 'clave-de-prueba'
        cls.admin = Usuario.objects.create_user(username='admin_corr', password=clave, rol=Usuario.Rol.ADMINISTRADOR)
        cls.operador = Usuario.objects.create_user(username='oper_corr', password=clave, rol=Usuario.Rol.OPERADOR)
        cls.contable = Usuario.objects.create_user(username='cont_corr', password=clave, rol=Usuario.Rol.CONTABILIDAD)
        cls.practicante = Usuario.objects.create_user(username='prac_corr', password=clave, rol=Usuario.Rol.PRACTICANTE)

    def setUp(self):
        self.client.force_login(self.admin)
        self.zm405 = Articulo.objects.create(
            nombre_producto='Indicador ZM405', modelo='ZM405', capacidad='SD3',
            bodega=self.bodega, precio=1500, lleva_serie=True,
        )
        self.indicador_7516 = Articulo.objects.create(
            nombre_producto='Indicador 7516', modelo='7516', capacidad='C',
            bodega=self.bodega, precio=900, lleva_serie=True,
        )
        self.linea = self.ingresar(self.zm405, 'ING-00380', ['260650084', '260650342', '260650349'])
        self.otra_linea = self.ingresar(self.indicador_7516, 'ING-00381', ['211115042'])

    def ingresar(self, articulo, folio, seriales):
        movimiento = MovimientoVenta.objects.create(
            articulo=articulo, tipo_documento=INGRESO, tipo_transaccion=TIPO.VENTA,
            cantidad=len(seriales), usuario=self.admin, folio=folio,
        )
        ingresar_unidades(movimiento, seriales)
        return movimiento

    def unidad(self, serial):
        return UnidadArticulo.objects.get(numero_serie=serial)

    def existencia(self, articulo):
        articulo.refresh_from_db()
        return articulo.stock_actual

    def sacar(self, serial, folio='SAL-00001', tipo=TIPO.VENTA):
        unidad = self.unidad(serial)
        salida = MovimientoVenta.objects.create(
            articulo=unidad.articulo, tipo_documento=SALIDA, tipo_transaccion=tipo,
            cantidad=1, cantidad_vendida=1 if tipo == TIPO.VENTA else 0,
            usuario=self.admin, folio=folio,
        )
        sacar_unidades(salida, [unidad], vendidas=tipo == TIPO.VENTA)
        return salida


class SoloElAdministradorTests(BaseCorrecciones):
    def test_nadie_mas_entra(self):
        urls = [
            reverse('correcciones'),
            reverse('correccion_serial', args=[self.unidad('260650342').pk]),
            reverse('correccion_quitar', args=[self.unidad('260650342').pk]),
        ]
        for usuario, codigo in ((self.admin, 200), (self.operador, 403),
                                (self.contable, 403), (self.practicante, 403)):
            self.client.force_login(usuario)
            for url in urls:
                with self.subTest(rol=usuario.rol, url=url):
                    self.assertEqual(self.client.get(url).status_code, codigo)

    def test_el_menu_la_ofrece_solo_al_administrador(self):
        enlace = f'href="{reverse("correcciones")}"'
        self.assertContains(self.client.get(reverse('catalogo_articulos')), enlace)

        self.client.force_login(self.operador)
        self.assertNotContains(self.client.get(reverse('catalogo_articulos')), enlace)

    def test_la_ficha_no_lleva_botones_de_corregir(self):
        """Pedido expreso: las pantallas de todos los días quedan limpias."""
        respuesta = self.client.get(reverse('articulo_detalle', args=[self.zm405.pk]))

        self.assertNotContains(respuesta, reverse('correccion_serial', args=[self.unidad('260650342').pk]))


class BuscarTests(BaseCorrecciones):
    def encontradas(self, q, accion='serial'):
        respuesta = self.client.get(reverse('correcciones'), {'q': q, 'accion': accion})
        return [u.numero_serie for u in respuesta.context['unidades']]

    def test_por_serial(self):
        self.assertEqual(self.encontradas('260650342'), ['260650342'])

    def test_por_codigo_o_nombre_del_producto(self):
        self.assertEqual(self.encontradas('zm405'), ['260650084', '260650342', '260650349'])
        self.assertEqual(self.encontradas('7516'), ['211115042'])

    def test_sin_busqueda_no_lista_nada(self):
        self.assertEqual(self.encontradas(''), [])

    def test_con_demasiados_resultados_pide_afinar(self):
        muchos = [f'X-{i:03d}' for i in range(55)]
        self.ingresar(self.zm405, 'ING-00999', muchos)

        respuesta = self.client.get(reverse('correcciones'), {'q': 'X-'})

        self.assertEqual(len(respuesta.context['unidades']), 50)
        self.assertContains(respuesta, 'Se muestran 50 de 55')


class CorregirSerialTests(BaseCorrecciones):
    def corregir(self, serial, nuevo):
        return self.client.post(
            reverse('correccion_serial', args=[self.unidad(serial).pk]), {'numero_serie': nuevo},
        )

    def test_corrige_el_caso_del_zm405(self):
        unidad = self.unidad('260650342')

        respuesta = self.corregir('260650342', '260650344')

        self.assertRedirects(respuesta, reverse('articulo_detalle', args=[self.zm405.pk]))
        unidad.refresh_from_db()
        self.assertEqual(unidad.numero_serie, '260650344', 'la misma unidad, con el número bueno')
        self.assertFalse(unidades_con_serial(['260650342']).exists())

    def test_la_boleta_dice_el_corregido(self):
        self.corregir('260650342', '260650344')

        seriales = documentos.lineas_del_documento('ING-00380')[0].seriales

        self.assertIn('260650344', seriales)
        self.assertNotIn('260650342', seriales)

    def test_no_mueve_nada_mas(self):
        movimientos, unidades = MovimientoVenta.objects.count(), UnidadArticulo.objects.count()

        self.corregir('260650342', '260650344')

        self.assertEqual(self.existencia(self.zm405), 3)
        self.assertEqual(MovimientoVenta.objects.count(), movimientos)
        self.assertEqual(UnidadArticulo.objects.count(), unidades)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.cantidad, 3)

    def test_se_limpia_como_al_capturarlo(self):
        self.corregir('260650342', '  260650344  ')

        self.assertTrue(UnidadArticulo.objects.filter(numero_serie='260650344').exists())

    def test_rechaza_vacio_o_sin_serial(self):
        for escrito in ('', '   ', 'S/S'):
            with self.subTest(escrito=escrito):
                respuesta = self.corregir('260650342', escrito)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self.unidad('260650342').numero_serie, '260650342')

    def test_rechaza_el_mismo(self):
        respuesta = self.corregir('260650342', '260650342')

        self.assertContains(respuesta, 'Es el mismo número de serie')

    def test_rechaza_uno_que_ya_existe_en_otro_producto(self):
        respuesta = self.corregir('260650342', '211115042')

        self.assertContains(respuesta, 'ya está registrado en')
        self.assertContains(respuesta, 'Indicador 7516')
        self.assertTrue(UnidadArticulo.objects.filter(numero_serie='260650342').exists())

    def test_rechaza_uno_del_mismo_producto_aunque_cambien_las_mayusculas(self):
        self.ingresar(self.zm405, 'ING-00382', ['ABC-1'])

        respuesta = self.corregir('260650342', 'abc-1')

        self.assertContains(respuesta, 'ya está registrado')

    def test_corregir_solo_las_mayusculas_se_puede(self):
        self.ingresar(self.zm405, 'ING-00383', ['abc-9'])

        self.corregir('abc-9', 'ABC-9')

        self.assertTrue(UnidadArticulo.objects.filter(numero_serie='ABC-9').exists())

    def test_una_que_ya_salio_se_corrige_y_avisa_del_papel(self):
        salida = self.sacar('260650342', folio='SAL-00050')
        url = reverse('correccion_serial', args=[self.unidad('260650342').pk])

        self.assertContains(self.client.get(url), 'SAL-00050')
        self.corregir('260650342', '260650344')

        self.assertEqual([u.numero_serie for u in salida.unidades.all()], ['260650344'])


class QuitarUnidadTests(BaseCorrecciones):
    def quitar(self, serial):
        return self.client.post(reverse('correccion_quitar', args=[self.unidad(serial).pk]))

    def test_quita_como_si_nunca_hubiera_entrado(self):
        respuesta = self.quitar('260650342')

        self.assertRedirects(respuesta, reverse('articulo_detalle', args=[self.zm405.pk]))
        self.assertFalse(unidades_con_serial(['260650342']).exists())
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.cantidad, 2)
        self.assertEqual(self.existencia(self.zm405), 2)
        self.assertEqual(
            sorted(u.numero_serie for u in self.zm405.unidades.all()), ['260650084', '260650349'],
        )

    def test_el_serial_queda_libre_para_su_producto(self):
        self.quitar('260650342')

        self.ingresar(self.indicador_7516, 'ING-00400', ['260650342'])

        self.assertEqual(self.unidad('260650342').articulo, self.indicador_7516)

    def test_las_demas_lineas_no_se_tocan(self):
        otra = self.ingresar(self.indicador_7516, 'ING-00380', ['211115044', '211115045'])

        self.quitar('260650342')

        otra.refresh_from_db()
        self.assertEqual(otra.cantidad, 2)
        self.assertEqual(self.existencia(self.indicador_7516), 3)

    def test_la_pantalla_dice_lo_que_va_a_cambiar(self):
        respuesta = self.client.get(reverse('correccion_quitar', args=[self.unidad('260650342').pk]))

        self.assertContains(respuesta, 'ING-00380')
        self.assertContains(respuesta, 'pasa de <strong>3</strong> a <strong>2</strong>', html=False)

    def test_no_quita_una_que_salio(self):
        self.sacar('260650342', folio='SAL-00060')

        respuesta = self.quitar('260650342')

        self.assertContains(respuesta, 'Ya salió de bodega con la boleta SAL-00060')
        self.assertTrue(unidades_con_serial(['260650342']).exists())
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.cantidad, 3)

    def test_tampoco_una_que_salio_y_regreso(self):
        """Sigue apareciendo en la boleta del demo: quitarla la descuadraría."""
        salida = self.sacar('260650342', folio='SAL-00061', tipo=TIPO.PRESTAMO_DEMO)
        registrar_resultado(
            salida, usuario=self.admin, unidades_devueltas=[self.unidad('260650342')],
            fecha_regreso=timezone.now(), devuelto_por='Pedro',
        )
        self.assertTrue(self.unidad('260650342').en_bodega)

        respuesta = self.quitar('260650342')

        self.assertContains(respuesta, 'Ya salió de bodega')
        self.assertTrue(unidades_con_serial(['260650342']).exists())

    def test_no_quita_la_unica_de_su_linea(self):
        respuesta = self.quitar('211115042')

        self.assertContains(respuesta, 'Es la única unidad de su línea')
        self.assertTrue(unidades_con_serial(['211115042']).exists())

    def test_la_puerta_tambien_lo_impide(self):
        """Las reglas viven en el modelo: valen aunque no se pase por la pantalla."""
        with self.assertRaisesMessage(ValidationError, 'Es la única unidad'):
            quitar_unidad(self.unidad('211115042'))

    def test_la_lista_dice_por_que_no_se_puede(self):
        self.sacar('260650342', folio='SAL-00062')

        respuesta = self.client.get(reverse('correcciones'), {'q': 'zm405', 'accion': 'quitar'})

        self.assertContains(respuesta, 'Ya salió de bodega con la boleta SAL-00062')
        self.assertContains(respuesta, reverse('correccion_quitar', args=[self.unidad('260650084').pk]))
        self.assertNotContains(respuesta, reverse('correccion_quitar', args=[self.unidad('260650342').pk]))

    def test_de_la_carga_inicial_tambien(self):
        """Las unidades del alta del producto entran con un ajuste sin número de boleta."""
        inicial = self.ingresar(self.zm405, '', ['C-1', 'C-2'])

        respuesta = self.quitar('C-1')

        inicial.refresh_from_db()
        self.assertEqual(inicial.cantidad, 1)
        self.assertEqual(
            [m.message for m in respuesta.wsgi_request._messages][0],
            'Se quitó el serial C-1 de "Indicador ZM405". Su línea en la carga inicial quedó en 1.',
        )
