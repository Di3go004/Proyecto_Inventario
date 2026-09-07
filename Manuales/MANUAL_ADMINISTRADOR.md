# Manual del administrador — Control de Bodega

**Soluciones Exactas, S.A.**

Sos quien tiene acceso a todo el sistema: el catálogo, los movimientos, los
reportes, los usuarios y las listas de categorías y proveedores. Este manual
recorre cada pantalla en el orden en que las vas a usar.

Hay tres manuales más, uno por cada rol, para que le des a cada persona solo
lo que le toca:

- `MANUAL_OPERADOR.md` — quien registra entradas, salidas y préstamos
- `MANUAL_CONTABILIDAD.md` — quien consulta e imprime los reportes
- `MANUAL_PRACTICANTE.md` — quien captura el catálogo

---

## Índice

1. [Cómo entrar](#1-cómo-entrar)
2. [El Resumen](#2-el-resumen)
3. [Quién puede hacer qué](#3-quién-puede-hacer-qué)
4. [Catálogo — Bodega 1 y 2](#4-catálogo--bodega-1-y-2)
5. [Catálogo — Bodega Técnica](#5-catálogo--bodega-técnica)
6. [Entradas y salidas (FO-SE-013 y FO-SE-012)](#6-entradas-y-salidas-fo-se-013-y-fo-se-012)
7. [Préstamos de herramienta (FO-SE-066)](#7-préstamos-de-herramienta-fo-se-066)
8. [Reportes](#8-reportes)
9. [Usuarios](#9-usuarios)
10. [Categorías](#10-categorías)
11. [Proveedores](#11-proveedores)
12. [Carga masiva desde Excel](#12-carga-masiva-desde-excel)
13. [Respaldos y mantenimiento](#13-respaldos-y-mantenimiento)
14. [Cuando algo sale mal](#14-cuando-algo-sale-mal)

---

## 1. Cómo entrar

Desde cualquier computadora, tablet o celular **conectado a la red de la
oficina**, abrí el navegador y entrá a:

```
http://192.168.1.200:8000
```

**No necesita internet.** El sistema vive en la computadora de la oficina; si
se cae el internet, sigue funcionando igual para todos los que estén en la red.

El usuario no distingue mayúsculas (da igual `admin` que `Admin`); la
contraseña sí.

<!-- CAPTURA: pantalla de inicio de sesión -->
![Pantalla de inicio de sesión](capturas-admin/01-login.png)

> Si una computadora no conecta, revisá el paso 10 de
> `Docs/PUESTA_EN_MARCHA.md`, que tiene la lista de comprobaciones.

---

## 2. El Resumen

Es la primera pantalla al entrar. Está pensada para mirarla y saber en diez
segundos cómo están las dos bodegas.

<!-- CAPTURA: Resumen general completo, con las tarjetas y los tres paneles -->
![Resumen general](capturas-admin/02-resumen.png)

**Las cuatro tarjetas de arriba:**

| Tarjeta | Qué dice |
|---|---|
| **Artículos activos (Ventas)** | Cuántos productos hay en el catálogo de Bodega 1 y 2 |
| **Valorización Bodega 1+2** | Precio × existencia de todo lo que hay para vender |
| **Valorización Bodega Técnica** | Lo mismo para la herramienta interna |
| **Préstamos / demos abiertos** | Equipo que salió y todavía no regresa |

**Los tres paneles de abajo:**

- **Alertas de stock — Bodega 1 y 2**: los diez más urgentes. Hacé clic en
  cualquiera para ir a su ficha, o en *Ver las N →* para el reporte completo.
- **Alertas de stock — Bodega Técnica**: lo mismo para la herramienta.
- **Activos técnicos prestados**: quién tiene qué y desde cuándo.

> Las dos tarjetas de valorización y los enlaces *Ver las N →* **solo los ven
> el administrador y contabilidad**. Al operador se le muestra en su lugar el
> número de activos de Bodega Técnica.

---

## 3. Quién puede hacer qué

Esta tabla es la que conviene tener a mano cuando le des de alta a alguien.

| | Administrador | Operador | Contabilidad | Practicante |
|---|:---:|:---:|:---:|:---:|
| Resumen | ✅ | ✅ | ✅ | ❌ |
| Ver los catálogos | ✅ | ✅ | ✅ | ✅ |
| Crear/editar/eliminar productos | ✅ | ❌ | ❌ | ✅ |
| Entradas y salidas | ✅ | ✅ | ❌ | ❌ |
| Préstamos de herramienta | ✅ | ✅ | ❌ | ❌ |
| Dar de baja en Bodega Técnica | ✅ | ✅ | ❌ | ❌ |
| **Reportes y valorización** | ✅ | ❌ | ✅ | ❌ |
| Usuarios, categorías, proveedores | ✅ | ❌ | ❌ | ❌ |

Dos cosas que suelen confundir:

- **El operador no ve los reportes ni cuánto vale el inventario.** Mueve
  bodega, y para eso no le hace falta. Sí ve en el Resumen qué hay que reponer.
- **El practicante no registra movimientos.** Solo captura el catálogo. Ni
  siquiera entra al Resumen: cae directo en Bodega 1 y 2.

<!-- CAPTURA: barra lateral del administrador, con todas las secciones visibles -->
![Barra lateral del administrador](capturas-admin/03-navegacion.png)

---

## 4. Catálogo — Bodega 1 y 2

Los productos que la empresa vende: indicadores, básculas, pesas y repuestos.

<!-- CAPTURA: catálogo de Bodega 1 y 2 con varios productos -->
![Catálogo de Bodega 1 y 2](capturas-admin/04-catalogo-ventas.png)

### Buscar y filtrar

El buscador de arriba encuentra por **código o nombre del producto**.
Abriendo **Filtros** podés combinar **bodega, proveedor, nivel de stock,
estado y rango de precio**, todos a la vez y junto con el buscador.

<!-- CAPTURA: panel de Filtros abierto con varios filtros aplicados -->
![Filtros del catálogo](capturas-admin/05-filtros.png)

### Crear un producto

**+ Nuevo artículo**, arriba a la derecha.

| Campo | ¿Obligatorio? | Qué poner |
|---|---|---|
| **Código interno** | No | **Dejalo vacío**: se arma solo como `SE-MODELO-CAPACIDAD` |
| **Número de serie** | No | Si el equipo no trae placa, dejalo vacío: aparece como `S/S` |
| **Producto** | **Sí** | El nombre completo, sin abreviar |
| **Marca / Modelo / Capacidad** | No | BRECKNELL, LP7510, 300 kg… |
| **Bodega** | **Sí** | Bodega 1 (equipo) o Bodega 2 (repuestos) |
| **Categoría / Proveedor** | No | De la lista, o escribí uno nuevo y se crea solo |
| **Precio (Q)** | **Sí** | Se usa para valorizar el inventario |
| **Foto** | No | Subila como archivo (JPG/PNG, máx. 5 MB) |
| **Stock óptimo / alerta / crítico** | **Sí** | Vienen en 20 / 5 / 2 |
| **Activo** | — | Desmarcalo para retirarlo del catálogo sin borrarlo |

<!-- CAPTURA: formulario de nuevo artículo, vacío -->
![Formulario de nuevo artículo](capturas-admin/06-articulo-nuevo.png)

**El stock no se escribe acá.** Se calcula solo desde las entradas y salidas.
Si un producto tiene que arrancar con existencia, registrale un ingreso.

**Los tres umbrales** deciden cuándo el sistema avisa que hay que reponer:

- **Óptimo (20)** — bien surtido, chip verde
- **Alerta (5)** — por debajo avisa en amarillo
- **Crítico (2)** — por debajo avisa en rojo

Tienen que cumplir **crítico ≤ alerta ≤ óptimo**; si no, el sistema no deja
guardar y lo explica en pantalla.

### La ficha de un producto

Hacé clic en cualquier fila. Ahí ves su foto, sus datos, su nivel de stock y el
enlace **Ver kardex completo**.

<!-- CAPTURA: ficha de un artículo con datos y foto -->
![Ficha de un artículo](capturas-admin/07-articulo-ficha.png)

### El kardex

Todo lo que le pasó a ese producto: cada entrada, cada salida, con su fecha,
folio y quién la registró. Es lo que responde *"¿por qué este producto tiene
esta cantidad?"*.

<!-- CAPTURA: kardex de un artículo con varios movimientos -->
![Kardex de un artículo](capturas-admin/08-kardex.png)

### Eliminar un producto

El sistema **no deja borrar** un producto que ya tiene movimientos: se perdería
el historial. Si ya no se vende, desmarcá **Activo** en vez de borrarlo.

---

## 5. Catálogo — Bodega Técnica

La herramienta y el equipo de uso interno. No se vende: se presta y se devuelve.

<!-- CAPTURA: catálogo de Bodega Técnica -->
![Catálogo de Bodega Técnica](capturas-admin/09-catalogo-tecnica.png)

Funciona casi igual que Bodega 1 y 2, con **cuatro diferencias**:

### Diferencia 1 — el código interno sí se escribe

Acá no se genera solo: lo asigna la empresa (`SE-TE001`, `SE-EP012`…).

### Diferencia 2 — un activo nace en 0

El campo **Cantidad en bodega** sale bloqueado al crear. La cantidad entra con
un ingreso (FO-SE-013), igual que en Bodega 1 y 2.

### Diferencia 3 — el interruptor de consumible

Marcá **Es consumible** en lo que se gasta: tornillos, brocas, cinta, pintura.

- **Marcado**: después se puede corregir la cantidad escribiéndola en Editar, y
  queda registrado como ajuste
- **Sin marcar**: la cantidad solo cambia con un ingreso o una baja

### Diferencia 4 — el estado

Son tres, de mejor a peor:

| Estado | Cuándo |
|---|---|
| **Buen estado** | Sirve bien |
| **Próximo a reemplazo** | Todavía sirve, pero está gastada: hay que ir comprando la de repuesto |
| **Mal estado** | Ya no sirve |

<!-- CAPTURA: formulario de nuevo activo, mostrando cantidad bloqueada, consumible y estado -->
![Formulario de nuevo activo](capturas-admin/10-activo-nuevo.png)

### Dar de baja

Es **lo único que baja la existencia** de Bodega Técnica. Entrá a la ficha del
activo y usá **Dar de baja**. Pide cuatro cosas: *¿Cuántas se dan de baja?*,
*Motivo* (dañado, extraviado, consumido u otro), *Fecha* y una observación.
No genera boleta — queda solo en el registro.

<!-- CAPTURA: pantalla de dar de baja, con cantidad y motivo -->
![Dar de baja](capturas-admin/11-dar-de-baja.png)

> Prestar **no** baja la existencia: la herramienta sigue siendo de la bodega y
> va a volver.

---

## 6. Entradas y salidas (FO-SE-013 y FO-SE-012)

**Movimientos → Entradas y salidas.** Es el registro digital de las boletas de
papel: una boleta = un folio = varias líneas de producto.

<!-- CAPTURA: lista de entradas y salidas con varios movimientos -->
![Entradas y salidas](capturas-admin/12-movimientos.png)

### Registrar un ingreso

Botón **+ Ingreso**. Llena primero la cabecera:

| Campo | Qué poner |
|---|---|
| **Folio de la boleta** | **El número impreso en el talonario de papel.** El sistema propone el siguiente, pero mandá siempre el del papel |
| **Fecha del movimiento** | Por defecto ahora; cambiala si estás digitando una boleta vieja |
| **Tipo de movimiento** | Venta · Préstamo/Demo · Repuestos · Materiales/Otro |
| **Solicitado por** | Quién pidió el movimiento |
| **No. de factura** | La factura del proveedor |
| **Boleta de ingreso a bodega** | Si el papel trae otro número aparte del folio |
| **Observación** | Lo que no cabe en los campos |

Después agregá las líneas: producto, cantidad y precio. Podés agregar tantas
como traiga la boleta.

<!-- CAPTURA: formulario de ingreso con la cabecera llena y dos líneas -->
![Registrar ingreso](capturas-admin/13-ingreso.png)

### Registrar una salida

Botón **+ Salida**. La cabecera trae tres campos más: **Entregado por**,
**Cliente** y **Envío / recibo**.

### El PDF para imprimir y firmar

Desde la pantalla del folio, **Imprimir boleta (PDF)**. Sale en **media carta**,
igual que el talonario físico, listo para imprimir y firmar.

<!-- CAPTURA: pantalla del detalle de un folio con el botón de PDF -->
![Detalle de un folio](capturas-admin/14-documento.png)

<!-- CAPTURA: el PDF generado, para comparar con la boleta de papel -->
![Boleta en PDF](capturas-admin/15-boleta-pdf.png)

### Cuando la salida era un préstamo o demo

Si el tipo fue **Préstamo / Demo**, el movimiento queda **abierto** hasta que el
equipo regrese. En la lista aparece marcado; para cerrarlo usá **Registrar
devolución** y anotá la fecha y quién lo devolvió.

<!-- CAPTURA: registrar el regreso de un equipo en demo -->
![Devolución de un demo](capturas-admin/16-devolucion-demo.png)

---

## 7. Préstamos de herramienta (FO-SE-066)

**Movimientos → Préstamos de herramienta.** Es el flujo de Bodega Técnica:
quién se llevó qué, en qué estado salió y en qué estado volvió.

<!-- CAPTURA: lista de préstamos, con uno abierto y uno cerrado -->
![Préstamos de herramienta](capturas-admin/17-prestamos.png)

El botón **Imprimir hoja (PDF)** saca la hoja de control con el formato del
FO-SE-066, para tenerla física en la bodega.

### Registrar una salida

**+ Registrar salida**. Se elige el activo con el buscador, la cantidad, quién
lo solicita, quién lo entrega y **en qué estado sale**.

El sistema no deja prestar más unidades de las que hay libres.

<!-- CAPTURA: formulario de salida de herramienta -->
![Salida de herramienta](capturas-admin/18-prestamo-salida.png)

### Registrar el regreso

En la fila del préstamo abierto, **Registrar regreso**. Se anota quién lo
recibe y **en qué estado volvió** — ahí es donde se marca una herramienta como
*Próximo a reemplazo* o *Mal estado* si volvió gastada.

<!-- CAPTURA: formulario de regreso, mostrando el estado al salir y al volver -->
![Regreso de herramienta](capturas-admin/19-prestamo-regreso.png)

---

## 8. Reportes

**Reportes** en la barra lateral. Son cinco, y todos se pueden **descargar a
Excel** para trabajarlos aparte.

<!-- CAPTURA: índice de reportes con las seis tarjetas -->
![Índice de reportes](capturas-admin/20-reportes-indice.png)

| Reporte | Para qué sirve |
|---|---|
| **Existencias y valorización** | Cuánto hay en cada bodega y cuánto vale. El que se cruza contra el conteo físico |
| **Alertas de stock** | Qué reponer, lo más urgente primero. Bodega Técnica va en su propia sección |
| **Movimientos por período** | Qué entró y qué salió entre dos fechas |
| **Inventario de Bodega Técnica** | La herramienta con su estado, existencia y cuántas están prestadas |
| **Fuera de bodega** | Todo lo que está afuera ahora: préstamos y demos |

<!-- CAPTURA: reporte de existencias con la tabla por bodega y el detalle -->
![Reporte de existencias](capturas-admin/21-reporte-existencias.png)

<!-- CAPTURA: reporte de alertas, mostrando la sección de Bodega Técnica -->
![Reporte de alertas](capturas-admin/22-reporte-alertas.png)

> El Excel de alertas trae **dos hojas**: una por bodega. Los montos salen como
> número, no como texto, así que se pueden sumar y ordenar sin reformatear.

---

## 9. Usuarios

**Administración → Usuarios.** Solo vos entrás acá.

<!-- CAPTURA: lista de usuarios con sus roles -->
![Usuarios del sistema](capturas-admin/23-usuarios.png)

### Crear un usuario

**+ Nuevo usuario**. Los campos son *Usuario para iniciar sesión*, *Rol en el
sistema*, *Nombres*, *Apellidos* y la contraseña.

Marcá **Generar una contraseña segura** y el sistema la arma y te la muestra
**una sola vez**. Copiala y entregala en persona; después ya no se puede ver,
solo cambiar. Si preferís ponerla vos, usá *O escribir una contraseña*.

<!-- CAPTURA: formulario de nuevo usuario, con el selector de rol desplegado -->
![Nuevo usuario](capturas-admin/24-usuario-nuevo.png)

<!-- CAPTURA: la pantalla que muestra la contraseña generada -->
![Contraseña generada](capturas-admin/25-usuario-clave.png)

### Cambiar una contraseña

Botón **Contraseña** en la fila del usuario. Se usa cuando alguien la olvidó o
cuando se filtró.

### Dar de baja a alguien

**Desmarcá "Puede iniciar sesión"** en vez de eliminarlo: así no entra pero se
conserva quién registró cada movimiento. Eliminarlo solo tiene sentido si nunca
llegó a usar el sistema.

> **Cuando alguien se va de la empresa, desactivalo el mismo día.**

---

## 10. Categorías

**Administración → Categorías.** Sirven para agrupar el catálogo y filtrarlo.

<!-- CAPTURA: lista de categorías con el conteo de productos -->
![Categorías](capturas-admin/26-categorias.png)

Cada categoría muestra cuántos productos la usan. Si borrás una que está en
uso, **los productos no se borran**: quedan sin categoría y se les puede
asignar otra.

---

## 11. Proveedores

**Administración → Proveedores.** La lista de a quién se le compra.

<!-- CAPTURA: lista de proveedores con el filtro de origen -->
![Proveedores](capturas-admin/27-proveedores.png)

Cada proveedor lleva **contacto**, **teléfono** y un **origen**:

- **Local** — se consigue en el país
- **Extranjero** — es importado, hay que pedirlo con mucha más anticipación
- **Sin clasificar** — todavía nadie dijo cuál es

El origen aparece en el reporte de alertas: si lo que falta es importado, sale
marcado, para que sepas que no lo vas a tener en dos días.

> La lista avisa cuántos están **sin clasificar**. Vale la pena irlos
> clasificando: es lo que hace útil ese aviso.

Igual que con las categorías, borrar un proveedor **no borra sus productos**.

---

## 12. Carga masiva desde Excel

Para cargar muchos productos de una sola vez desde los archivos `FO-SE-053`
(Bodega 1 y 2) o `FO-SE-065` (Bodega Técnica).

**Catálogo → Carga masiva desde Excel.** Son tres pasos:

1. **Subir** el archivo y elegir de qué hoja (mes) importar
2. **Mapear**: confirmar qué columna del Excel corresponde a cada dato. El
   sistema propone el mapeo solo; revisalo
3. **Confirmar**: se ve una vista previa antes de guardar nada

<!-- CAPTURA: paso 1, subir el archivo y elegir la hoja -->
![Carga masiva — subir](capturas-admin/28-carga-subir.png)

<!-- CAPTURA: paso 2, mapeo de columnas con la vista previa -->
![Carga masiva — mapear](capturas-admin/29-carga-mapear.png)

En Bodega 1 y 2 el **código interno no se mapea**: se genera solo. En Bodega
Técnica **sí se importa tal cual**, porque lo asigna la empresa.

Los productos que ya existen se actualizan; los nuevos se crean con su
cantidad como saldo inicial.

> **Hacé un respaldo antes de una carga masiva.** Si el mapeo sale mal, es
> mucho más rápido restaurar que corregir a mano.

---

## 13. Respaldos y mantenimiento

Esto se hace desde **PowerShell**, en la computadora servidor, dentro de la
carpeta del proyecto.

### Respaldar

```powershell
.\scripts\respaldo.ps1
```

Guarda un archivo en `respaldos\` con la fecha en el nombre y borra los que
pasen de 30 días. **Corré esto antes de cualquier cosa grande**: una carga
masiva, una limpieza, una actualización.

### Restaurar

```powershell
.\scripts\restaurar.ps1                                    # ver los disponibles
.\scripts\restaurar.ps1 -Archivo respaldos\bodega_....dump # restaurar uno
.\scripts\restaurar.ps1 -Archivo respaldos\... -SoloProbar # probarlo sin tocar nada
```

Pide escribir `RESTAURAR` en mayúsculas antes de hacer nada. **Reemplaza todo
el contenido actual.**

### Comprobar que el stock cuadra

```powershell
docker compose exec web python manage.py recalcular_stock --solo-revisar
```

Informa las diferencias sin corregir nada. Sin `--solo-revisar`, las corrige
recalculando desde el historial.

### Cambiar una contraseña desde la terminal

```powershell
docker compose exec web python manage.py cambiar_clave admin --generar
```

Sirve cuando no podés entrar al sistema para hacerlo desde la pantalla.

### Empezar de cero

```powershell
docker compose exec web python manage.py limpiar_catalogo --que todo
docker compose exec web python manage.py limpiar_historial_tecnica
```

Sin `--si-estoy-seguro` solo informan qué se borraría. **Son irreversibles**:
respaldá primero.

- `limpiar_catalogo` borra productos **e** historial
- `limpiar_historial_tecnica` borra solo el historial de Bodega Técnica y deja
  las existencias en 0, **conservando el catálogo**

---

## 14. Cuando algo sale mal

| Síntoma | Qué revisar |
|---|---|
| Una PC no abre el sistema | ¿Está en la red de la oficina? ¿La IP es `192.168.1.200`? Ver paso 10 de `Docs/PUESTA_EN_MARCHA.md` |
| "No tienes permiso para ver esta pantalla" | El rol de esa persona no la alcanza. Revisá la tabla de la sección 3 |
| El stock no cuadra con el conteo físico | `recalcular_stock --solo-revisar` primero; si hay diferencias, registrá el ajuste como movimiento |
| No deja borrar un producto | Ya tiene movimientos. Desmarcá **Activo** en vez de borrarlo |
| No deja guardar los umbrales | Tienen que cumplir crítico ≤ alerta ≤ óptimo |
| Alguien se fue de la empresa | Desactivalo en Usuarios el mismo día |

Si algo se rompió de verdad, el respaldo más reciente está en `respaldos\`.

---

## Recordá

1. **Respaldá antes de cualquier cosa grande** — carga masiva, limpieza, actualización
2. **El folio se escribe del papel**, no se inventa
3. **Desactivar, no eliminar** — se conserva el historial
4. **La contraseña generada se ve una sola vez** — copiala en el momento
5. **Clasificá los proveedores** — es lo que hace útil la alerta de importados

---

## Cómo agregar las capturas a este manual

Guardá cada imagen en la carpeta `capturas-admin/`, junto a este archivo, con
el nombre exacto que ya trae escrito cada bloque (`01-login.png`,
`02-resumen.png`…). Al abrir el manual en cualquier visor de Markdown las
imágenes aparecen solas donde corresponde.

La lista completa, con qué debe mostrar cada una, está en
`capturas-admin/LEEME.txt`.

Todas se toman **entrando con un usuario de rol Administrador**, para que se
vea lo mismo que va a ver quien lea el manual.
