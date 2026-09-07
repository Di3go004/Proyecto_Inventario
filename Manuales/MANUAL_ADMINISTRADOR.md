# INSTRUCTIVO SISTEMA DE INVENTARIO — PERFIL ADMINISTRADOR

**IT-005**

> **Borrador de trabajo.** El documento formal es
> `INSTRUCTIVO SISTEMA DE INVENTARIO IT-005.docx`, que ya trae el encabezado,
> el control documental y el pie de página del Sistema de Gestión. De aquí se
> copia el texto hacia esa plantilla.

---

## Datos para el control documental

| Campo | Valor |
|---|---|
| Código | IT-005 |
| Versión | 01 |
| Elaborado por | Proyectos |
| Revisado por | Gerente Administrativo |
| Aprobado por | Gerente Técnico |

Encabezado de cada página: **SOLUCIONES EXACTAS, S.A.** ·
*Instructivo Sistema de Inventario* · Código IT-005 · Versión 01 · Página N de M.

---

## 1. OBJETIVO

El presente instructivo tiene como objetivo establecer una guía clara y de
fácil comprensión para el uso del Sistema de Control de Bodega por parte del
personal con perfil de **Administrador**. A través de este documento se busca
estandarizar el registro de los movimientos de inventario, garantizar la
trazabilidad de cada entrada, salida y préstamo, y asegurar que la información
de las bodegas se mantenga uniforme y confiable.

El sistema sustituye el control que anteriormente se llevaba en los libros de
Excel **FO-SE-053** (Bodega 1 y 2) y **FO-SE-065** (Bodega Técnica),
conservando los mismos formatos físicos de registro: **FO-SE-013** para
ingresos, **FO-SE-012** para salidas y **FO-SE-066** para préstamos de
herramienta.

Este instructivo aplica únicamente al perfil de Administrador. Los perfiles de
Operador de Bodega, Contabilidad y Practicante cuentan con su propio documento.

---

## 2. CONTENIDO

### 2.1. Acceso al Sistema

El sistema se encuentra alojado en una computadora de la oficina y se utiliza
desde el navegador de cualquier equipo conectado a la red interna, sea
computadora, tableta o teléfono.

Se deberá ingresar a la siguiente dirección:

```
http://192.168.1.200:8000
```

**Nota importante:** el sistema **no requiere conexión a internet**. Al residir
en la red local de la empresa, permanece disponible aun cuando el servicio de
internet se encuentre interrumpido.

El nombre de usuario no distingue entre mayúsculas y minúsculas; la contraseña
sí las distingue.

<!-- CAPTURA: pantalla de inicio de sesión -->
![Pantalla de inicio de sesión](capturas-admin/01-login.png)

En caso de que algún equipo no logre establecer conexión, se deberá consultar
el apartado correspondiente del documento `PUESTA_EN_MARCHA.md`.

---

### 2.2. Perfiles de Usuario y Alcance de Cada Uno

El sistema cuenta con cuatro perfiles. La siguiente tabla resume qué puede
realizar cada uno:

| Función | Administrador | Operador | Contabilidad | Practicante |
|---|:---:|:---:|:---:|:---:|
| Pantalla de resumen | Sí | Sí | Sí | No |
| Consulta de catálogos | Sí | Sí | Sí | Sí |
| Alta, modificación y baja de productos | Sí | No | No | Sí |
| Registro de entradas y salidas | Sí | Sí | No | No |
| Registro de préstamos de herramienta | Sí | Sí | No | No |
| Baja de existencia en Bodega Técnica | Sí | Sí | No | No |
| Reportes y valorización | Sí | No | Sí | No |
| Usuarios, categorías y proveedores | Sí | No | No | No |

**Nota importante:** el perfil de Operador de Bodega no tiene acceso a los
reportes ni a la valorización del inventario. Su función es registrar
movimientos, para lo cual dicha información no resulta necesaria. La
información sobre qué productos requieren reposición sí se encuentra
disponible para él en la pantalla de resumen.

