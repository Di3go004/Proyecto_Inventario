"""
Pruebas de la existencia por cantidad en Bodega Técnica.

Antes cada registro era una unidad física. El FO-SE-065 real desmiente eso:
150 de sus 249 productos traen más de una unidad (hay 94 de uno y 62 de
otro), y por eso la valorización salía muy por debajo de lo real.

Las reglas del negocio, tal como las explicó la empresa:
  - A esta bodega **solo entran** cosas, con el mismo FO-SE-013 de Bodega 1 y 2.
  - Lo único que baja la existencia es dar de baja: descartar lo que ya no sirve.
  - Los préstamos no la mueven: la herramienta sale y vuelve, sigue siendo
    de la bodega.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bodega
from tecnica.ayuda_pruebas import dar_de_baja, dar_existencia
from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from usuarios.models import Usuario


class BaseExistencia(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodega = Bodega.objects.create(nombre='Bodega Técnica', tipo=Bodega.Tipo.TECNICA)
        cls.admin = Usuario.objects.create_user(
            username='admin_exi', password='clave-de-prueba', rol=Usuario.Rol.ADMINISTRADOR,
        )
        cls.operador = Usuario.objects.create_user(
            username='op_exi', password='clave-de-prueba', rol=Usuario.Rol.OPERADOR,
        )
        cls.contable = Usuario.objects.create_user(
            username='cont_exi', password='clave-de-prueba', rol=Usuario.Rol.CONTABILIDAD,
        )

    def crear(self, codigo='SE-T1', nombre='Bombillo LED', precio=25, **extra):
        return Activo.objects.create(
            codigo_interno=codigo, nombre_producto=nombre,
            bodega=self.bodega, precio=precio, **extra,
        )


class ExistenciaDerivadaTests(BaseExistencia):
    def test_un_activo_nuevo_arranca_en_cero(self):
        """Nada existe hasta que entra: no se escribe la cantidad a mano."""
        self.assertEqual(self.crear().existencia, 0)

    def test_los_ingresos_suman(self):
        activo = self.crear()

        dar_existencia(activo, 10, self.admin)
        dar_existencia(activo, 5, self.admin)

        self.assertEqual(activo.existencia, 15)

    def test_las_bajas_restan(self):
        activo = dar_existencia(self.crear(), 10, self.admin)

        dar_de_baja(activo, 3, self.admin)

        self.assertEqual(activo.existencia, 7)

    def test_no_se_puede_dar_de_baja_mas_de_lo_que_hay(self):
        activo = dar_existencia(self.crear(), 2, self.admin)

        with self.assertRaises(ValidationError):
            MovimientoActivo.objects.create(
                tipo=MovimientoActivo.Tipo.BAJA, activo=activo,
                cantidad=5, usuario=self.admin,
            )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 2, 'no se guardó nada a medias')

    def test_prestar_no_cambia_la_existencia(self):
        """
        Es la diferencia con Bodega 1 y 2: lo prestado sigue siendo de la
        bodega, solo que no está en el estante.
        """
        activo = dar_existencia(self.crear(), 10, self.admin)

        PrestamoActivo.objects.create(
            activo=activo, cantidad=4, solicitante='Byron', usuario=self.admin,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 10, 'la existencia no se toca')
        self.assertEqual(activo.cantidad_afuera, 4)
        self.assertEqual(activo.disponibles, 6)

    def test_al_regresar_el_prestamo_deja_de_contar_como_afuera(self):
        activo = dar_existencia(self.crear(), 10, self.admin)
        prestamo = PrestamoActivo.objects.create(
            activo=activo, cantidad=4, solicitante='Byron', usuario=self.admin,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        prestamo.fecha_regreso = timezone.now()
        prestamo.estado_al_regresar = Activo.Estado.BUEN_ESTADO
        prestamo.save()

        activo.refresh_from_db()
        self.assertEqual(activo.cantidad_afuera, 0)
        self.assertEqual(activo.disponibles, 10)

    def test_darlo_de_baja_todo_lo_deja_agotado(self):
        activo = dar_existencia(self.crear(), 3, self.admin)

        dar_de_baja(activo, 3, self.admin)

        self.assertTrue(activo.agotado)
        self.assertEqual(activo.valor_en_bodega, 0)

    def test_el_valor_es_precio_por_existencia(self):
        """
        Regresión: era solo el precio, porque se asumía una unidad por
        registro. Con 10 bombillos de Q25 la bodega valía Q25 en vez de Q250.
        """
        activo = dar_existencia(self.crear(precio=25), 10, self.admin)

        self.assertEqual(activo.valor_en_bodega, 250)

    def test_borrar_un_movimiento_en_bloque_deja_la_existencia_cuadrada(self):
        """
        Django no llama al delete() del modelo en un borrado en bloque, que es
        el camino del panel de administración y de cualquier limpieza por
        consola. Sin señal, la existencia quedaba desfasada sin avisar.
        """
        activo = dar_existencia(self.crear(), 10, self.admin)
        dar_existencia(activo, 5, self.admin)

        MovimientoActivo.objects.filter(activo=activo, cantidad=5).delete()

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 10)


class PantallaDeBajaTests(BaseExistencia):
    def setUp(self):
        self.client.force_login(self.operador)
        self.activo = dar_existencia(self.crear(), 10, self.admin)

    def dar_baja(self, **extra):
        datos = {
            'cantidad': 3,
            'motivo': MovimientoActivo.Motivo.DANADO,
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'observacion': '',
        }
        datos.update(extra)
        return self.client.post(reverse('activo_baja', args=[self.activo.pk]), datos)

    def test_registrar_una_baja_descuenta_la_existencia(self):
        respuesta = self.dar_baja()

        self.activo.refresh_from_db()
        self.assertRedirects(respuesta, reverse('activo_detalle', args=[self.activo.pk]))
        self.assertEqual(self.activo.existencia, 7)

    def test_la_baja_no_lleva_folio(self):
        """No es una salida hacia nadie: no se llena boleta."""
        self.dar_baja()

        movimiento = MovimientoActivo.objects.get(tipo=MovimientoActivo.Tipo.BAJA)
        self.assertEqual(movimiento.folio, '')
        self.assertEqual(movimiento.motivo, MovimientoActivo.Motivo.DANADO)
        self.assertEqual(movimiento.usuario, self.operador)

    def test_no_se_puede_dar_de_baja_lo_que_esta_prestado(self):
        """
        De 10 con 8 afuera solo se pueden descartar 2: dar de baja algo que
        está en manos de alguien dejaría el historial mintiendo.
        """
        PrestamoActivo.objects.create(
            activo=self.activo, cantidad=8, solicitante='Byron', usuario=self.admin,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        respuesta = self.dar_baja(cantidad=5)

        self.activo.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Solo hay 2 en bodega')
        self.assertEqual(self.activo.existencia, 10)

    def test_contabilidad_no_puede_dar_de_baja(self):
        """RF-04: consulta e imprime, pero no modifica."""
        self.client.force_login(self.contable)

        respuesta = self.dar_baja()

        self.activo.refresh_from_db()
        self.assertIn(respuesta.status_code, (302, 403))
        self.assertEqual(self.activo.existencia, 10)


class ConsumiblesTests(BaseExistencia):
    """
    En los consumibles —bombillos, flejes, pintura— la cantidad se corrige
    escribiéndola en el catálogo, sin el trámite de registrar una baja. Aun
    así queda el ajuste en el historial: el catálogo y los movimientos nunca
    pueden decir cosas distintas.
    """

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, activo, **extra):
        datos = {
            'codigo_interno': activo.codigo_interno,
            'nombre_producto': activo.nombre_producto,
            'marca': '', 'modelo': '',
            'bodega': self.bodega.pk,
            'precio': activo.precio,
            'estado': Activo.Estado.BUEN_ESTADO,
            'imagen_url': '',
            'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
        }
        datos.update(extra)
        return datos

    def test_en_un_consumible_la_cantidad_se_puede_corregir(self):
        activo = dar_existencia(self.crear(es_consumible=True), 10, self.admin)

        self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(activo, es_consumible='on', existencia=4),
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 4)

    def test_la_correccion_queda_como_movimiento(self):
        activo = dar_existencia(self.crear(es_consumible=True), 10, self.admin)

        self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(activo, es_consumible='on', existencia=4),
        )

        ajuste = MovimientoActivo.objects.exclude(tipo=MovimientoActivo.Tipo.INGRESO).get()
        self.assertEqual(ajuste.cantidad, 6, 'se guarda la diferencia, no el total')
        self.assertEqual(ajuste.usuario, self.admin)

    def test_en_lo_que_no_es_consumible_la_cantidad_no_se_edita(self):
        """
        En herramienta y equipo la existencia solo se mueve con un ingreso o
        una baja: escribirla acá dejaría el historial diciendo otra cosa.
        """
        activo = dar_existencia(self.crear(), 10, self.admin)

        self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(activo, existencia=4),
        )

        activo.refresh_from_db()
        self.assertEqual(activo.existencia, 10)

    def test_no_se_puede_bajar_por_debajo_de_lo_prestado(self):
        activo = dar_existencia(self.crear(es_consumible=True), 10, self.admin)
        PrestamoActivo.objects.create(
            activo=activo, cantidad=7, solicitante='Byron', usuario=self.admin,
            estado_al_salir=Activo.Estado.BUEN_ESTADO,
        )

        respuesta = self.client.post(
            reverse('activo_editar', args=[activo.pk]),
            self.datos(activo, es_consumible='on', existencia=3),
        )

        activo.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(activo.existencia, 10)

    def test_al_crearlo_arranca_en_cero_aunque_manden_cantidad(self):
        """
        Antes el alta aceptaba una cantidad inicial y la guardaba como un
        movimiento de "saldo inicial". Eso dejaba entrar existencia a Bodega
        Técnica sin ninguna boleta detrás: en la lista de movimientos salían
        como "Ajuste", sin folio ni solicitante, y así entraron 218.

        Ahora un activo nace en 0 igual que un artículo de Bodega 1 y 2: la
        cantidad entra con un ingreso (FO-SE-013), o escribiéndola al editar
        si es consumible. Ver tecnica/test_alta_en_cero.py.
        """
        self.client.post(reverse('activo_nuevo'), {
            'codigo_interno': 'SE-NUEVO', 'nombre_producto': 'Juego de llaves',
            'marca': '', 'modelo': '', 'bodega': self.bodega.pk, 'precio': 300,
            'estado': Activo.Estado.BUEN_ESTADO, 'imagen_url': '', 'existencia': 6,
            'stock_critico': 2, 'stock_alerta': 5, 'stock_optimo': 20,
        })

        activo = Activo.objects.get(codigo_interno='SE-NUEVO')
        self.assertEqual(activo.existencia, 0)
        self.assertEqual(activo.movimientos.count(), 0)
