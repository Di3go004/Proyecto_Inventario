# Sistema de Control de Bodega — Plan

## Diseño visual (referencia)

- **[DESIGN.md](DESIGN.md)** — sistema de tokens ("Precision Logic": color, tipografía Inter, radios, espaciado) generado con Stitch a partir de la paleta real de la empresa.
- **[mockups/](mockups/)** — 5 pantallas de referencia generadas en Stitch (inventario, dashboard, catálogo de activos, captura de movimiento, reportes). Usan branding genérico ("ScaleFlow Pro") y montos en `$` — al construir se reemplaza por el nombre real y quetzales (Q).
- Wireframes propios (estructura ligada 1 a 1 con los RF): ver el Artifact compartido en la conversación.

## Contexto

Hoy el control se lleva en dos libros de Excel (presentes en este repo) que en
realidad son **dos procesos de negocio distintos**, aunque comparten el mismo
formato de "hoja por mes":

### 1. `01 FO-SE-053 INVENTARIO 2025.xlsx` — Inventario para venta (Bodega 1 y 2)

Es el inventario de productos que la empresa vende. Confirmado con el
usuario y con la estructura real de la hoja (`EQUIPO ENERO 2025`, columnas
fila 4):

- **Bodega 1**: indicadores, pesas, básculas, masas patrón, kits de
  conversión, celdas de montaje, balanzas.
- **Bodega 2**: repuestos — celdas de carga, partes de báscula, accesorios,
  conectores, pantallas remotas, básculas de supermercado.
- Ambas bodegas conviven en la misma hoja/tabla, distinguidas por la columna
  `No. BODEGA` (valor `No. 1` / `No. 2`).

Columnas reales de la hoja: `No.`, `PRODUCTO`, `No. BODEGA`, `MARCA`,
`MODELO`, `CAPACIDAD`, `IMAGEN`, `PRECIO`, `CODIGO INTERNO` (el código que
identifica/se escanea), `PROVEEDOR`, `FECHA INGRESO BODEGA`, `FACTURA No.
PROVEEDOR`, `BOLETA INGRESO BODEGA`, `OBSERVACION`, y luego, **repetido 5
veces (una por semana del mes)**: existencia al inicio de semana, ingreso por
importación/compra, salida/descarga, devoluciones, existencia por semana —
más `DEMO`, `TOTAL EXISTENCIA MENSUAL`, `FACTURA VENTA`, `BOLETA DE SALIDA`,
`ENVÍO`, firma y fecha de última revisión.

➡️ Es decir, hoy lleva un **kardex manual semana a semana metido en columnas**.
Eso es exactamente lo que un log de movimientos con fecha reemplaza sin tener
que duplicar columnas ni hojas por mes.

📌 **Ajuste pedido por el usuario**: agregar **Número de Serie** al artículo
como identificador único (hoy la hoja no lo tiene, solo `CODIGO INTERNO`).

### 2. `FO-SE-065 ... Bodega Técnica 2025.xlsx` — Activos de la empresa

Son herramientas/activos de uso interno (rotomartillos, taladros, extintores,
kits de herramientas, lámparas, etc.), **no son para vender**. Lo importante
aquí, según el usuario, es **quién saca/usa cada activo y en qué estado
sale y en qué estado regresa** — es decir, es un flujo de **préstamo /
devolución**, distinto al de venta.

Columnas reales de la hoja (`INVENTARIO ENERO 2025`): `No.`, `PRODUCTO`,
`MARCA`, `MODELO`, `CODIGO INTERNO`, `IMAGEN`, `PROVEEDOR`, `FECHA INGRESO
BODEGA`, `FACTURA No. PROVEEDOR`, `BOLETA INGRESO BODEGA`, `OBSERVACION`, el
mismo bloque semanal de ingreso/salida/devolución/existencia, `TOTAL
EXISTENCIA MENSUAL`, `SALIDA /`, firma y fecha de última revisión. Los
artículos están agrupados en secciones dentro de la misma hoja (ej. fila con
"EQUIPO TÉCNICO" como encabezado de grupo).

📌 **Ajustes pedidos por el usuario**:
- Agregar **Precio** — para poder valorizar cuánto cuesta en total lo que
  hay en la bodega técnica.
- Agregar **Estado** del activo, con 3 valores definidos por el usuario:
  **buen estado**, **mal estado**, **de baja** (cuando el artículo ya no se
  va a volver a utilizar) — y registrar el estado en cada salida y cada
  regreso (no solo un estado fijo del artículo).

### Cómo se registran hoy las entradas y salidas (formatos en papel)

El usuario compartió los formatos físicos que se llenan hoy a mano:

- **FO-SE-013 "Ingreso a Bodega"** (Bodega 1 y 2): folio correlativo, fecha,
  solicitado por, tipo de movimiento (checkbox: **Equipo venta / Equipo
  préstamo / Repuestos / Materiales-Otro**), y tabla de líneas: cantidad,
  descripción, precio, nombre de proveedor, no. de factura.
- **FO-SE-012 "Salida de Bodega"** (Bodega 1 y 2): folio, fecha, solicitado
  por, entregado por, mismo checkbox de tipo (**venta / préstamo / repuestos
  / materiales-otro**), tabla de líneas (cantidad, descripción y código,
  nombre cliente), no. factura, envío y/o recibo, **devuelto por** (para
  cuando la salida es préstamo o demo y el equipo regresa), y firmas de
  quien autoriza / recibe / devuelve.
- **FO-SE-066 "Salida-Entrada Insumos Herramienta Bodega Técnica"**: una
  sola fila combina fecha de salida **y** fecha de entrada (regreso),
  cantidad, herramienta o insumo, código interno, solicitante, entregado
  por/devuelto por, recibido por. Confirma exactamente el modelo de
  préstamo/devolución ya planteado para el módulo Activos.

📌 Dato clave que aporta el usuario: en el módulo Ventas, **una salida no
siempre es una venta definitiva** — puede ser préstamo o demo (para dar
demostraciones a un cliente), en cuyo caso se espera que el equipo regrese,
igual que en Bodega Técnica. Esto significa que el módulo Ventas también
necesita un mini-flujo de préstamo/devolución para esos casos, no solo
entrada/salida simple.

## Decisiones ya confirmadas

- **Despliegue**: varios computadores en la misma red local (LAN). Un equipo
  actúa como servidor con la base de datos; el resto se conecta por
  navegador. Sin necesidad de internet.
- **Tecnología**: **Django + PostgreSQL**. Con varios usuarios concurrentes
  (4–10) y roles con permisos distintos, Django aporta ya resuelto
  autenticación, permisos por rol y panel admin, ahorrando tiempo justo donde
  este proyecto más lo necesita. PostgreSQL evita bloqueos de escritura que
  sí pueden darse con SQLite si varias personas registran movimientos al
  mismo tiempo.
- **Lector de código de barras: descartado por ahora.** Se arranca con
  captura 100% por teclado/texto manual; el lector queda como posible fase
  futura. Como los lectores USB comunes emulan teclado (escriben el código +
  Enter donde esté el cursor), el mismo campo de texto que se construya para
  captura manual va a funcionar sin cambios el día que agreguen un lector —
  no es trabajo perdido.
- **Usuarios concurrentes**: 4 a 10.
- **Boletas físicas**: sí se van a seguir imprimiendo y firmando a mano. El
  sistema debe generar un PDF con el mismo formato de hoy (folio
  correlativo, líneas de detalle, espacios de firma) para cada
  ingreso/salida (FO-SE-013/012) y cada préstamo de Bodega Técnica
  (FO-SE-066), además de quedar el registro guardado digitalmente.

## Arquitectura propuesta

```
[PC Servidor]                          [PC Bodega 1] [PC Bodega 2] [PC Oficina]
  PostgreSQL                                  \            |            /
  Django (backend + páginas web)      todos entran por navegador a
  corre como servicio Windows          http://<ip-servidor>:<puerto>
```

Un equipo corre PostgreSQL + Django como servicios de Windows (arrancan
solos). Los demás PCs —incluida la bodega, donde va el lector USB— solo
abren un navegador apuntando a la IP del servidor en la red local.

## Modelo de datos (dos módulos, un mismo sistema)

En vez de "una hoja por mes", un **catálogo único por bodega/módulo** + un
**historial de movimientos**, del cual se calcula el stock/estado actual y se
puede reconstruir cualquier mes pasado sin duplicar nada.

### Módulo Ventas (Bodega 1 y Bodega 2) — `01 FO-SE-053`

- `Articulo`: código interno, **número de serie**, producto, marca, modelo,
  capacidad, bodega (1 o 2), precio, proveedor, imagen, stock actual
  (calculado), y 3 umbrales de stock para alertas.

📌 **Umbrales de stock pedidos por el usuario (Bodega 1 — indicadores,
básculas, etc.)**: stock óptimo = **20**, alerta de "hay que ir comprando
pronto" cuando baja de **5**, y alerta crítica cuando solo quedan **1 o 2**
unidades. Estos 3 umbrales (óptimo/alerta/crítico) se guardan como campos
configurables en cada artículo — con esos valores como default para Bodega
1 — para poder ajustarlos por artículo o definir otros para Bodega 2 más
adelante. El dashboard/reportes (fase 5) muestra estas alertas por color
(ej. verde ≥ óptimo, amarillo ≤ alerta, rojo ≤ crítico).
- `Movimiento` (reemplaza a los formatos FO-SE-013/FO-SE-012 en papel):
  artículo, dirección (`ingreso` / `salida`), **tipo de transacción**
  (`venta`, `prestamo_demo`, `repuestos`, `materiales_otro`), cantidad,
  fecha, usuario que lo registra, solicitado por, entregado por, cliente
  (si aplica), proveedor/no. factura (ingreso) o no. factura/envío (salida),
  folio correlativo (para mantener la misma numeración que hoy si se sigue
  necesitando).