**Nota importante:** el perfil de Practicante no registra movimientos de
ningún tipo. Su función se limita a la captura del catálogo, por lo que el
sistema lo dirige directamente a esa pantalla al iniciar sesión.

<!-- CAPTURA: barra lateral del administrador, con todas las secciones visibles -->
![Barra lateral del administrador](capturas-admin/03-navegacion.png)

---

### 2.3. Pantalla de Resumen

Constituye la primera pantalla que se presenta al iniciar sesión. Su propósito
es permitir una revisión rápida del estado de ambas bodegas.

<!-- CAPTURA: Resumen general completo, con las tarjetas y los tres paneles -->
![Resumen general](capturas-admin/02-resumen.png)

En la parte superior se presentan cuatro indicadores:

| Indicador | Descripción |
|---|---|
| Artículos activos (Ventas) | Cantidad de productos registrados en el catálogo de Bodega 1 y 2 |
| Valorización Bodega 1+2 | Precio multiplicado por existencia de todo el inventario de venta |
| Valorización Bodega Técnica | El mismo cálculo aplicado a la herramienta de uso interno |
| Préstamos / demos abiertos | Equipo que ha salido de bodega y aún no ha sido devuelto |

En la parte inferior se presentan tres paneles:

- **Alertas de stock — Bodega 1 y 2:** los diez productos más urgentes. Al
  seleccionar cualquiera de ellos se accede a su ficha; mediante el enlace
  *Ver las N* se accede al reporte completo.
- **Alertas de stock — Bodega Técnica:** el mismo listado para la herramienta.
- **Activos técnicos prestados:** relación de qué equipo se encuentra fuera de
  bodega, con quién y desde qué fecha.

**Nota importante:** los dos indicadores de valorización y los enlaces al
reporte de alertas se muestran únicamente a los perfiles de Administrador y
Contabilidad. Al perfil de Operador se le presenta en su lugar el número de
activos registrados en Bodega Técnica.

---

### 2.4. Catálogo de Bodega 1 y 2

Corresponde a los productos destinados a la venta: indicadores, básculas,
pesas y repuestos.

<!-- CAPTURA: catálogo de Bodega 1 y 2 con varios productos -->
![Catálogo de Bodega 1 y 2](capturas-admin/04-catalogo-ventas.png)

#### 2.4.1. Búsqueda y filtros

El buscador localiza productos por **código interno o nombre**. Mediante la
opción **Filtros** se pueden combinar, de forma simultánea y junto con el
buscador, los siguientes criterios: bodega, proveedor, nivel de stock, estado
y rango de precio.

<!-- CAPTURA: panel de Filtros abierto con varios filtros aplicados -->
![Filtros del catálogo](capturas-admin/05-filtros.png)

#### 2.4.2. Registro de un producto nuevo

Se deberá seleccionar la opción **+ Nuevo artículo**, ubicada en la parte
superior derecha de la pantalla, y completar los campos conforme a la
siguiente tabla:

| Campo | Obligatorio | Contenido |
|---|:---:|---|
| Código interno | No | Se deberá dejar vacío. El sistema lo genera como `SE-MODELO-CAPACIDAD` |
| Número de serie | No | Si el equipo no cuenta con placa, se deberá dejar vacío; el sistema lo presenta como `S/S` |
| Producto | **Sí** | Nombre completo, sin abreviaturas |
| Marca / Modelo / Capacidad | No | BRECKNELL, LP7510, 300 kg |
| Bodega | **Sí** | Bodega 1 (equipo) o Bodega 2 (repuestos) |
| Categoría / Proveedor | No | Se selecciona de la lista o se escribe uno nuevo, que el sistema registra automáticamente |
| Precio (Q) | **Sí** | Se utiliza para valorizar el inventario |
| Foto | No | Se deberá cargar como archivo JPG o PNG, con un máximo de 5 MB |
| Stock óptimo / alerta / crítico | **Sí** | Valores predeterminados: 20 / 5 / 2 |
| Activo | — | Al desmarcarlo, el producto se retira del catálogo sin eliminar su historial |

