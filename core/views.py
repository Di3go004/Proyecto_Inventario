from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.shortcuts import render

from ventas.models import Articulo, MovimientoVenta
from tecnica.models import Activo, PrestamoActivo


@login_required
def resumen(request):
    """
    Primera pantalla tras el login (RF-15 la ven los 3 roles). Sirve
    también para comprobar de un vistazo que los modelos y sus reglas
    (stock, alertas, préstamos abiertos) están funcionando de verdad.
    """
    articulos = Articulo.objects.filter(activo=True)
    alertas = [a for a in articulos if a.nivel_alerta in ('alerta', 'critico')]

    valorizacion_ventas = articulos.aggregate(
        total=Sum(F('precio') * F('stock_actual'))
    )['total'] or 0

    valorizacion_tecnica = Activo.objects.exclude(estado=Activo.Estado.DE_BAJA).aggregate(
        total=Sum('precio')
    )['total'] or 0

    prestamos_demo_abiertos = MovimientoVenta.objects.filter(
        tipo_transaccion=MovimientoVenta.TipoTransaccion.PRESTAMO_DEMO,
        fecha_devolucion__isnull=True,
    ).count()

    activos_prestados = PrestamoActivo.objects.filter(fecha_regreso__isnull=True).select_related('activo')

    contexto = {
        'total_articulos': articulos.count(),
        'alertas': alertas,
        'valorizacion_ventas': valorizacion_ventas,
        'valorizacion_tecnica': valorizacion_tecnica,
        'prestamos_demo_abiertos': prestamos_demo_abiertos,
        'activos_prestados': activos_prestados,
    }
    return render(request, 'core/resumen.html', contexto)
