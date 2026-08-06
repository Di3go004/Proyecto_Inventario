# Requerimientos Funcionales — Sistema de Control de Bodega

Lo que el sistema debe **hacer**. Ver también [PLAN.md](PLAN.md) (contexto,
modelo de datos y flujo del proyecto) y
[REQUERIMIENTOS_NO_FUNCIONALES.md](REQUERIMIENTOS_NO_FUNCIONALES.md).

| # | Requerimiento |
|---|---|
| RF-01 | Autenticar usuarios con 3 roles (administrador, operador de bodega, contabilidad), cada uno con permisos distintos. |
| RF-02 | El administrador puede crear, editar, eliminar y consultar artículos (Ventas, Bodega 1 y 2) y activos (Técnica). |
| RF-03 | El operador puede registrar movimientos de entrada/salida (Ventas) y préstamos/regresos (Activos), sin poder modificar el catálogo. |
| RF-04 | El rol contabilidad puede consultar todo (catálogo, movimientos, préstamos, reportes) en modo solo lectura, sin crear/editar/eliminar nada. |
| RF-05 | Cada movimiento de Ventas registra: artículo, dirección (ingreso/salida), tipo (venta/préstamo-demo/repuestos/materiales-otro), cantidad, fecha, usuario, solicitado por, entregado por, cliente/proveedor, no. factura/boleta. |
| RF-06 | Una salida de tipo préstamo/demo se puede cerrar registrando su devolución (fecha y quién devuelve); mientras está "afuera" no cuenta como vendida. |
| RF-07 | Cada préstamo de un activo de Bodega Técnica registra: activo, solicitante, fecha de salida, entregado por, estado al salir, fecha de regreso, recibido por, estado al regresar. |
| RF-08 | El stock actual de cada artículo de Ventas se calcula automáticamente a partir del historial de movimientos. |
| RF-09 | Permitir carga masiva de artículos desde los Excel actuales (FO-SE-053/FO-SE-065), mapeando columnas y evitando duplicados por código interno. |
| RF-10 | Generar un PDF imprimible con el mismo formato de los documentos actuales (FO-SE-013/012/066) por cada movimiento o préstamo. |
| RF-11 | Mostrar alertas de stock en Bodega 1 según 3 umbrales configurables por artículo (óptimo/alerta/crítico; default 20/5/2). |
| RF-12 | Permitir marcar un activo de Bodega Técnica como "de baja" y dejar de ofrecerlo para préstamo. |
| RF-13 | El buscador de artículos/activos sugiere coincidencias mientras el usuario escribe (por código o nombre), para captura manual sin lector. |
| RF-14 | Generar reportes de stock actual, valorización por bodega, activos actualmente prestados (y por quién) y kardex por artículo/activo, exportables a Excel/PDF. |
| RF-15 | El sistema es accesible desde varios computadores de la misma red local por navegador, sin instalar nada fuera del servidor. |
