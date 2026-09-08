# INSTRUCTIVO SISTEMA DE INVENTARIO — PERFIL OPERADOR DE BODEGA

**IT-006**

> **Borrador de trabajo.** De aquí se copia el texto hacia la plantilla del
> Sistema de Gestión, que ya trae el encabezado, el control documental y el
> pie de página.
>
> El código IT-006 es una propuesta; deberá confirmarse con la numeración que
> lleve el Sistema de Gestión.

---

## Datos para el control documental

| Campo | Valor |
|---|---|
| Código | IT-006 |
| Versión | 01 |
| Elaborado por | Proyectos |
| Revisado por | Gerente Administrativo |
| Aprobado por | Gerente Técnico |

Encabezado de cada página: **SOLUCIONES EXACTAS, S.A.** ·
*Instructivo Sistema de Inventario — Operador de Bodega* · Código IT-006 ·
Versión 01 · Página N de M.

---

## 1. OBJETIVO

El presente instructivo tiene como objetivo establecer una guía clara y de
fácil comprensión para el registro de los movimientos de bodega en el Sistema
de Control de Bodega, por parte del personal con perfil de **Operador de
Bodega**.

A través de este documento se busca estandarizar el registro de entradas,
salidas, préstamos de herramienta y devoluciones, de manera que cada
movimiento quede documentado con su respaldo correspondiente y la existencia
que muestra el sistema coincida en todo momento con la bodega física.

El sistema conserva los mismos formatos físicos de registro que se utilizan
actualmente: **FO-SE-013** para ingresos, **FO-SE-012** para salidas y
**FO-SE-066** para préstamos de herramienta. Lo que cambia es que, además de
llenarse en papel, el movimiento queda registrado en el sistema.

---

## 2. CONTENIDO

### 2.1. Acceso al Sistema

El sistema se utiliza desde el navegador de cualquier equipo conectado a la
red interna de la empresa, sea computadora, tableta o teléfono.

Se deberá ingresar a la siguiente dirección:

```
http://192.168.1.200:8000
```

**Nota importante:** el sistema **no requiere conexión a internet**. Al residir
en una computadora de la oficina, permanece disponible aun cuando el servicio
de internet se encuentre interrumpido.

El nombre de usuario no distingue entre mayúsculas y minúsculas; la contraseña
sí las distingue.

**Nota importante:** el usuario y la contraseña son personales e
intransferibles. El sistema registra qué usuario capturó cada movimiento, por
lo que no deberán compartirse con otras personas.

<!-- CAPTURA: pantalla de inicio de sesión -->
![Pantalla de inicio de sesión](capturas-operador/01-login.png)

---

### 2.2. Alcance del Perfil de Operador de Bodega

El perfil de Operador de Bodega comprende las siguientes funciones:

| Función | Apartado |
|---|---|
| Consultar los catálogos de ambas bodegas | 2.4 |
| Registrar ingresos a bodega (FO-SE-013) | 2.5 |
| Registrar salidas de bodega (FO-SE-012) | 2.6 |
| Registrar la devolución de equipo prestado o en demostración | 2.7 |
| Registrar préstamos de herramienta (FO-SE-066) | 2.8 |
| Registrar el regreso de herramienta prestada | 2.9 |
| Registrar la baja de existencia en Bodega Técnica | 2.10 |

Al iniciar sesión, el menú lateral presenta cinco opciones: **Resumen**,
**Bodega 1 y 2**, **Bodega Técnica**, **Entradas y salidas** y **Préstamos de
herramienta**.

<!-- CAPTURA: barra lateral del operador, con sus cinco opciones -->
![Menú del operador](capturas-operador/03-navegacion.png)

**Nota importante:** el sistema cuenta con otras pantallas que corresponden a
perfiles distintos y que no forman parte de las funciones del Operador de
Bodega. Al intentar acceder a ellas, el sistema presentará el mensaje *"No
tienes permiso para ver esta pantalla"*. **Esto no constituye un error del
sistema ni una falla del usuario**, sino la asignación normal de funciones.

---

### 2.3. Pantalla de Resumen

Constituye la primera pantalla que se presenta al iniciar sesión. Permite
identificar rápidamente qué requiere atención.

<!-- CAPTURA: Resumen tal como lo ve el operador -->
![Pantalla de resumen](capturas-operador/02-resumen.png)

En la parte superior se presentan tres indicadores:

| Indicador | Descripción |
|---|---|
| Artículos activos (Ventas) | Cantidad de productos registrados en el catálogo de Bodega 1 y 2 |
| Activos en Bodega Técnica | Cantidad de herramientas y equipo registrados |
| Préstamos / demos abiertos | Equipo que salió de bodega y aún no ha sido devuelto |

En la parte inferior se presentan tres paneles:

- **Alertas de stock — Bodega 1 y 2:** los productos con menor existencia,
  ordenados por urgencia. Al seleccionar cualquiera de ellos se accede a su
  ficha.
- **Alertas de stock — Bodega Técnica:** el mismo listado para la herramienta.
- **Activos técnicos prestados:** qué equipo se encuentra fuera de bodega, con
  quién y desde qué fecha.

**Nota importante:** los paneles de alertas indican qué productos deberán
reportarse para su reposición. El operador no realiza la compra; su función es
informar al encargado cuando un producto aparezca en nivel crítico.

---

### 2.4. Consulta de los Catálogos

El operador consulta ambos catálogos pero no los modifica: el alta y la
corrección de productos corresponden a otro perfil.

<!-- CAPTURA: catálogo de Bodega 1 y 2 visto por el operador -->
![Catálogo de Bodega 1 y 2](capturas-operador/04-catalogo-ventas.png)

El buscador localiza productos por **código interno o nombre**. Mediante la
opción **Filtros** se pueden combinar bodega, proveedor, nivel de stock,
estado y rango de precio.

Al seleccionar cualquier fila se accede a la ficha del producto, donde se
presentan sus datos, su existencia y su nivel de reposición.

<!-- CAPTURA: ficha de un artículo -->
![Ficha de un artículo](capturas-operador/05-articulo-ficha.png)

Desde la ficha, el enlace **Ver kardex completo** presenta la totalidad de los
movimientos del producto —cada entrada y cada salida— con su fecha, número de
boleta y el usuario que los registró.

**Nota importante:** el kardex es la herramienta a utilizar cuando la
existencia que muestra el sistema no coincide con el conteo físico. Permite
identificar en qué movimiento se originó la diferencia.

<!-- CAPTURA: kardex de un artículo con varios movimientos -->
![Kardex de un artículo](capturas-operador/06-kardex.png)

El catálogo de Bodega Técnica funciona de la misma forma. En él, cada activo
presenta además su **estado** (Buen estado, Próximo a reemplazo o Mal estado) y
su **disponibilidad**, indicando cuántas unidades se encuentran prestadas y
cuántas permanecen en bodega.

<!-- CAPTURA: catálogo de Bodega Técnica -->
![Catálogo de Bodega Técnica](capturas-operador/07-catalogo-tecnica.png)

Desde la ficha de un activo que cuente con existencia se presentan las dos
acciones que el operador realiza sobre él: **Registrar salida**, para
entregarlo en préstamo (apartado 2.8), y **Dar de baja** (apartado 2.10).

<!-- CAPTURA: ficha de un activo con existencia, mostrando sus dos botones -->
![Ficha de un activo](capturas-operador/08-activo-ficha.png)

---

### 2.5. Registro de un Ingreso a Bodega (FO-SE-013)

Se realiza desde **Entradas y salidas**, mediante la opción **+ Ingreso**.

<!-- CAPTURA: pantalla de Entradas y salidas -->
![Entradas y salidas](capturas-operador/09-movimientos.png)

Una boleta puede contener varios productos. El sistema reproduce esa
estructura: primero se captura el encabezado, que corresponde a la parte
superior de la boleta, y a continuación las líneas de detalle.

#### 2.5.1. Encabezado del documento

| Campo | Contenido |
|---|---|
| Número de boleta | El que trae impreso el talonario de papel |
| Fecha del movimiento | Se presenta la fecha y hora actuales |
| Tipo de movimiento | Venta, Préstamo/Demo, Repuestos o Materiales/Otro |
| Solicitado por | Persona que solicitó el ingreso |
| No. de factura | Número de factura del proveedor |
| Observación | Información complementaria |

**Nota importante:** el número de boleta deberá corresponder **siempre** al que
impreso en el talonario físico. El sistema propone el siguiente número de la
serie únicamente como referencia; cuando el talonario vaya en otra numeración,
el valor propuesto deberá corregirse.

**Nota importante:** cuando se digite una boleta de días anteriores, se deberá
modificar la fecha para que corresponda a la del movimiento real y no a la del
día en que se captura.

<!-- CAPTURA: encabezado del formulario de ingreso, lleno -->
![Encabezado de un ingreso](capturas-operador/10-ingreso.png)

#### 2.5.2. Líneas de detalle

Para cada producto de la boleta se deberá indicar el **producto**, la
**cantidad** y el **precio**. El producto se localiza escribiendo parte de su
código o de su nombre; el sistema presenta las coincidencias para seleccionar
la correcta, y debajo de la línea muestra su bodega, su existencia actual y su
marca, para confirmar que se eligió el correcto.

Se podrán agregar tantas líneas como contenga la boleta física, ya sea con la
opción **+ Agregar línea** o presionando Enter sobre el campo de cantidad.