<!-- CAPTURA: formulario de nuevo artículo, vacío -->
![Formulario de nuevo artículo](capturas-admin/06-articulo-nuevo.png)

**Nota importante:** la existencia no se captura en esta pantalla. El sistema
la calcula a partir de las entradas y salidas registradas. Cuando un producto
deba iniciar con existencia, se deberá registrar el ingreso correspondiente.

#### 2.4.3. Umbrales de reposición

Los tres umbrales determinan en qué momento el sistema advierte que un
producto requiere reposición:

- **Óptimo (20):** nivel considerado bien surtido.
- **Alerta (5):** por debajo de este valor el sistema advierte en color ámbar.
- **Crítico (2):** por debajo de este valor el sistema advierte en color rojo.

**Nota importante:** los tres valores deberán cumplir la relación
**crítico ≤ alerta ≤ óptimo**. En caso contrario el sistema no permite guardar
el registro e indica el motivo en pantalla.

#### 2.4.4. Ficha del producto y kardex

Al seleccionar cualquier fila del catálogo se accede a la ficha del producto,
donde se presentan su imagen, sus datos, su nivel de reposición y el enlace
**Ver kardex completo**.

<!-- CAPTURA: ficha de un artículo con datos y foto -->
![Ficha de un artículo](capturas-admin/07-articulo-ficha.png)

El kardex presenta la totalidad de los movimientos del producto —cada entrada
y cada salida— con su fecha, folio y el usuario que los registró. Constituye
el respaldo de la existencia que muestra el sistema.

<!-- CAPTURA: kardex de un artículo con varios movimientos -->
![Kardex de un artículo](capturas-admin/08-kardex.png)

#### 2.4.5. Eliminación de un producto

**Nota importante:** el sistema no permite eliminar un producto que registre
movimientos, ya que se perdería su historial. Cuando un producto deje de
comercializarse, se deberá desmarcar la casilla **Activo** en lugar de
eliminarlo.

---

### 2.5. Catálogo de Bodega Técnica

Corresponde a la herramienta y el equipo de uso interno de la empresa. Este
inventario no se comercializa: se presta y se devuelve.

<!-- CAPTURA: catálogo de Bodega Técnica -->
![Catálogo de Bodega Técnica](capturas-admin/09-catalogo-tecnica.png)

Su funcionamiento es equivalente al de Bodega 1 y 2, con cuatro diferencias:

#### 2.5.1. El código interno se captura manualmente

A diferencia de Bodega 1 y 2, el sistema no genera el código: este es asignado
por la empresa conforme a su propia nomenclatura (`SE-TE001`, `SE-EP012`).

#### 2.5.2. Todo activo se registra con existencia cero

El campo **Cantidad en bodega** se presenta bloqueado durante el alta. La
existencia ingresa mediante un ingreso registrado con el formato **FO-SE-013**,
del mismo modo que en Bodega 1 y 2.

#### 2.5.3. Clasificación de consumibles

Se deberá marcar la casilla **Es consumible** en aquellos artículos que se
agotan con el uso: tornillos, brocas, cinta, pintura.

- **Marcado:** la cantidad puede corregirse escribiéndola en la opción
  *Editar*, y el sistema registra dicha corrección como un ajuste.
- **Sin marcar:** la cantidad únicamente se modifica mediante un ingreso o una
  baja.

#### 2.5.4. Estado del activo

El sistema contempla tres estados, ordenados de mejor a peor condición:

| Estado | Criterio de aplicación |
|---|---|
| Buen estado | El equipo se encuentra en condiciones adecuadas de uso |
| Próximo a reemplazo | El equipo continúa siendo utilizable, pero presenta desgaste y deberá programarse su reposición |
| Mal estado | El equipo ya no se encuentra en condiciones de uso |