- Cuando el tipo de transacción de una salida es `prestamo_demo`, el
  movimiento queda "abierto" (equipo fuera, no vendido) hasta registrar su
  regreso (fecha de devolución + quién lo devuelve) — igual que el flujo de
  préstamo de Bodega Técnica, así el stock no se descuenta como vendido sino
  que se marca "afuera en demo/préstamo".
- El stock por semana/mes que hoy se ve en columnas se obtiene filtrando este
  historial por fecha — no se vuelve a capturar a mano.

### Módulo Activos / Bodega Técnica — `FO-SE-065`

- `Activo`: código interno, producto, marca, modelo, precio, imagen,
  proveedor, estado actual (**buen estado** / **mal estado** / **de baja**),
  bodega técnica. "De baja" es el estado definitivo cuando el artículo ya no
  se va a volver a utilizar (deja de aparecer disponible para préstamo).
  Normalmente cantidad = 1 por activo (se identifica cada unidad física, no
  solo se cuenta).
- `Prestamo` (reemplaza al formato FO-SE-066 en papel): activo, cantidad,
  solicitante, fecha de salida, entregado por, estado del activo al salir,
  fecha de regreso (vacío mientras está afuera), recibido por, estado del
  activo al regresar, observación. Esto reemplaza el bloque semanal de
  ingreso/salida y además responde lo que hoy no queda registrado en Excel:
  quién tiene cada herramienta en un momento dado y en qué estado salió/
  volvió.

### Compartido

- `Usuario` — rol `admin`, `operador` o `contabilidad` (Django auth + rol).
- `Categoria` — para agrupar dentro de cada módulo (ej. "EQUIPO TÉCNICO"
  dentro de Activos; indicadores/pesas/básculas/etc. dentro de Ventas).

## Roles y permisos

- **Administrador**: crea/edita/elimina artículos y activos, gestiona
  usuarios, carga masiva desde Excel, ve reportes y valorización total,
  cambia estado de un activo a "de baja".
- **Operador de bodega**: pantalla de captura para registrar movimientos
  (entradas/salidas de venta, o préstamos/regresos de activos) — no puede
  crear/eliminar del catálogo.
- **Contabilidad** *(nuevo)*: acceso de **solo lectura a todo el sistema**
  — catálogo completo, movimientos, préstamos, historial/kardex, reportes y
  valorización de ambas bodegas — sin poder crear, editar, eliminar ni
  registrar movimientos. En Django esto se implementa con un grupo de
  permisos que solo tiene `view_*` sobre todos los modelos (nada de `add`,
  `change` ni `delete`), reutilizando el mismo sistema de permisos que ya se
  usa para admin/operador.

## Flujo de captura manual (pantalla de operador, sin lector por ahora)

Sin lector, lo que más tiempo quita es escribir bien el código/artículo
correcto y llenar campos repetidos. La pantalla se diseña para minimizar
tecleo y errores:

1. **Buscar-mientras-escribe (autocompletar)**: un solo campo de búsqueda
   donde el operador escribe unas letras del código o del nombre del
   producto, y el sistema sugiere coincidencias en vivo (como un buscador),
   en vez de tener que saber/escribir el código completo de memoria.
2. Al elegir el artículo/activo, se muestra su ficha (nombre, foto, bodega,
   stock o estado actual) para confirmar visualmente que es el correcto
   antes de continuar — mismo control que daría un lector, pero por
   selección en vez de escaneo.
3. **Menos tecleo en cada movimiento**:
   - Campos con valor por defecto inteligente: fecha = hoy, usuario =
     quien tiene la sesión iniciada, cantidad = 1.
   - Recordar el último proveedor/cliente/solicitante usado en la sesión
     para no volver a escribirlo.
   - Lista de "artículos frecuentes" o "últimos usados" con un clic, para
     los productos que más rotan.
   - Validación al instante (código no existe, stock insuficiente) antes de
     guardar, para no tener que corregir después.
4. Al confirmar, el formulario se limpia y el foco vuelve al buscador para
   registrar el siguiente movimiento sin usar el mouse — deja lista la
   misma pantalla para que, si más adelante agregan un lector, simplemente
   escanear ahí funcione igual que escribir (útil también para conteos
   físicos/auditorías).

## Carga masiva desde Excel

Pantalla de administrador para subir el `.xlsx` de cada módulo, mapear las
columnas reales ya identificadas arriba, previsualizar y confirmar. Se usará
`openpyxl` para leer los archivos. Los `CODIGO INTERNO` ya existentes se
actualizan, los nuevos se crean con un movimiento de "saldo de apertura".