**Nota importante:** al seleccionar el producto, el sistema propone el precio
que este tiene en el catálogo, que es el caso normal. **Cuando la factura del
proveedor traiga otro precio, deberá escribirse el de la factura**: es el que
queda guardado en el movimiento y el que aparecerá impreso en la boleta.

**Nota importante:** el precio capturado aquí queda pegado a este movimiento y
no cambia después. Registrar un ingreso a un precio distinto **no modifica el
precio del catálogo**: si el producto subió de precio de forma permanente,
deberá reportarse al encargado para que actualice la ficha.

<!-- CAPTURA: líneas de detalle con dos productos capturados -->
![Líneas de un ingreso](capturas-operador/11-ingreso-lineas.png)

**Nota importante:** la existencia se calcula automáticamente a partir de los
movimientos registrados. No existe ninguna pantalla en la que la cantidad se
escriba directamente, y no deberá buscarse: la única forma de que un producto
tenga existencia es que se le registre su ingreso.

#### 2.5.3. Impresión de la boleta

Una vez guardado, desde la pantalla de la boleta se deberá utilizar la opción
**Imprimir boleta (PDF)**. El documento se genera en tamaño **media carta**,
conforme al talonario físico, para su impresión y firma.

<!-- CAPTURA: detalle de una boleta, con el botón de PDF -->
![Detalle de una boleta](capturas-operador/12-documento.png)

<!-- CAPTURA: la boleta en PDF -->
![Boleta en PDF](capturas-operador/13-boleta-pdf.png)

---

### 2.6. Registro de una Salida de Bodega (FO-SE-012)

Se realiza mediante la opción **+ Salida**. El procedimiento es el mismo que
el del ingreso, con tres campos adicionales en el encabezado:

| Campo | Contenido |
|---|---|
| Entregado por | Persona que entrega el producto |
| Cliente | Cliente al que se destina |
| Envío / recibo | Número de envío o recibo, cuando aplique |

<!-- CAPTURA: encabezado del formulario de salida -->
![Registrar una salida](capturas-operador/14-salida.png)

**Nota importante:** el sistema no permite registrar una salida por una
cantidad mayor a la existencia disponible. Cuando esto ocurra, deberá
verificarse el kardex del producto (apartado 2.4) antes de continuar, ya que
indica que la bodega física y el sistema no coinciden.

---

### 2.7. Devolución de Equipo en Préstamo o Demostración

Cuando una salida se registre con el tipo de movimiento **Préstamo / Demo**,
el equipo no se considera vendido: se espera su regreso. El sistema mantiene
ese movimiento abierto hasta que la devolución sea registrada.

Para cerrarlo se deberá utilizar la opción **Registrar devolución** e indicar:

| Campo | Contenido |
|---|---|
| Fecha de devolución | Fecha en que el equipo regresó |
| Devuelto por | Persona que realiza la devolución |
| Observación | Condición en que regresó el equipo, cuando corresponda |

<!-- CAPTURA: formulario de devolución de un demo -->
![Devolución de un demo](capturas-operador/15-devolucion-demo.png)

**Nota importante:** mientras la devolución no se registre, el equipo continúa
contabilizado como fuera de bodega en la pantalla de resumen.

---

### 2.8. Registro de un Préstamo de Herramienta (FO-SE-066)

Corresponde a la herramienta de Bodega Técnica que se entrega al personal
técnico. Se realiza desde **Préstamos de herramienta**, mediante la opción
**+ Registrar salida**.

<!-- CAPTURA: pantalla de Préstamos de herramienta -->
![Préstamos de herramienta](capturas-operador/16-prestamos.png)

| Campo | Contenido |
|---|---|
| Herramienta | Se localiza escribiendo su código o su nombre |
| Solicitante (quién se lo lleva) | Persona que retira la herramienta |
| Entregado por | Persona que la entrega |
| Fecha de salida | Fecha y hora de la entrega |
| Estado con el que sale | Buen estado, Próximo a reemplazo o Mal estado |
| Cantidad | Número de unidades que se entregan |
| Observación | Información complementaria |

<!-- CAPTURA: formulario de salida de herramienta -->
![Salida de herramienta](capturas-operador/17-prestamo-salida.png)

**Nota importante:** el sistema no permite prestar una cantidad mayor a la
disponible. Si una herramienta se encuentra prestada en su totalidad, no
aparecerá como disponible hasta que se registre su regreso.

**Nota importante:** el préstamo **no disminuye la existencia** de la bodega.
La herramienta prestada continúa perteneciendo a Bodega Técnica y únicamente
se encuentra fuera de las instalaciones de forma temporal.

La opción **Imprimir hoja (PDF)** genera la hoja de control conforme al
formato FO-SE-066, para su resguardo físico en bodega.

