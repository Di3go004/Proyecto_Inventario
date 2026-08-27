"""
Siembra las categorías con las que se arranca.

El sistema salía con la tabla vacía, y como la categoría se elige de una
lista, el desplegable aparecía sin nada: parecía que la función no servía.
Estas salen de agrupar los productos reales de los dos Excel de 2025
(FO-SE-053 y FO-SE-065), no de una lista inventada — así la mayoría del
catálogo cae en alguna desde el primer día.

No pretenden ser definitivas: el administrador las edita, borra y agrega
desde Administración › Categorías.
"""

from django.db import migrations

# Bodega 1 y 2 — celdas de carga, masas patrón, básculas e indicadores son
# el grueso del inventario de venta.
VENTAS = [
    'Celdas de carga',
    'Indicadores',
    'Básculas',
    'Balanzas',
    'Masas patrón y pesas',
    'Cajas suma',
    'Cables y conectores',
    'Tarjetas y repuestos electrónicos',
    'Baterías y adaptadores',
    'Consumibles y accesorios',
]

# Bodega Técnica — herramienta e insumos de uso interno.
TECNICA = [
    'Herramienta manual',
    'Herramienta eléctrica',
    'Brocas y discos',
    'Ferretería',
    'Pinturas y químicos',
    'Material eléctrico',
    'Cuerdas y eslingas',
    'Limpieza',
    'Equipo de protección',
]


def sembrar(apps, schema_editor):
    Categoria = apps.get_model('core', 'Categoria')
    for modulo, nombres in (('ventas', VENTAS), ('tecnica', TECNICA)):
        for nombre in nombres:
            # get_or_create y no bulk_create: si alguien ya creó una a mano
            # con ese nombre, la migración no debe reventar por el índice
            # único (nombre, modulo).
            Categoria.objects.get_or_create(nombre=nombre, modulo=modulo)


def quitar(apps, schema_editor):
    """
    Al revertir solo se van las que nadie está usando. Borrar una categoría
    con artículos dentro los dejaría sin clasificar sin avisar, y revertir
    una migración no debería perder datos que capturó el usuario.
    """
    Categoria = apps.get_model('core', 'Categoria')
    for modulo, nombres in (('ventas', VENTAS), ('tecnica', TECNICA)):
        (Categoria.objects
         .filter(nombre__in=nombres, modulo=modulo, articulo__isnull=True, activo__isnull=True)
         .delete())


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('ventas', '0001_initial'),
        ('tecnica', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
