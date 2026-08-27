# Sistema de Control de Bodega — Plan

> 📌 **Para poner el sistema en marcha con los datos reales**, seguí
> [PUESTA_EN_MARCHA.md](PUESTA_EN_MARCHA.md) — es el paso a paso, con dónde
> se corre cada comando. Este documento es el porqué de cada decisión.

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

### Cómo quedó implementado (Fase 3)

**Un documento = un folio con varias líneas.** Una boleta de papel lleva
varios productos bajo un mismo encabezado, así que el sistema hace lo mismo:
el encabezado se captura una vez y se copia a cada `MovimientoVenta` que
comparte el folio. El folio es correlativo y separado por tipo, imitando la
numeración preimpresa: `ING-00001` para FO-SE-013 e `SAL-00001` para
FO-SE-012. El administrador puede escribir uno propio si necesita calzar con
una boleta física ya numerada.

**El documento entra completo o no entra.** Si una línea falla —por ejemplo,
no hay stock suficiente— no se guarda ninguna. Una boleta a medias dejaría el
stock mintiendo, que es justo el problema que este sistema viene a resolver.

**La fecha la pone el operador.** No es la hora de captura: las boletas se
llenan a mano y muchas veces se digitan al día siguiente, así que el campo es
editable y solo trae "ahora" como valor propuesto.

**Al regresar una herramienta, el catálogo se actualiza solo.** Si sale buena
y vuelve dañada, el estado del activo cambia sin depender de que alguien se
acuerde de editarlo aparte. Es lo que hoy se pierde en el Excel.

De la lista de arriba quedó **pendiente** (no bloquea el uso, se puede sumar
después): recordar el último proveedor/cliente usado en la sesión, la lista
de "artículos frecuentes", y proponer cantidad = 1 por defecto. Y un cambio
deliberado sobre el punto 4: al guardar **no** se limpia el formulario, se
abre el documento recién creado — el operador necesita verlo para imprimirlo
y firmarlo, que es el flujo real de la empresa.

## Carga masiva desde Excel

Pantalla de administrador para subir el `.xlsx` de cada módulo, mapear las
columnas reales ya identificadas arriba, previsualizar y confirmar. Se usará
`openpyxl` para leer los archivos. Los `CODIGO INTERNO` ya existentes se
actualizan, los nuevos se crean con un movimiento de "saldo de apertura".

## Boletas impresas (Fase 4)

Se generan con **ReportLab** y no con una librería de HTML→PDF: los tres
formatos son tablas regladas de ancho fijo, que es lo que mejor resuelve, y
ReportLab es Python puro — no agrega paquetes del sistema a la imagen de
Docker ni al equipo de la oficina, que muchas veces trabaja sin internet.

- **FO-SE-013 / FO-SE-012** → un PDF por folio, en carta apaisada. Lleva el
  encabezado con el logo, el folio, la casilla marcada según el tipo de
  movimiento, el detalle con filas en blanco hasta completar la hoja y, en la
  salida, los tres espacios de firma (autoriza / recibe / devuelve).
- **FO-SE-066** → no es un PDF por préstamo: en el papel es una hoja de
  registro donde se anotan varios, así que se imprime **el listado que se
  está viendo en pantalla, con sus filtros aplicados**. La pantalla y el PDF
  comparten la misma función de filtrado justamente para que nunca se
  separen.

Decisiones que conviene tener presentes:

- **Cada formato sale en el tamaño real de su talonario**, y no es un detalle
  estético: las boletas se imprimen, se firman y se archivan junto a las de
  papel de los años anteriores. Si no calzan, no entran en el mismo folder.
  - FO-SE-013 / FO-SE-012 → **media carta apaisada** (216 × 140 mm), que es
    la hoja carta partida a la mitad. Ojo: el `HALF_LETTER` de ReportLab mide
    140 × 203 mm (5.5 × 8") y **no** es media carta.
  - FO-SE-066 → carta vertical.
- **6 líneas por hoja** en las boletas de venta. En 140 mm de alto no entran
  más sin empujar el bloque de firmas a una segunda página, y la hoja que se
  firma tiene que ser una. Un documento con más líneas se reparte en varias,
  cada una con su encabezado y su "Página X de Y".
- **Las descripciones largas se recortan a un renglón**, midiendo el ancho
  real del texto con las métricas de la fuente en vez de contar caracteres
  (una "W" y una "l" no ocupan lo mismo, y el cálculo fallaba justo con los
  nombres largos). El nombre completo siempre queda en el sistema.
- **El estado de regreso de una herramienta se anota** bajo su nombre en la
  hoja técnica, solo si volvió distinta de como salió. El papel no tiene esa
  columna, pero perder ese dato justo al imprimir el registro dejaría fuera
  lo que hoy más cuesta rastrear.
- **Imprimir lo pueden hacer los 3 roles**, contabilidad incluida: imprimir es
  consultar, no modificar (RF-04).

## Reportes (Fase 5)

Cuatro reportes, todos descargables a Excel, y los ven los tres roles — para
contabilidad son la razón de ser de su acceso: consultan e imprimen, no
modifican (RF-04).

| Reporte | Responde a |
|---|---|
| **Existencias y valorización** | Cuánto hay y cuánto vale, por bodega |
| **Alertas de stock** | Qué reponer, lo que está en cero primero |
| **Movimientos por período** | Qué entró y qué salió entre dos fechas |
| **Fuera de bodega** | Qué está prestado, con quién y desde hace cuántos días |

El kardex por artículo (RF-14) ya existía desde la Fase 3; se abre desde la
ficha del producto.

Decisiones que conviene tener presentes:

- **La pantalla y el Excel comparten `core/reportes.py`.** Es el error
  clásico de los reportes: cada camino arma su propia consulta y con el
  tiempo dejan de cuadrar. Con una sola función no pueden separarse, y hay
  una prueba que compara ambos resultados.
- **Bodega Técnica se valoriza distinto**: cada herramienta es una unidad
  física, así que el valor es la suma de precios, no precio × existencia.
  Las dadas de baja no cuentan — ya no son patrimonio utilizable (RF-12).
- **El Excel sale listo para trabajar**: encabezado fijo al hacer scroll,
  filtros puestos, anchos ajustados, y los montos y fechas como número y
  fecha de verdad (no como texto). Un reporte que hay que reformatear a mano
  cada vez termina no usándose.
- **Los filtros de la pantalla se aplican a la descarga.** Si estás viendo
  solo Bodega 2, eso es lo que baja.

## Requerimientos

El detalle de lo que el sistema debe hacer y cómo debe comportarse quedó en
documentos separados, para que este archivo se mantenga enfocado en el
flujo/contexto del proyecto:

- [REQUERIMIENTOS_FUNCIONALES.md](REQUERIMIENTOS_FUNCIONALES.md) (RF-01 a RF-15)
- [REQUERIMIENTOS_NO_FUNCIONALES.md](REQUERIMIENTOS_NO_FUNCIONALES.md) (RNF-01 a RNF-09)

## Plan de construcción por fases

1. ✅ **Base del proyecto**: Django + PostgreSQL, modelos núcleo de ambos
   módulos, autenticación con los tres roles (admin/operador/contabilidad),
   despliegue accesible por LAN.
2. ✅ **Catálogo**: CRUD de artículos (Ventas) y activos (Técnica) para el
   admin + carga masiva desde los dos Excel reales.
3. ✅ **Movimientos por captura manual**: pantalla con buscador/autocompletar
   — entradas/salidas (venta/préstamo-demo/repuestos/materiales-otro) en
   Ventas, préstamo/regreso en Activos.
4. ✅ **Boletas en PDF**: generar el PDF de cada movimiento con el mismo
   formato de FO-SE-013/FO-SE-012/FO-SE-066 (folio, líneas, espacios de
   firma) para imprimir y firmar a mano, conservando también el registro
   digital.
5. ✅ **Reportes**: stock actual y valorización por bodega, alertas de stock
   por los 3 umbrales (óptimo/alerta/crítico) en Bodega 1, activos/equipos
   actualmente prestados y por quién, kardex por artículo/activo, exportar
   a Excel/PDF. Vista de solo lectura para el rol Contabilidad.
6. ⬜ **Extras**: fotos, modo "conteo físico", respaldo automático de la base
   de datos, y — si más adelante lo confirman — soporte para lector de
   código de barras (el mismo campo de captura ya queda listo para eso).

## Operación y mantenimiento

### Levantar el sistema

```bash
# Desarrollo (la máquina donde se programa): recarga sola al guardar
docker compose up -d

# Producción (la PC servidor de la oficina): Waitress, con migrate y
# collectstatic incluidos. Requiere DJANGO_DEBUG=False en el .env.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Actualizar el sistema en el servidor es volver a ejecutar esa misma línea de
producción: aplica migraciones, recopila los estáticos y reinicia.

Antes de dejarlo corriendo por primera vez conviene revisar la configuración
con `manage.py check --deploy`. Debe salir limpio: los 4 avisos que piden
HTTPS están silenciados a propósito y explicados en `config/settings.py`.

### Acceso desde el resto de la red (RF-15)

Las demás computadoras y las tablets entran por navegador a la IP de la PC
servidor: `http://<IP-del-servidor>:8000`. Para que funcione hacen falta
tres cosas, y las tres ya están puestas:

1. **Regla de firewall** que abra el puerto 8000 de entrada.
2. **Perfil de red "Privada"** en Windows. Con perfil "Pública" el firewall
   bloquea la conexión aunque la regla exista.
3. **La IP en `DJANGO_ALLOWED_HOSTS`** del `.env`. Con `DEBUG=False` Django
   rechaza cualquier host que no esté en esa lista, con un error 400.

⚠️ **La IP tiene que ser fija.** Hoy la asigna el router por DHCP y ya cambió
una vez (de `192.168.1.17` a `192.168.1.6`). Cuando cambia, se rompen dos
cosas a la vez: el enlace que tiene guardado la gente deja de responder, y
Django empieza a rechazar el host. Hay que resolverlo de una de estas dos
formas, **antes de repartir el enlace al personal**:

- **Reserva DHCP en el router** (lo más recomendable): se le dice al router
  que a esa PC siempre le dé la misma IP. No hay que tocar nada en Windows.
- **IP estática en Windows**: configurarla a mano en el adaptador de red.
  Funciona, pero hay que elegir una IP fuera del rango que reparte el router
  o dos equipos pueden terminar con la misma.

Después de fijarla, actualizar `DJANGO_ALLOWED_HOSTS` en el `.env` y
reiniciar con `docker compose restart web`.

### Qué se puede borrar del catálogo y qué no

- **Sin movimientos** → se borra.
- **Solo con el "saldo inicial"** que crea la carga masiva → se borra, y ese
  ajuste se va con él. No es historial: es el conteo con el que arrancó. Sin
  esta distinción, importar el Excel dejaba los 216 artículos imposibles de
  borrar para siempre, incluso los importados por error.
- **Con movimientos registrados por alguien** → no se borra, y desactivarlo
  *tampoco* lo habilita. Para sacarlo de circulación se desmarca como activo
  (o, en Bodega Técnica, se pasa a "De baja"): deja de aparecer en el
  buscador y en las listas de captura, pero su kardex se conserva.

Para **empezar de cero** (una carga masiva que salió mal, el Excel con las
columnas cambiadas), borrar 200 artículos uno por uno no es viable:

```bash
docker compose exec web python manage.py limpiar_catalogo --que ventas
# muestra qué se borraría y NO toca nada; agregar --si-estoy-seguro para hacerlo
```

No está en la interfaz a propósito: es irreversible, y un botón de "borrar
todo" a un clic en la pantalla de catálogo es un accidente esperando a pasar.

### Comandos del día a día

```bash
docker compose exec web python manage.py test
docker compose exec web python manage.py recalcular_stock --solo-revisar
docker compose exec web python manage.py crear_usuario <usuario> <rol>
docker compose exec web python manage.py cambiar_clave <usuario> --generar
```

```powershell
.\scripts\respaldo.ps1     # respaldar la base de datos
.\scripts\restaurar.ps1    # ver los respaldos disponibles
```

- **Respaldos (RNF-08)**: ver [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md)
  para dejarlo automático en el servidor. Se conservan 30 días.
- **Usuarios**: lo normal es hacerlo desde la pantalla **Administración →
  Usuarios** del propio sistema (ver abajo). Los comandos quedan como salida
  de emergencia, para cuando nadie pueda entrar.
- **Cambiar contraseñas**: `cambiar_clave` con `--generar` produce una fuerte
  y la muestra una sola vez.

### Pantalla de usuarios

Crear, editar, desactivar y restablecer contraseñas se hace desde el sistema,
no desde el panel `/admin/` de Django. El panel muestra grupos, permisos,
`is_staff` y `is_superuser` — cosas que este sistema no usa (el rol lo decide
todo) y que un administrador no técnico podría cambiar sin querer y dejarse
fuera. Solo la ve el rol administrador.

Dos detalles que salieron de un bloqueo real, no de la teoría:

- **El nombre de usuario se guarda siempre en minúsculas**, y al entrar da
  igual cómo se escriba. En tablets el teclado capitaliza la primera letra
  solo: así se creó un "Karla" que después nadie lograba escribir igual para
  iniciar sesión.
- **Si se escribe una contraseña, esa es la que vale**, aunque la casilla de
  "Generar" haya quedado marcada. Antes ganaba la generada en silencio, con
  lo que alguien ponía la suya, se guardaba otra al azar, y se quedaba fuera
  sin entender por qué.

Tres reglas que la pantalla hace cumplir sola:

- **El rol manda sobre el panel de Django**: solo el administrador recibe
  `is_staff`. Así los dos no se pueden contradecir según por dónde se edite.
- **Nadie se puede dejar fuera a sí mismo**: no se puede quitar el propio rol
  de administrador, ni desactivarse, ni borrarse. Y no deja que el sistema se
  quede sin ningún administrador activo.
- **A quien ya registró movimientos no se le borra, se le desactiva**: pierde
  el acceso pero su historial conserva el autor. Borrarlo dejaría los
  registros sin saber quién los hizo, que es justo lo que este sistema vino a
  resolver. La pantalla lo explica y ofrece desactivar en su lugar.
- **Auditar el stock**: `recalcular_stock --solo-revisar` compara el stock
  guardado contra el historial de movimientos y avisa si algo no cuadra; sin
  `--solo-revisar` lo corrige.

### Pruebas automatizadas

219 pruebas cubren lo que no se puede romper en silencio: cálculo de stock
(alta, edición y borrado de movimientos), atomicidad de un documento
completo, préstamos y devoluciones en ambos módulos, umbrales de alerta,
generación del código interno, carga masiva desde Excel, paginación con
filtros, las boletas en PDF, el formato de números de Guatemala, la gestión
de usuarios (incluidas las protecciones contra dejarse fuera), qué se puede
borrar del catálogo y qué no, los reportes y su exportación a Excel, y los
permisos de los tres roles. Correrlas antes de cada commit evita
reintroducir errores ya corregidos.

## Pendiente conocido (deuda técnica)

Registrado a conciencia, no olvidado:

- **Respaldo automático sin programar**: los scripts funcionan y están
  probados con una restauración real, pero hoy hay que ejecutarlos a mano.
  Falta dejarlos en el Programador de tareas de Windows del servidor — el
  paso a paso está en [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md).
- **Correlativo de folio bajo concurrencia**: se calcula dentro de la
  transacción, pero no hay una secuencia en la base. Con 4–10 personas es
  muy improbable que choquen; si alguna vez pasa, la solución es una
  secuencia de PostgreSQL por tipo de documento.
- **Devolución parcial de un préstamo/demo**: si salieron 3 equipos y
  regresan 2, hoy no se puede cerrar a medias — la fila se cierra completa.
  No apareció como caso real todavía; si aparece, hay que separar la
  devolución en su propia tabla.
- **La hoja de préstamos se limita a 300 registros** por impresión. Si el
  filtro trae más, se pide acotarlo en vez de generar un PDF de decenas de
  páginas por accidente.
- **Las fotos subidas las sirve Django**, no un servidor de archivos. La
  documentación lo desaconseja para sitios de tráfico alto; para 4–10
  personas en red local es la opción sensata y evita montar un nginx aparte.

Ya resueltos (quedan aquí para dejar rastro):

- Paginación de catálogos y autocompletado en vivo (RF-13).
- **Servidor de producción**: Waitress + WhiteNoise vía
  `docker-compose.prod.yml`, con `DEBUG=False` y `check --deploy` limpio.
- **Puerto 5432**: atado a `127.0.0.1`, ya no es alcanzable desde la red.
- **Contraseñas débiles**: rotadas, y con `cambiar_clave` para hacerlo de
  nuevo cuando haga falta.
- **Formato de números**: `config/formats/es/formats.py` deja los precios
  como `Q 1,500.00` y las fechas en día/mes/año.

## Verificación

- Cada fase se prueba corriendo el servidor y accediendo desde otro equipo
  de la red por IP.
- La carga masiva se probará importando los Excel reales del repo.
- El flujo de captura manual se probó end-to-end en un navegador real
  (Playwright, Chromium): escribir en el buscador, elegir con el teclado,
  agregar líneas, guardar, y ver el stock reflejado. Se comprobó también el
  rechazo de una salida sin stock (el documento no queda a medias), el
  ciclo completo de préstamo/demo con su devolución, y el ciclo de
  préstamo/regreso de herramienta con el cambio de estado del activo.
- El rol Contabilidad se comprueba en cada fase: ve los historiales (200) y
  recibe 403 en las pantallas de registro, sin botones para registrar.
- Las boletas en PDF se revisaron **abriendo los archivos generados**, no
  solo comprobando que existieran: se compararon el encabezado, la casilla
  marcada, el detalle y los espacios de firma contra las fotos de los
  formatos de papel que están en `pdf/`. Ahí aparecieron dos defectos que
  ninguna prueba automática habría visto — un nombre largo se salía de su
  fila, y el bloque de firmas se iba solo a una segunda hoja.
- Los datos de prueba que generan estas verificaciones se borran al
  terminar y se revisa con `manage.py recalcular_stock --solo-revisar` que
  el stock quede cuadrado.

## Pendiente a confirmar con el usuario antes de cerrar el plan

- Ninguno por ahora — el lector de código de barras queda descartado para
  esta primera versión (ver "Extras", fase 6) y los estados/umbrales ya
  están definidos.