---

### 2.9. Registro del Regreso de una Herramienta

En el renglón del préstamo abierto se deberá utilizar la opción **Registrar
regreso** e indicar:

| Campo | Contenido |
|---|---|
| Fecha de regreso | Fecha y hora en que la herramienta fue devuelta |
| Recibido por | Persona que la recibe en bodega |
| Estado al regresar | Condición en la que se devuelve |
| Observación | Detalle del daño o desgaste, cuando corresponda |

<!-- CAPTURA: formulario de regreso, mostrando el estado al salir y al volver -->
![Regreso de herramienta](capturas-operador/18-prestamo-regreso.png)

**Nota importante:** este es el momento en que corresponde clasificar una
herramienta como **Próximo a reemplazo** cuando se devuelva con desgaste, o
como **Mal estado** cuando ya no se encuentre en condiciones de uso. Dicha
clasificación es la que permite programar la compra de reposición con
anticipación, por lo que no deberá omitirse.

---

### 2.10. Baja de Existencia en Bodega Técnica

La baja constituye **el único movimiento que disminuye la existencia** de
Bodega Técnica, y se aplica cuando una herramienta o insumo se dañó, se
extravió o se consumió por completo.

Se registra desde la ficha del activo, mediante la opción **Dar de baja**:

| Campo | Contenido |
|---|---|
| ¿Cuántas se dan de baja? | Número de unidades que salen de la existencia |
| Motivo | Dañado, extraviado, consumido u otro |
| Fecha | Fecha en que ocurrió |
| Observación | Detalle de lo sucedido |

<!-- CAPTURA: pantalla de dar de baja, con cantidad y motivo -->
![Dar de baja](capturas-operador/19-dar-de-baja.png)

**Nota importante:** la baja no genera boleta física. Es un registro interno
que documenta por qué disminuyó la existencia.

**Nota importante:** la opción **Dar de baja** se presenta únicamente cuando
el activo cuenta con existencia disponible. Si no aparece, significa que el
activo se encuentra en cero: la propia pantalla indica si se dio de baja la
totalidad o si aún no se le ha registrado ningún ingreso.

**Nota importante:** dar de baja no elimina el activo. La herramienta
permanece en el catálogo con su historial completo, y si posteriormente se
adquiere una nueva unidad, bastará con registrar su ingreso.

---

### 2.11. Solución de Problemas Frecuentes

| Situación | Acción a seguir |
|---|---|
| El equipo no logra abrir el sistema | Verificar que se encuentre conectado a la red de la oficina. El sistema no depende del servicio de internet |
| El sistema indica *"No tienes permiso para ver esta pantalla"* | Dicha pantalla corresponde a otro perfil. No se trata de un error |
| El sistema no permite registrar una salida por falta de existencia | Consultar el kardex del producto (apartado 2.4) y reportar la diferencia al encargado |
| La existencia no coincide con el conteo físico | Consultar el kardex e informar al encargado. **No deberá corregirse registrando movimientos que no ocurrieron** |
| No aparece la opción **Dar de baja** | El activo se encuentra en existencia cero |
| Se registró un movimiento con datos incorrectos | Informar al encargado. El operador no elimina movimientos, ya que el historial es el respaldo de la existencia |

---

### 2.12. Consideraciones Generales

1. **El número de boleta se toma siempre del talonario físico.** Es lo que permite
   localizar la boleta de papel a partir del registro del sistema.
2. **Cada movimiento se registra el mismo día en que ocurre.** Un registro
   atrasado produce diferencias entre la bodega física y el sistema.
3. **La existencia nunca se escribe directamente.** Se obtiene de los
   movimientos registrados.
4. **El estado de la herramienta se clasifica al momento del regreso**, no
   posteriormente.
5. **Las diferencias se reportan, no se corrigen.** Registrar un movimiento
   que no ocurrió para cuadrar una diferencia elimina el respaldo del
   inventario.

---

## 3. HISTORIAL DE REVISIONES

| Revisión No. | Fecha de Emisión | Descripción de la Revisión o Actualización | Aprobado Por |
|:---:|:---:|---|---|
| 01 | *(pendiente)* | Emisión inicial del instructivo para el perfil de Operador de Bodega | Gerente Técnico |

---

## Anexo — Capturas de pantalla

Las imágenes se guardan en la carpeta `capturas-operador/`, junto a este
archivo, con el nombre indicado en cada bloque. La descripción de lo que debe
mostrar cada una se encuentra en `capturas-operador/LEEME.txt`.

**Nota importante:** todas las capturas deberán tomarse iniciando sesión con
un usuario de perfil **Operador de Bodega**. Si se toman con un perfil
distinto, las imágenes mostrarán opciones que el operador no tiene, lo cual
contradice el propósito de este documento.
