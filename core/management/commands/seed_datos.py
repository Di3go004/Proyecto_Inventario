from django.core.management.base import BaseCommand

from core.models import Bodega


class Command(BaseCommand):
    help = 'Crea las bodegas reales de la empresa (idempotente, seguro de correr varias veces).'

    def handle(self, *args, **options):
        bodegas = [
            ('Bodega 1', Bodega.Tipo.VENTA,
             'Indicadores, pesas, básculas, masas patrón, kits de conversión, celdas de montaje, balanzas'),
            ('Bodega 2', Bodega.Tipo.VENTA,
             'Repuestos: celdas de carga, partes de báscula, accesorios, conectores, pantallas remotas, básculas de supermercado'),
            ('Bodega Técnica', Bodega.Tipo.TECNICA,
             'Herramientas y activos de uso interno de la empresa'),
        ]
        for nombre, tipo, descripcion in bodegas:
            bodega, creada = Bodega.objects.get_or_create(
                nombre=nombre, defaults={'tipo': tipo, 'descripcion': descripcion},
            )
            accion = 'creada' if creada else 'ya existía'
            self.stdout.write(self.style.SUCCESS(f'  · {nombre}: {accion}'))

        self.stdout.write(self.style.SUCCESS('Seed completo.'))
