from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

# Cuántas filas se muestran por página en los catálogos. 25 entra cómodo en
# una pantalla de laptop sin obligar a hacer scroll eterno, y evita cargar
# los 200+ artículos de golpe en cada visita.
POR_PAGINA = 25


def paginar(request, elementos, por_pagina=POR_PAGINA):
    """
    Devuelve la página pedida en ?pagina=N. Si el número no es válido o se
    pasa del total, devuelve la primera o la última en vez de reventar
    (alguien puede editar la URL a mano, o quedar en una página que ya no
    existe tras aplicar un filtro).
    """
    paginador = Paginator(elementos, por_pagina)
    numero = request.GET.get('pagina')
    try:
        return paginador.page(numero)
    except PageNotAnInteger:
        return paginador.page(1)
    except EmptyPage:
        return paginador.page(paginador.num_pages)
