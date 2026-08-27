# Requerimientos No Funcionales — Sistema de Control de Bodega

Cómo debe **comportarse** el sistema. Ver también [PLAN.md](PLAN.md)
(contexto, modelo de datos y flujo del proyecto) y
[REQUERIMIENTOS_FUNCIONALES.md](REQUERIMIENTOS_FUNCIONALES.md).

| # | Requerimiento |
|---|---|
| RNF-01 | **Rendimiento**: soportar 4–10 usuarios concurrentes registrando movimientos sin bloqueos ni demoras notables (PostgreSQL, no SQLite). |
| RNF-02 | **Disponibilidad**: debe operar completo en la red local, sin depender de internet. |
| RNF-03 | **Seguridad**: acceso por usuario/contraseña, contraseñas con hash, ninguna acción anónima. |
| RNF-04 | **Trazabilidad**: todo movimiento/préstamo queda asociado a fecha, hora y usuario responsable (no hay registros "huérfanos"). |
| RNF-05 | **Usabilidad**: la captura manual debe requerir el mínimo de clics/tecleo posible (buscador, valores por defecto, frecuentes), pensada para operadores sin perfil técnico. |
| RNF-06 | **Mantenibilidad**: código organizado por módulo (Ventas / Activos / usuarios) siguiendo la estructura estándar de Django, para poder ampliarlo sin reescribirlo. |
| RNF-07 | **Compatibilidad**: funcionar en los navegadores ya instalados en los equipos de la empresa (Chrome/Edge), sin plugins. |
| RNF-08 | **Respaldo**: debe existir un mecanismo de backup periódico de la base de datos, al ser la única fuente de verdad del inventario. |
| RNF-09 | **Escalabilidad futura**: el modelo de datos y la pantalla de captura deben poder incorporar un lector de código de barras y/o más bodegas sin rediseño desde cero. |