<!-- CAPTURA: formulario de nuevo activo, mostrando cantidad bloqueada, consumible y estado -->
![Formulario de nuevo activo](capturas-admin/10-activo-nuevo.png)

#### 2.5.5. Baja de existencia

La baja constituye **el único movimiento que disminuye la existencia** de
Bodega Técnica. Se registra desde la ficha del activo, mediante la opción
**Dar de baja**, y requiere los siguientes datos: cantidad que se da de baja,
motivo (dañado, extraviado, consumido u otro), fecha y observación.

<!-- CAPTURA: pantalla de dar de baja, con cantidad y motivo -->
![Dar de baja](capturas-admin/11-dar-de-baja.png)

**Nota importante:** dar de baja no equivale a eliminar. La baja disminuye la
cantidad y conserva el activo en el catálogo junto con su historial; la
eliminación retira el registro por completo y únicamente procede cuando el
activo fue capturado por error.

**Nota importante:** la opción **Dar de baja** se presenta solamente cuando el
activo cuenta con existencia disponible. Si el activo se encuentra en cero, el
sistema indica en pantalla el motivo: que se dio de baja la totalidad, o bien
que aún no se le ha registrado ningún ingreso.

**Nota importante:** el préstamo de una herramienta no disminuye su
existencia. El equipo prestado continúa perteneciendo a la bodega y su
devolución se encuentra pendiente.

---

### 2.6. Registro de Entradas y Salidas (FO-SE-013 y FO-SE-012)

Corresponde al registro digital de las boletas físicas. Cada boleta constituye
un folio que puede contener varias líneas de producto.

<!-- CAPTURA: lista de entradas y salidas con varios movimientos -->
![Entradas y salidas](capturas-admin/12-movimientos.png)

#### 2.6.1. Registro de un ingreso

Se deberá seleccionar la opción **+ Ingreso** y completar el encabezado del
documento:

| Campo | Contenido |
|---|---|
| Folio de la boleta | El número impreso en la boleta física. El sistema propone el siguiente de la serie, el cual deberá corregirse cuando no corresponda |
| Fecha del movimiento | Se presenta la fecha actual; se deberá modificar cuando se digite una boleta de fecha anterior |
| Tipo de movimiento | Venta, Préstamo/Demo, Repuestos o Materiales/Otro |
| Solicitado por | Persona que solicitó el movimiento |
| No. de factura | Número de factura del proveedor |
| Boleta de ingreso a bodega | Número adicional, cuando la boleta física lo incluya |
| Observación | Información complementaria |

Posteriormente se agregarán las líneas de detalle, indicando producto,
cantidad y precio. Se podrán registrar tantas líneas como contenga la boleta.

<!-- CAPTURA: formulario de ingreso con la cabecera llena y dos líneas -->
![Registrar ingreso](capturas-admin/13-ingreso.png)

**Nota importante:** el folio se captura manualmente y deberá corresponder
siempre al número impreso en el talonario físico.

#### 2.6.2. Registro de una salida

Se deberá seleccionar la opción **+ Salida**. El encabezado incorpora tres
campos adicionales: **Entregado por**, **Cliente** y **Envío / recibo**.

#### 2.6.3. Impresión de la boleta

Desde la pantalla del folio se deberá utilizar la opción **Imprimir boleta
(PDF)**. El documento se genera en tamaño **media carta**, conforme al
talonario físico, para su impresión y firma.

<!-- CAPTURA: pantalla del detalle de un folio con el botón de PDF -->
![Detalle de un folio](capturas-admin/14-documento.png)

<!-- CAPTURA: el PDF generado, para comparar con la boleta de papel -->
![Boleta en PDF](capturas-admin/15-boleta-pdf.png)

#### 2.6.4. Devolución de equipo en préstamo o demostración

