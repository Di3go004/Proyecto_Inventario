"""
Editar un registro cuya foto ya no está en el disco.

El formulario limitaba el peso de la imagen a 5 MB preguntándole el tamaño al
archivo. Al editar sin cambiar la foto, ahí no llega lo que se acaba de subir
sino el archivo que el registro ya tenía guardado — y preguntarle el tamaño va
al disco. Si ese archivo falta, la pantalla reventaba con FileNotFoundError y
el registro quedaba imposible de editar.

Pasa más de lo que parece: la carpeta `media/` no se versiona, así que basta
copiar la base a otra máquina —o restaurar un respaldo sin las fotos— para que
todos los registros con imagen queden así. También pasa si alguien borra un
archivo a mano.

El límite tiene que aplicarse a lo que se **sube**, no a lo que ya estaba.
"""

import shutil
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Bodega
from tecnica.models import Activo
from usuarios.models import Usuario
from ventas.models import Articulo

# Un PNG de 1x1 de verdad: el campo es ImageField y valida que sea una imagen.
PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05'
    b'\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

MEDIA_DE_PRUEBA = Path('/tmp/media-pruebas')


@override_settings(MEDIA_ROOT=str(MEDIA_DE_PRUEBA))
class BaseImagen(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.venta = Bodega.objects.create(nombre='Bodega 1', tipo=Bodega.Tipo.VENTA)
        cls.tecnica = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_imagen', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )

    def setUp(self):
        self.client.force_login(self.admin)
        MEDIA_DE_PRUEBA.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(MEDIA_DE_PRUEBA, ignore_errors=True)

    def borrar_el_archivo(self, registro):
        """Deja el registro apuntando a una foto que ya no existe."""
        Path(registro.imagen.path).unlink()
        self.assertFalse(Path(registro.imagen.path).exists())


class ActivoConFotoPerdidaTests(BaseImagen):
    def activo_con_foto(self):
        activo = Activo.objects.create(
            codigo_interno='SE-TE900', nombre_producto='TALADRO', bodega=self.tecnica,
            precio=100, es_consumible=True,
            imagen=SimpleUploadedFile('foto.png', PNG, content_type='image/png'),
        )
        self.borrar_el_archivo(activo)
        return activo

    def datos(self, activo, **extra):
        datos = {
            'codigo_interno': activo.codigo_interno, 'nombre_producto': activo.nombre_producto,
            'marca': '', 'modelo': '', 'bodega': self.tecnica.pk, 'categoria': '',
            'proveedor': '', 'precio': '100', 'estado': Activo.Estado.BUEN_ESTADO,
            'imagen_url': '', 'es_consumible': 'on',
            'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
        }
        datos.update(extra)
        return datos

    def test_se_puede_abrir_la_pantalla_de_editar(self):
        activo = self.activo_con_foto()

        respuesta = self.client.get(reverse('activo_editar', args=[activo.pk]))

        self.assertEqual(respuesta.status_code, 200)

    def test_se_puede_guardar_sin_que_reviente(self):
        """Es el error que se vio: FileNotFoundError al guardar."""
        activo = self.activo_con_foto()

        respuesta = self.client.post(
            reverse('activo_editar', args=[activo.pk]), self.datos(activo),
        )

        self.assertEqual(respuesta.status_code, 302, 'no guardó')

    def test_se_le_puede_corregir_la_cantidad_a_un_consumible(self):
        """El caso concreto: subirle la cantidad a un consumible con foto perdida."""
        activo = self.activo_con_foto()

        self.client.post(
            reverse('activo_editar', args=[activo.pk]), self.datos(activo, existencia=12),
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 12)

    def test_la_foto_perdida_se_conserva_en_el_registro(self):
        """No se borra la referencia: el archivo puede volver a aparecer."""
        activo = self.activo_con_foto()
        antes = activo.imagen.name

        self.client.post(reverse('activo_editar', args=[activo.pk]), self.datos(activo))

        activo.refresh_from_db()
        self.assertEqual(activo.imagen.name, antes)


class ArticuloConFotoPerdidaTests(BaseImagen):
    """Bodega 1 y 2 tenía exactamente el mismo formulario y el mismo problema."""

    def articulo_con_foto(self):
        articulo = Articulo.objects.create(
            nombre_producto='BASCULA', modelo='B-1', bodega=self.venta, precio=100,
            imagen=SimpleUploadedFile('foto.png', PNG, content_type='image/png'),
        )
        self.borrar_el_archivo(articulo)
        return articulo

    def test_se_puede_guardar_sin_que_reviente(self):
        articulo = self.articulo_con_foto()

        respuesta = self.client.post(reverse('articulo_editar', args=[articulo.pk]), {
            'codigo_interno': articulo.codigo_interno, 'numero_serie': '',
            'nombre_producto': 'BASCULA', 'marca': '', 'modelo': 'B-1', 'capacidad': '',
            'bodega': self.venta.pk, 'categoria': '', 'proveedor': '', 'precio': '100',
            'imagen_url': '', 'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2,
            'activo': 'on',
        })

        self.assertEqual(respuesta.status_code, 302, 'no guardó')


class ElLimiteDeTamañoSigueVigenteTests(BaseImagen):
    """Lo que el arreglo NO debía aflojar."""

    def test_no_deja_subir_una_imagen_de_mas_de_5_MB(self):
        from tecnica.forms import ActivoForm

        grande = SimpleUploadedFile(
            'grande.png', PNG + b'\x00' * (6 * 1024 * 1024), content_type='image/png',
        )
        form = ActivoForm(
            data={
                'codigo_interno': 'SE-TE901', 'nombre_producto': 'X',
                'bodega': self.tecnica.pk, 'precio': '1',
                'estado': Activo.Estado.BUEN_ESTADO, 'imagen_url': '',
                'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
            },
            files={'imagen': grande},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('5 MB', ' '.join(form.errors.get('imagen', [])))

    def test_una_imagen_chica_si_pasa(self):
        from tecnica.forms import ActivoForm

        form = ActivoForm(
            data={
                'codigo_interno': 'SE-TE902', 'nombre_producto': 'X',
                'bodega': self.tecnica.pk, 'precio': '1',
                'estado': Activo.Estado.BUEN_ESTADO, 'imagen_url': '',
                'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
            },
            files={'imagen': SimpleUploadedFile('ok.png', PNG, content_type='image/png')},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_el_mismo_limite_en_bodega_1_y_2(self):
        from ventas.forms import ArticuloForm

        grande = SimpleUploadedFile(
            'grande.png', PNG + b'\x00' * (6 * 1024 * 1024), content_type='image/png',
        )
        form = ArticuloForm(
            data={
                'codigo_interno': '', 'numero_serie': '', 'nombre_producto': 'X',
                'marca': '', 'modelo': 'M1', 'capacidad': '', 'bodega': self.venta.pk,
                'categoria': '', 'proveedor': '', 'precio': '1', 'imagen_url': '',
                'stock_optimo': 20, 'stock_alerta': 5, 'stock_critico': 2, 'activo': 'on',
            },
            files={'imagen': grande},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('5 MB', ' '.join(form.errors.get('imagen', [])))