## Requerimientos

El detalle de lo que el sistema debe hacer y cómo debe comportarse quedó en
documentos separados, para que este archivo se mantenga enfocado en el
flujo/contexto del proyecto:

- [REQUERIMIENTOS_FUNCIONALES.md](REQUERIMIENTOS_FUNCIONALES.md) (RF-01 a RF-15)
- [REQUERIMIENTOS_NO_FUNCIONALES.md](REQUERIMIENTOS_NO_FUNCIONALES.md) (RNF-01 a RNF-09)

## Plan de construcción por fases

1. **Base del proyecto**: Django + PostgreSQL, modelos núcleo de ambos
   módulos, autenticación con los tres roles (admin/operador/contabilidad),
   despliegue accesible por LAN.
2. **Catálogo**: CRUD de artículos (Ventas) y activos (Técnica) para el
   admin + carga masiva desde los dos Excel reales.
3. **Movimientos por captura manual**: pantalla con buscador/autocompletar
   — entradas/salidas (venta/préstamo-demo/repuestos/materiales-otro) en
   Ventas, préstamo/regreso en Activos.
4. **Boletas en PDF**: generar el PDF de cada movimiento con el mismo
   formato de FO-SE-013/FO-SE-012/FO-SE-066 (folio, líneas, espacios de
   firma) para imprimir y firmar a mano, conservando también el registro
   digital.
5. **Reportes**: stock actual y valorización por bodega, alertas de stock
   por los 3 umbrales (óptimo/alerta/crítico) en Bodega 1, activos/equipos
   actualmente prestados y por quién, kardex por artículo/activo, exportar
   a Excel/PDF. Vista de solo lectura para el rol Contabilidad.
6. **Extras**: fotos, modo "conteo físico", respaldo automático de la base
   de datos, y — si más adelante lo confirman — soporte para lector de
   código de barras (el mismo campo de captura ya queda listo para eso).

## Operación y mantenimiento

Comandos del día a día (desde la carpeta del proyecto):

```bash
docker compose up -d                              # levantar el sistema
docker compose exec web python manage.py test     # correr todas las pruebas
```

```powershell
.\scriptsespaldo.ps1                             # respaldar la base de datos
.\scriptsestaurar.ps1                            # ver respaldos disponibles
```

- **Respaldos (RNF-08)**: ver [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md)
  para dejarlo automático en el servidor. Se conservan 30 días.
- **Crear usuarios**: `python manage.py crear_usuario <usuario> <rol>`
  (roles: administrador / operador / contabilidad). Solo el administrador
  recibe acceso al panel `/admin/` de Django.
- **Auditar el stock**: `python manage.py recalcular_stock --solo-revisar`
  compara el stock guardado contra el historial de movimientos y avisa si
  algo no cuadra; sin `--solo-revisar` lo corrige.

### Pruebas automatizadas

36 pruebas cubren lo que no se puede romper en silencio: cálculo de stock
(alta, edición y borrado de movimientos), préstamos y devoluciones, umbrales
de alerta, generación del código interno, y los permisos de los tres roles.
Correrlas antes de cada commit evita reintroducir errores ya corregidos.

## Pendiente conocido (deuda técnica)

Registrado a conciencia, no olvidado:

- **Sin paginación** en los catálogos: hoy se cargan completos (216 artículos
  / 249 activos). Conviene resolverlo antes de que crezcan mucho más.
- **Servidor de desarrollo**: corre con `runserver` y `DEBUG=True`. Sirve para
  la red interna, pero antes de dejarlo definitivo hay que pasar a un
  servidor de producción (gunicorn/waitress) y `DEBUG=False`.
- **Puerto 5432 expuesto** en `docker-compose.yml`: la base es alcanzable
  desde otros equipos de la red sin necesidad. Se puede cerrar.
- **Autocompletado en vivo (RF-13)**: hoy el buscador funciona con botón. El
  autocompletado mientras se escribe se implementa en la Fase 3, que es
  donde de verdad ahorra tiempo al operador.

## Verificación

- Cada fase se prueba corriendo el servidor y accediendo desde otro equipo
  de la red por IP.
- La carga masiva se probará importando los Excel reales del repo.
- El flujo de captura manual se probará registrando movimientos de prueba
  end-to-end (buscar artículo, confirmar, guardar, ver reflejado el stock)
  antes de cerrar la fase 3, incluyendo probar el permiso de solo lectura
  del rol Contabilidad.

## Pendiente a confirmar con el usuario antes de cerrar el plan

- Ninguno por ahora — el lector de código de barras queda descartado para
  esta primera versión (ver "Extras", fase 6) y los estados/umbrales ya
  están definidos.