Cuando el tipo de movimiento registrado sea **Préstamo / Demo**, el sistema
mantiene el movimiento abierto hasta que el equipo sea devuelto. Para cerrarlo
se deberá utilizar la opción **Registrar devolución**, indicando la fecha y la
persona que realiza la devolución.

<!-- CAPTURA: registrar el regreso de un equipo en demo -->
![Devolución de un demo](capturas-admin/16-devolucion-demo.png)

---

### 2.7. Registro de Préstamos de Herramienta (FO-SE-066)

Corresponde al control de la herramienta de Bodega Técnica: quién la retira,
en qué estado sale y en qué estado se devuelve.

<!-- CAPTURA: lista de préstamos, con uno abierto y uno cerrado -->
![Préstamos de herramienta](capturas-admin/17-prestamos.png)

La opción **Imprimir hoja (PDF)** genera la hoja de control conforme al
formato FO-SE-066, para su resguardo físico en bodega.

#### 2.7.1. Registro de la salida

Mediante la opción **+ Registrar salida** se deberá indicar el activo, la
cantidad, la persona que lo solicita, quien lo entrega y el estado en que sale.

**Nota importante:** el sistema no permite prestar una cantidad mayor a la
disponible.

<!-- CAPTURA: formulario de salida de herramienta -->
![Salida de herramienta](capturas-admin/18-prestamo-salida.png)

#### 2.7.2. Registro del regreso

En el renglón del préstamo abierto se deberá utilizar la opción **Registrar
regreso**, indicando quien recibe el equipo y el estado en que se devuelve.

**Nota importante:** este es el momento en que corresponde clasificar una
herramienta como *Próximo a reemplazo* o *Mal estado*, cuando se devuelva con
desgaste o deterioro.

<!-- CAPTURA: formulario de regreso, mostrando el estado al salir y al volver -->
![Regreso de herramienta](capturas-admin/19-prestamo-regreso.png)

---

### 2.8. Reportes

El sistema genera cinco reportes, todos ellos exportables a Excel.

<!-- CAPTURA: índice de reportes con las tarjetas -->
![Índice de reportes](capturas-admin/20-reportes-indice.png)

| Reporte | Finalidad |
|---|---|
| Existencias y valorización | Cantidad y valor del inventario de cada bodega. Es el reporte que se contrasta contra el conteo físico |
| Alertas de stock | Productos que requieren reposición, ordenados por urgencia. Bodega Técnica se presenta en un apartado independiente |
| Movimientos por período | Entradas y salidas registradas entre dos fechas |
| Inventario de Bodega Técnica | Herramienta con su estado, existencia y cantidad prestada |
| Fuera de bodega | Equipo que se encuentra fuera de las instalaciones: préstamos y demostraciones |

<!-- CAPTURA: reporte de existencias con la tabla por bodega y el detalle -->
![Reporte de existencias](capturas-admin/21-reporte-existencias.png)

<!-- CAPTURA: reporte de alertas, mostrando la sección de Bodega Técnica -->
![Reporte de alertas](capturas-admin/22-reporte-alertas.png)

**Nota importante:** el archivo de Excel del reporte de alertas contiene dos
hojas, una por bodega. Los importes se exportan con formato numérico, por lo
que pueden sumarse y ordenarse sin necesidad de reformatear el archivo.

---

### 2.9. Administración de Usuarios

El acceso a este apartado corresponde exclusivamente al perfil de
Administrador.

<!-- CAPTURA: lista de usuarios con sus roles -->
![Usuarios del sistema](capturas-admin/23-usuarios.png)

#### 2.9.1. Alta de un usuario

Mediante la opción **+ Nuevo usuario** se deberán completar los campos
*Usuario para iniciar sesión*, *Rol en el sistema*, *Nombres*, *Apellidos* y la
contraseña.

Al marcar la casilla **Generar una contraseña segura**, el sistema genera la
contraseña y la presenta en pantalla.

