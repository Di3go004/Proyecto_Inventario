"""
Carga masiva de activos desde Excel (RF-09) — Bodega Técnica.

Mismo diseño en 2 pasos que ventas/importador.py, pero con 3 diferencias
reales del negocio (ver PLAN.md y la conversación con el usuario):

  1. Aquí el "código interno" SÍ se importa tal cual viene en el archivo
     (columna CODIGO INTERNO) — es lo contrario de Bodega 1/2, porque en
     Bodega Técnica el código lo asigna la empresa a mano, no depende de
     modelo/capacidad. Por eso también es el campo que decide si una fila
     ya existe (actualizar) o es nueva (crear).
  2. No hay bodega 1/2 que elegir por fila: todo entra a la única Bodega
     Técnica.
  3. La bodega solo recibe: la existencia del Excel entra como un ajuste de
     saldo inicial, no como una compra. En Bodega 1 y 2 el equivalente es
     ajuste_inicial.
"""

from core import importador_excel as xl

CAMPOS_IMPORTABLES = [
    ('nombre_producto', 'Producto', True, ['PRODUCTO']),
    ('codigo_interno', 'Código interno', True, ['CODIGO INTERNO', 'CÓDIGO INTERNO']),
    ('marca', 'Marca', False, ['MARCA']),
    ('modelo', 'Modelo', False, ['MODELO']),
    ('proveedor', 'Proveedor', False, ['PROVEEDOR']),
    ('precio', 'Precio', False, ['PRECIO']),
    # El orden importa: manda la primera palabra que aparezca en la hoja.
    # 'TOTAL EXISTENCIA MENSUAL' es la columna buena; las otras son saldos
    # parciales por semana que en enero vienen vacíos.
    ('existencia', 'Existencia inicial', False,
     ['TOTAL EXISTENCIA', 'EXISTENCIA MENSUAL', 'EXISTENCIA']),
]

MAX_FILAS_PREVIEW = xl.MAX_FILAS_PREVIEW

listar_hojas = xl.listar_hojas
detectar_encabezados = xl.detectar_encabezados


def autodetectar_mapeo(columnas):
    return xl.autodetectar_mapeo(columnas, CAMPOS_IMPORTABLES)


def leer_filas(ruta, hoja, fila_encabezado, mapeo):
    """Filas sin producto o sin código interno se omiten — ambos son
    obligatorios para un activo (ver tecnica/models.py)."""
    libro = xl.abrir_libro(ruta)
    try:
        ws = libro[hoja]
        col_idx = xl.columnas_a_indices(mapeo)

        for fila in ws.iter_rows(min_row=fila_encabezado + 1, values_only=True):
            def obtener(clave):
                idx = col_idx.get(clave)
                return fila[idx] if idx is not None and idx < len(fila) else None

            nombre = xl.valor_texto(obtener('nombre_producto'))
            codigo = xl.valor_texto(obtener('codigo_interno'))
            if not nombre or not codigo:
                continue

            yield {
                'nombre_producto': nombre,
                'codigo_interno': codigo,
                'marca': xl.valor_texto(obtener('marca')),
                'modelo': xl.valor_texto(obtener('modelo')),
                'proveedor': xl.valor_texto(obtener('proveedor')),
                'precio': xl.valor_decimal(obtener('precio')),
                # None cuando la columna no se mapeó, y ahí la existencia
                # no se toca. Con valor_entero a secas, una importación sin
                # esa columna daría de baja todo lo que ya había: valor_entero
                # convierte el vacío en 0.
                'existencia': (
                    xl.valor_entero(obtener('existencia'))
                    if 'existencia' in col_idx else None
                ),
            }
    finally:
        libro.close()


def _ajustar_existencia(activo, existencia, usuario):
    """
    Deja el activo con la existencia que trae el Excel, como un ajuste.

    Se registra la diferencia y no el total, para que volver a importar el
    mismo archivo no duplique el saldo: si ya estaba en 10 y el Excel dice
    10, no se crea nada. No es una compra, así que no lleva folio: es "así
    arrancó el conteo".
    """
    from .models import MovimientoActivo

    if existencia is None:
        return
    diferencia = existencia - activo.existencia
    if diferencia == 0:
        return

    MovimientoActivo.objects.create(
        tipo=MovimientoActivo.Tipo.AJUSTE if diferencia > 0 else MovimientoActivo.Tipo.BAJA,
        activo=activo, cantidad=abs(diferencia), usuario=usuario,
        motivo=MovimientoActivo.Motivo.OTRO if diferencia < 0 else '',
        observacion='Saldo inicial de la carga masiva del FO-SE-065.',
    )


def ejecutar_importacion(ruta, hoja, fila_encabezado, mapeo, usuario):
    from django.db import IntegrityError, transaction

    from core.models import Bodega, Proveedor
    from .models import Activo, MovimientoActivo

    resultado = {'creados': 0, 'actualizados': 0, 'omitidos': 0, 'errores': []}

    bodega_tecnica = Bodega.objects.filter(tipo=Bodega.Tipo.TECNICA).first()
    if not bodega_tecnica:
        resultado['errores'].append('No existe una bodega de tipo Técnica configurada — nada se importó.')
        return resultado

    for i, fila in enumerate(leer_filas(ruta, hoja, fila_encabezado, mapeo), start=2):
        etiqueta_fila = f"Fila {i} ('{fila['nombre_producto']}')"
        try:
            with transaction.atomic():
                proveedor = None
                if fila['proveedor']:
                    proveedor, _ = Proveedor.objects.get_or_create(nombre=fila['proveedor'])

                existente = Activo.objects.filter(codigo_interno=fila['codigo_interno']).first()
                if existente:
                    existente.nombre_producto = fila['nombre_producto']
                    existente.marca = fila['marca']
                    existente.modelo = fila['modelo']
                    if proveedor:
                        existente.proveedor = proveedor
                    if fila['precio']:
                        existente.precio = fila['precio']
                    existente.save()
                    _ajustar_existencia(existente, fila['existencia'], usuario)
                    resultado['actualizados'] += 1
                else:
                    activo = Activo.objects.create(
                        codigo_interno=fila['codigo_interno'],
                        nombre_producto=fila['nombre_producto'],
                        marca=fila['marca'],
                        modelo=fila['modelo'],
                        bodega=bodega_tecnica,
                        proveedor=proveedor,
                        precio=fila['precio'],
                    )
                    _ajustar_existencia(activo, fila['existencia'], usuario)
                    resultado['creados'] += 1
        except IntegrityError as e:
            resultado['omitidos'] += 1
            resultado['errores'].append(f"{etiqueta_fila}: {e}")

    return resultado
