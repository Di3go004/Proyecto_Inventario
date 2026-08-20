from django.core.management.base import BaseCommand

from ventas.models import Articulo


class Command(BaseCommand):
    help = (
        'Recalcula el stock de todos los artículos a partir de sus movimientos. '
        'Sirve para reparar datos que quedaron desincronizados y para auditar '
        'que el stock guardado coincide con el historial.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-revisar',
            action='store_true',
            help='Solo informa las diferencias, sin corregir nada.',
        )

    def handle(self, *args, **options):
        solo_revisar = options['solo_revisar']
        descuadrados = 0

        for articulo in Articulo.objects.all():
            esperado = articulo.calcular_stock_desde_movimientos()
            if esperado != articulo.stock_actual:
                descuadrados += 1
                self.stdout.write(
                    f'  {articulo.codigo_interno}: guardado={articulo.stock_actual} '
                    f'→ segun movimientos={esperado}'
                )
                if not solo_revisar:
                    articulo.recalcular_stock()

        if descuadrados == 0:
            self.stdout.write(self.style.SUCCESS('Todo cuadra: ningún artículo tiene el stock descuadrado.'))
        elif solo_revisar:
            self.stdout.write(self.style.WARNING(f'{descuadrados} artículo(s) descuadrados (no se corrigió nada).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{descuadrados} artículo(s) corregidos.'))
