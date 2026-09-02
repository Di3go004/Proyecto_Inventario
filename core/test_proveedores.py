"""
Pruebas de la pantalla de proveedores (RF-02/RF-03).

Antes no existía: los proveedores se creaban solos —por la carga masiva del
Excel o al escribirlos en el formulario de un producto— y no había forma de
corregirlos ni de borrar los que entraron por error. Así aparecieron
proveedores llamados "-" y "-----", sacados de celdas del Excel con guiones.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Bodega, Proveedor
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo


class BaseProveedores(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_prov', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='op_prov', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extra):
        datos = {
            'nombre': 'FERRETERIA EL TORNILLO',
            'origen': Proveedor.Origen.LOCAL,
            'contacto': '', 'telefono': '',
        }
        datos.update(extra)
        return datos


class PermisosTests(BaseProveedores):
    def test_solo_el_administrador_entra(self):
        self.client.force_login(self.operador)
        for nombre in ('lista_proveedores', 'proveedor_nuevo'):
            respuesta = self.client.get(reverse(nombre))
            self.assertIn(respuesta.status_code, (302, 403), f'{nombre} quedó abierta al operador')

    def test_el_administrador_ve_la_lista(self):
        self.assertEqual(self.client.get(reverse('lista_proveedores')).status_code, 200)


class CrearYEditarTests(BaseProveedores):
    def test_crea_un_proveedor(self):
        respuesta = self.client.post(reverse('proveedor_nuevo'), self.datos())

        self.assertRedirects(respuesta, reverse('lista_proveedores'))
        self.assertTrue(Proveedor.objects.filter(nombre='FERRETERIA EL TORNILLO').exists())

    def test_guarda_el_origen(self):
        self.client.post(reverse('proveedor_nuevo'), self.datos(
            nombre='LOCOSC', origen=Proveedor.Origen.EXTRANJERO,
        ))

        proveedor = Proveedor.objects.get(nombre='LOCOSC')
        self.assertTrue(proveedor.es_extranjero)
        self.assertFalse(proveedor.sin_clasificar)

    def test_guarda_contacto_y_telefono(self):
        """Los campos existían en el modelo pero no había dónde llenarlos."""
        self.client.post(reverse('proveedor_nuevo'), self.datos(
            contacto='Marisol Pérez', telefono='2222-3333',
        ))

        proveedor = Proveedor.objects.get(nombre='FERRETERIA EL TORNILLO')
        self.assertEqual(proveedor.contacto, 'Marisol Pérez')
        self.assertEqual(proveedor.telefono, '2222-3333')

    def test_no_permite_dos_con_el_mismo_nombre(self):
        """El Excel trae el mismo proveedor con distinta capitalización."""
        Proveedor.objects.create(nombre='BRECKNELL')

        respuesta = self.client.post(reverse('proveedor_nuevo'), self.datos(nombre='brecknell'))

        self.assertEqual(respuesta.status_code, 200, 'debe volver al formulario con el error')
        self.assertEqual(Proveedor.objects.filter(nombre__iexact='brecknell').count(), 1)

    def test_junta_los_espacios_de_en_medio(self):
        self.client.post(reverse('proveedor_nuevo'), self.datos(nombre='AVERY  WEIGH   TRONIX'))

        self.assertTrue(Proveedor.objects.filter(nombre='AVERY WEIGH TRONIX').exists())

    def test_editar_no_desasigna_los_productos(self):
        proveedor = Proveedor.objects.create(nombre='CELASA')
        articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=self.bodega, proveedor=proveedor,
        )

        self.client.post(reverse('proveedor_editar', args=[proveedor.pk]), self.datos(
            nombre='CELASA, S.A.', origen=Proveedor.Origen.LOCAL,
        ))

        articulo.refresh_from_db()
        self.assertEqual(articulo.proveedor_id, proveedor.pk)
        self.assertEqual(articulo.proveedor.nombre, 'CELASA, S.A.')

    def test_uno_nuevo_llega_con_local_propuesto(self):
        """Es el caso común de las compras del día a día."""
        respuesta = self.client.get(reverse('proveedor_nuevo'))

        self.assertEqual(respuesta.context['form']['origen'].value(), Proveedor.Origen.LOCAL)


class SinClasificarTests(BaseProveedores):
    """
    Los proveedores que se crean al vuelo —al escribirlos en el formulario de
    un producto o al importar el Excel— no pasan por nadie que sepa si son
    locales o importados. Quedan sin clasificar a propósito: guardar una
    suposición como si fuera un dato es peor que admitir que falta.
    """

    def test_uno_creado_al_vuelo_queda_sin_clasificar(self):
        from core.forms import CampoProveedor

        proveedor = CampoProveedor().clean('PROVEEDOR NUEVO')

        self.assertTrue(proveedor.sin_clasificar)
        self.assertEqual(proveedor.origen, '')

    def test_la_lista_avisa_cuantos_faltan(self):
        Proveedor.objects.create(nombre='SIN CLASIFICAR 1')
        Proveedor.objects.create(nombre='SIN CLASIFICAR 2')
        Proveedor.objects.create(nombre='YA CLASIFICADO', origen=Proveedor.Origen.LOCAL)

        respuesta = self.client.get(reverse('lista_proveedores'))

        self.assertEqual(respuesta.context['sin_clasificar'], 2)

    def test_se_pueden_filtrar(self):
        Proveedor.objects.create(nombre='SIN CLASIFICAR')
        Proveedor.objects.create(nombre='LOCAL', origen=Proveedor.Origen.LOCAL)

        respuesta = self.client.get(reverse('lista_proveedores'), {'origen': 'sin_clasificar'})

        self.assertEqual(len(respuesta.context['proveedores']), 1)

    def test_el_buscador_encuentra_por_nombre(self):
        """
        Regresión: la vista usaba Q() sin importarlo y el buscador reventaba
        con NameError. No se notó porque ninguna prueba buscaba texto: todas
        abrían la lista sin filtro.
        """
        Proveedor.objects.create(nombre='FERRETERIA LA ESQUINA')
        Proveedor.objects.create(nombre='LOCOSC')

        respuesta = self.client.get(reverse('lista_proveedores'), {'q': 'ferreteria'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['proveedores']), 1)

    def test_el_buscador_tambien_busca_por_contacto_y_telefono(self):
        Proveedor.objects.create(nombre='CELASA', contacto='Marisol Pérez', telefono='2222-3333')
        Proveedor.objects.create(nombre='LOCOSC')

        por_contacto = self.client.get(reverse('lista_proveedores'), {'q': 'Marisol'})
        por_telefono = self.client.get(reverse('lista_proveedores'), {'q': '2222'})

        self.assertEqual(len(por_contacto.context['proveedores']), 1)
        self.assertEqual(len(por_telefono.context['proveedores']), 1)

    def test_se_puede_filtrar_por_extranjero(self):
        Proveedor.objects.create(nombre='LOCOSC', origen=Proveedor.Origen.EXTRANJERO)
        Proveedor.objects.create(nombre='CEMACO', origen=Proveedor.Origen.LOCAL)

        respuesta = self.client.get(reverse('lista_proveedores'), {'origen': 'extranjero'})

        self.assertEqual(len(respuesta.context['proveedores']), 1)


class EliminarTests(BaseProveedores):
    def test_elimina_uno_que_nadie_usa(self):
        """Es lo que hacía falta para poder limpiar los que entraron por error."""
        proveedor = Proveedor.objects.create(nombre='-----')

        self.client.post(reverse('proveedor_eliminar', args=[proveedor.pk]))

        self.assertFalse(Proveedor.objects.filter(pk=proveedor.pk).exists())

    def test_eliminar_uno_en_uso_no_borra_los_productos(self):
        """SET_NULL: el producto se queda, sin proveedor. Nunca se pierde stock."""
        proveedor = Proveedor.objects.create(nombre='EN USO')
        articulo = Articulo.objects.create(
            nombre_producto='Báscula', modelo='B-1', bodega=self.bodega, proveedor=proveedor,
        )

        self.client.post(reverse('proveedor_eliminar', args=[proveedor.pk]))

        articulo.refresh_from_db()
        self.assertIsNone(articulo.proveedor)
        self.assertTrue(Articulo.objects.filter(pk=articulo.pk).exists())

    def test_avisa_cuantos_productos_quedarian_sin_proveedor(self):
        proveedor = Proveedor.objects.create(nombre='EN USO')
        for i in range(2):
            Articulo.objects.create(
                nombre_producto=f'Báscula {i}', modelo=f'B-{i}',
                bodega=self.bodega, proveedor=proveedor,
            )
        Activo.objects.create(
            codigo_interno='SE-T1', nombre_producto='Taladro',
            bodega=self.tecnica, proveedor=proveedor,
        )

        respuesta = self.client.get(reverse('proveedor_eliminar', args=[proveedor.pk]))

        self.assertContains(respuesta, '3')
        self.assertContains(respuesta, 'sin proveedor')


class OrigenEnLasAlertasTests(BaseProveedores):
    """
    Es para lo que sirve el origen: en "qué hay que reponer", saber cuál es
    importado dice con cuánta anticipación hay que pedirlo.
    """

    def articulo_en_alerta(self, nombre, proveedor):
        return Articulo.objects.create(
            nombre_producto=nombre, modelo=nombre[:5], bodega=self.bodega,
            proveedor=proveedor, stock_critico=2, stock_alerta=5, stock_optimo=20,
        )

    def test_la_pantalla_marca_lo_importado(self):
        importado = Proveedor.objects.create(nombre='LOCOSC', origen=Proveedor.Origen.EXTRANJERO)
        self.articulo_en_alerta('CELDA IMPORTADA', importado)

        respuesta = self.client.get(reverse('reporte_alertas'))

        self.assertContains(respuesta, 'CELDA IMPORTADA')
        self.assertContains(respuesta, 'Extranjero')

    def test_lo_local_no_se_marca(self):
        local = Proveedor.objects.create(nombre='CEMACO', origen=Proveedor.Origen.LOCAL)
        self.articulo_en_alerta('TORNILLO LOCAL', local)

        respuesta = self.client.get(reverse('reporte_alertas'))

        self.assertContains(respuesta, 'TORNILLO LOCAL')
        self.assertNotContains(respuesta, 'Extranjero')

    def test_el_excel_lleva_la_columna_de_origen(self):
        importado = Proveedor.objects.create(nombre='LOCOSC', origen=Proveedor.Origen.EXTRANJERO)
        self.articulo_en_alerta('CELDA IMPORTADA', importado)

        respuesta = self.client.get(reverse('reporte_alertas'), {'formato': 'excel'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheetml', respuesta['Content-Type'])

    def test_un_articulo_sin_proveedor_no_revienta_el_reporte(self):
        self.articulo_en_alerta('SIN PROVEEDOR', None)

        self.assertEqual(self.client.get(reverse('reporte_alertas')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('reporte_alertas'), {'formato': 'excel'}).status_code, 200,
        )
