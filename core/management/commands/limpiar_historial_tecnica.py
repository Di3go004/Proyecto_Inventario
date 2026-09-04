"""
Borra el historial de movimientos de Bodega Técnica y deja todo en 0.

    python manage.py limpiar_historial_tecnica
    python manage.py limpiar_historial_tecnica --si-estoy-seguro

A diferencia de `limpiar_catalogo --que tecnica`, **no borra los activos**: el
catálogo queda intacto con sus códigos, precios y marcas. Lo único que se va
es el historial de cantidades.

Existe por una razón concreta. El formulario de alta traía abierto el campo
"Cantidad en bodega", así que al crear un activo se le podía poner una
cantidad inicial. Eso generaba un movimiento de tipo "Ajuste" sin folio, sin
solicitante y sin boleta que lo respaldara. Así entraron 219 cantidades que
nunca debieron entrar por ahí.

El alta ya se arregló (ver tecnica/test_alta_en_cero.py), pero eso solo evita
las nuevas. Esto limpia las que quedaron, para arrancar el historial de
verdad desde cero: de aquí en adelante toda cantidad tendrá detrás un ingreso
o una corrección hecha por alguien.

No hace falta poner las existencias en 0 a mano: la existencia se deriva de
los movimientos, así que al borrarlos la señal post_delete las recalcula sola.

No está en la interfaz a propósito, por lo mismo que limpiar_catalogo: es
irreversible y no debe estar a un clic de distancia.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from tecnica.models import Activo, MovimientoActivo, PrestamoActivo


class Command(BaseCommand):
    help = 'Borra el historial de Bodega Técnica y deja las existencias en 0. Irreversible.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--si-estoy-seguro', action='store_true',
            help='Sin esto solo muestra qué se borraría, sin tocar nada.',
        )

    def handle(self, *args, **opciones):
        movimientos = MovimientoActivo.objects.count()
        con_existencia = Activo.objects.filter(existencia__gt=0).count()
        activos = Activo.objects.count()

        self.stdout.write(f'Activos en el catálogo:      {activos:>6}  (no se borran)')
        self.stdout.write(f'Movimientos a borrar:        {movimientos:>6}')
        self.stdout.write(f'Activos que quedarán en 0:   {con_existencia:>6}')

        if not movimientos:
            self.stdout.write(self.style.SUCCESS('El historial ya está vacío.'))
            return

        # Con herramienta prestada, dejar la existencia en 0 diría que en la
        # bodega no hay nada de algo que sí salió y tiene que volver. Se para
        # acá en vez de dejar el dato mintiendo.
        afuera = PrestamoActivo.objects.filter(fecha_regreso__isnull=True).count()
        if afuera:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                f'No se hizo nada: hay {afuera} préstamo(s) sin devolver. '
                'Registrá primero su regreso; si no, quedarían herramientas '
                'afuera y la bodega diciendo que no tiene ninguna.'
            ))
            return

        if not opciones['si_estoy_seguro']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Nada se ha borrado. Hacé un respaldo antes '
                r'(.\scripts\respaldo.ps1) '
                'y volvé a ejecutar agregando --si-estoy-seguro.'
            ))
            return

        with transaction.atomic():
            # El borrado dispara post_delete por cada movimiento, y esa señal
            # recalcula la existencia del activo. Por eso no hace falta
            # tocarlas: quedan en 0 solas.
            borrados, _ = MovimientoActivo.objects.all().delete()

        quedan = Activo.objects.filter(existencia__gt=0).count()
        self.stdout.write('')
        self.stdout.write(f'Movimientos borrados: {borrados}')
        self.stdout.write(f'Activos en el catálogo: {Activo.objects.count()} (intactos)')

        if quedan:
            self.stdout.write(self.style.ERROR(
                f'Cuidado: {quedan} activo(s) siguen con existencia distinta de 0.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Listo: historial vacío y las existencias de Bodega Técnica en 0.'
            ))
