"""
Vacía el catálogo para volver a importarlo desde cero.

    python manage.py limpiar_catalogo --que ventas
    python manage.py limpiar_catalogo --que todo --si-estoy-seguro

Existe para la etapa de puesta en marcha: si una carga masiva salió mal, el
Excel tenía columnas cambiadas o simplemente se quiere arrancar limpio,
borrar 200 artículos uno por uno desde la pantalla no es viable.

No está en la interfaz a propósito. Es una operación irreversible, y un botón
de "borrar todo" al alcance de un clic en la pantalla de catálogo es un
accidente esperando a pasar.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tecnica.models import Activo, MovimientoActivo, PrestamoActivo
from ventas.models import Articulo, MovimientoVenta

OPCIONES = ('ventas', 'tecnica', 'todo')


class Command(BaseCommand):
    help = 'Borra el catálogo y su historial de movimientos. Irreversible.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--que', choices=OPCIONES, required=True,
            help='ventas (Bodega 1 y 2) | tecnica (herramienta) | todo',
        )
        parser.add_argument(
            '--si-estoy-seguro', action='store_true',
            help='Sin esto solo muestra qué se borraría, sin tocar nada.',
        )

    def handle(self, *args, **opciones):
        que = opciones['que']
        toca_ventas = que in ('ventas', 'todo')
        toca_tecnica = que in ('tecnica', 'todo')

        conteo = {}
        if toca_ventas:
            conteo['movimientos de venta'] = MovimientoVenta.objects.count()
            conteo['artículos (Bodega 1 y 2)'] = Articulo.objects.count()
        if toca_tecnica:
            conteo['préstamos de herramienta'] = PrestamoActivo.objects.count()
            conteo['movimientos de Bodega Técnica'] = MovimientoActivo.objects.count()
            conteo['activos (Bodega Técnica)'] = Activo.objects.count()

        self.stdout.write('Se borraría:')
        for etiqueta, cuantos in conteo.items():
            self.stdout.write(f'  {cuantos:>6}  {etiqueta}')

        if not any(conteo.values()):
            self.stdout.write(self.style.SUCCESS('No hay nada que borrar.'))
            return

        if not opciones['si_estoy_seguro']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Nada se ha borrado. Haz un respaldo antes (.\\scripts\\respaldo.ps1) '
                'y vuelve a ejecutar agregando --si-estoy-seguro.'
            ))
            return

        try:
            with transaction.atomic():
                # El historial primero: los artículos están protegidos
                # justamente para que no se borren dejándolo huérfano.
                if toca_ventas:
                    MovimientoVenta.objects.all().delete()
                    Articulo.objects.all().delete()
                if toca_tecnica:
                    PrestamoActivo.objects.all().delete()
                    MovimientoActivo.objects.all().delete()
                    Activo.objects.all().delete()
        except Exception as error:
            raise CommandError(f'No se borró nada: {error}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Catálogo vaciado. No se tocaron proveedores, categorías ni usuarios.'))
        self.stdout.write('Ya puedes volver a importar el Excel desde Carga masiva.')