**Nota importante:** la contraseña generada se muestra **una sola vez**. Se
deberá copiar en ese momento y entregarla personalmente al usuario.
Posteriormente solo podrá sustituirse por una nueva.

<!-- CAPTURA: formulario de nuevo usuario, con el selector de rol desplegado -->
![Nuevo usuario](capturas-admin/24-usuario-nuevo.png)

<!-- CAPTURA: la pantalla que muestra la contraseña generada -->
![Contraseña generada](capturas-admin/25-usuario-clave.png)

#### 2.9.2. Cambio de contraseña

Se realiza mediante la opción **Contraseña** del renglón correspondiente.
Aplica cuando el usuario ha olvidado su contraseña o cuando esta ha sido
comprometida.

#### 2.9.3. Baja de un usuario

**Nota importante:** cuando un colaborador deja la empresa se deberá desmarcar
la casilla **Puede iniciar sesión** el mismo día, en lugar de eliminar el
usuario. De este modo se impide el acceso y se conserva el registro de qué
movimientos fueron registrados por esa persona. La eliminación únicamente
procede cuando el usuario nunca llegó a utilizar el sistema.

---

### 2.10. Categorías

Las categorías permiten agrupar el catálogo y filtrarlo. Cada categoría indica
la cantidad de productos que la utilizan.

<!-- CAPTURA: lista de categorías con el conteo de productos -->
![Categorías](capturas-admin/26-categorias.png)

**Nota importante:** al eliminar una categoría en uso, los productos no se
eliminan: quedan sin categoría asignada y podrá asignárseles otra
posteriormente.

---

### 2.11. Proveedores

Registra las empresas a las que se realizan las compras. Cada proveedor
incorpora contacto, teléfono y origen:

- **Local:** el producto se adquiere en el país.
- **Extranjero:** el producto es importado y su pedido requiere mayor
  anticipación.
- **Sin clasificar:** el origen aún no ha sido determinado.

<!-- CAPTURA: lista de proveedores con el filtro de origen -->
![Proveedores](capturas-admin/27-proveedores.png)

El origen se refleja en el reporte de alertas de stock: los productos de
procedencia extranjera se identifican de forma diferenciada, a efecto de
considerar el tiempo adicional que requiere su reposición.

**Nota importante:** la pantalla indica cuántos proveedores permanecen sin
clasificar. Se recomienda completar dicha clasificación, ya que de ella
depende la utilidad de la advertencia anterior.

Al igual que con las categorías, la eliminación de un proveedor no elimina sus
productos.

---

### 2.12. Carga Masiva desde Excel

Permite incorporar múltiples productos a partir de los archivos **FO-SE-053**
(Bodega 1 y 2) o **FO-SE-065** (Bodega Técnica). El proceso consta de tres
pasos:

1. **Carga del archivo** y selección de la hoja correspondiente al mes que se
   desea importar.
2. **Asignación de columnas:** confirmar qué columna del archivo corresponde a
   cada dato. El sistema propone una asignación automática que deberá
   revisarse.
3. **Confirmación:** el sistema presenta una vista previa antes de registrar
   la información.

<!-- CAPTURA: paso 1, subir el archivo y elegir la hoja -->
![Carga masiva — subir](capturas-admin/28-carga-subir.png)

<!-- CAPTURA: paso 2, mapeo de columnas con la vista previa -->
![Carga masiva — mapear](capturas-admin/29-carga-mapear.png)

En Bodega 1 y 2 el código interno no se asigna, ya que el sistema lo genera.
En Bodega Técnica el código sí se importa tal como aparece en el archivo, por
tratarse de una nomenclatura asignada por la empresa.

Los productos existentes se actualizan; los nuevos se registran con su
cantidad como saldo inicial.

**Nota importante:** se deberá generar un respaldo de la base de datos antes
de ejecutar una carga masiva. Ante un error en la asignación de columnas,
restaurar el respaldo resulta considerablemente más rápido que corregir los
registros de forma individual.

---

### 2.13. Respaldos y Mantenimiento

Las siguientes instrucciones se ejecutan desde **PowerShell**, en la
computadora servidor, dentro de la carpeta del proyecto.

#### 2.13.1. Generación de respaldos

```powershell
.\scripts\respaldo.ps1
```

Genera un archivo en la carpeta `respaldos\` identificado con la fecha, y
elimina automáticamente los que superen los 30 días de antigüedad.

**Nota importante:** se deberá generar un respaldo antes de cualquier
operación de importancia: carga masiva, limpieza de registros o actualización
del sistema.

#### 2.13.2. Restauración

```powershell
.\scripts\restaurar.ps1                                     # listar los disponibles
.\scripts\restaurar.ps1 -Archivo respaldos\bodega_....dump  # restaurar
.\scripts\restaurar.ps1 -Archivo respaldos\... -SoloProbar  # verificar sin aplicar
```

El sistema solicita escribir la palabra `RESTAURAR` en mayúsculas antes de
proceder.

**Nota importante:** la restauración reemplaza la totalidad del contenido
actual de la base de datos.

#### 2.13.3. Verificación de existencias

```powershell
docker compose exec web python manage.py recalcular_stock --solo-revisar
```

Informa las diferencias entre la existencia registrada y el historial de
movimientos, sin modificar información. Sin el parámetro `--solo-revisar`, el
sistema corrige las diferencias recalculando desde el historial.

#### 2.13.4. Cambio de contraseña desde la terminal

```powershell
docker compose exec web python manage.py cambiar_clave admin --generar
```

Aplica cuando no resulta posible acceder al sistema para realizar el cambio
desde la pantalla correspondiente.

#### 2.13.5. Limpieza de registros

```powershell
docker compose exec web python manage.py limpiar_catalogo --que todo
docker compose exec web python manage.py limpiar_historial_tecnica
```

Sin el parámetro `--si-estoy-seguro`, ambas instrucciones únicamente informan
qué información se eliminaría.

- `limpiar_catalogo` elimina productos e historial.
- `limpiar_historial_tecnica` elimina únicamente el historial de Bodega
  Técnica y deja las existencias en cero, conservando el catálogo.

**Nota importante:** ambas operaciones son irreversibles. Se deberá generar un
respaldo previamente.

---

### 2.14. Solución de Problemas Frecuentes

| Situación | Acción a seguir |
|---|---|
| Un equipo no logra abrir el sistema | Verificar que se encuentre en la red de la oficina y que la dirección sea `192.168.1.200`. Consultar `PUESTA_EN_MARCHA.md` |
| El sistema indica que no se cuenta con permiso | El perfil del usuario no tiene acceso a esa pantalla. Consultar el apartado 2.2 |
| La existencia no coincide con el conteo físico | Ejecutar `recalcular_stock --solo-revisar`. De existir diferencias, registrar el ajuste como movimiento |
| El sistema no permite eliminar un producto | El producto registra movimientos. Se deberá desmarcar la casilla **Activo** |
| El sistema no permite guardar los umbrales | Deberán cumplir la relación crítico ≤ alerta ≤ óptimo |
| Un colaborador deja la empresa | Desmarcar **Puede iniciar sesión** el mismo día |

---

## 3. HISTORIAL DE REVISIONES

| Revisión No. | Fecha de Emisión | Descripción de la Revisión o Actualización | Aprobado Por |
|:---:|:---:|---|---|
| 01 | *(pendiente)* | Emisión inicial del instructivo para el perfil de Administrador | Gerente Técnico |

---

## Anexo — Capturas de pantalla

Las imágenes se guardan en la carpeta `capturas-admin/`, junto a este archivo,
con el nombre indicado en cada bloque. La descripción de lo que debe mostrar
cada una se encuentra en `capturas-admin/LEEME.txt`.

Todas se toman iniciando sesión con un usuario de perfil **Administrador**,
con la ventana del navegador a 1600 píxeles de ancho o más.
