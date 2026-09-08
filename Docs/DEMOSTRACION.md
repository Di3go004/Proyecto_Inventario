# Guion de la demostración — Sistema de Control de Bodega

**Duración estimada:** 20–25 minutos · **Preguntas:** 10 minutos aparte

Esta guía es para vos, no para entregar. Trae los pasos exactos, en orden, y
qué decir en cada uno.

> ⚠️ **La demostración corre sobre la copia de pruebas**, en
> <http://127.0.0.1:8001>. Los datos que se muestran son de prueba y nada de
> lo que se haga en vivo toca el sistema que usa la empresa.

---

## Antes de empezar

### 1. Comprobar que la copia de pruebas está arriba

```powershell
cd ...\Proyecto_Inventario_dev
docker compose ps          # los dos contenedores en "running"
```

Si no lo están: `docker compose up -d` y esperar unos segundos.

### 2. Dejar el punto de partida limpio

Si ya ensayaste, volvé al escenario original antes de la presentación real:

```powershell
cd ...\Proyecto_Inventario_dev
.\scripts\restaurar.ps1 -Archivo respaldos\DEMO-punto-de-partida.dump
```

Pide escribir `RESTAURAR` en mayúsculas. Verificá que la línea diga
`inventario_dev-db-1` antes de confirmar.

### 3. Preparar el navegador

- Ventana **maximizada**, y con zoom al 100 % (`Ctrl+0`)
- **Cerrá las pestañas de más.** La barra de marcadores también, si se puede
- Tené **tres pestañas** listas, para no perder tiempo escribiendo direcciones:
  1. `http://127.0.0.1:8001` — la vas a usar como administrador
  2. Una ventana **de incógnito** con la misma dirección — para el operador
  3. El PDF de una boleta física escaneada, o la boleta de papel a mano

> **Por qué de incógnito:** el navegador guarda una sola sesión por sitio. Sin
> una ventana aparte, entrar como operador te saca de la sesión de
> administrador y perdés el hilo.

### 4. Usuarios de la demostración

Todos con la misma contraseña, para no equivocarte en vivo:

| Usuario | Rol | Para mostrar |
|---|---|---|
| `admin` | Administrador | Todo el sistema |
| `servicio` | Operador de bodega | Lo que ve quien mueve bodega |
| `contabilidad` | Contabilidad | Consulta e impresión |

**Contraseña:** `Demo2026.SE`

> ⚠️ Esta contraseña vive **solo en la copia de pruebas**, que además solo se
> alcanza desde esta computadora. En el sistema de la empresa cada persona
> tiene la suya y no se comparte.

### 5. Tené a la vista

- Los dos Excel: `01 FO-SE-053` y `FO-SE-065`
- Un talonario de boletas **FO-SE-013** en papel

Sirven para el arranque y para el momento más convincente de la demostración.

---

## El arco de la presentación

| # | Bloque | Minutos |
|---|---|:---:|
| 1 | De dónde venimos | 2 |
| 2 | El catálogo | 3 |
| 3 | Registrar un ingreso e imprimir la boleta | 5 |
| 4 | Trazabilidad: quién, cuándo y por qué | 3 |
| 5 | Bodega Técnica: préstamo y estado | 4 |
| 6 | Reportes y valorización | 3 |
| 7 | Cada quien ve lo suyo | 3 |
| 8 | Cierre | 2 |

---

## 1 · De dónde venimos *(2 min)*

**Abrí los dos Excel en pantalla.** No los expliques, solo mostralos y dejá que
se vean: una hoja por mes, columnas repetidas por semana, celdas de colores.

> «Hoy el inventario se lleva en estos dos archivos. Cada mes se copia la hoja
> anterior y se empieza de nuevo, y cada semana se anota a mano lo que entró y
> lo que salió en una columna distinta.
>
> Funciona, pero tiene tres problemas. Primero: si alguien se equivoca en una
> celda, no hay forma de saber quién fue ni cuándo. Segundo: para saber cuánto
> vale el inventario hay que sumar a mano. Y tercero: solo lo puede tener
> abierto una persona a la vez.
>
> Lo que les voy a mostrar es lo mismo que hacen hoy, pero donde el sistema se
> encarga de las cuentas y guarda quién hizo cada cosa.»

**Cerrá los Excel** y abrí el sistema.

---

## 2 · El catálogo *(3 min)*

### Pasos

1. Entrá como **`admin`**
2. Quedás en el **Resumen**. Dejalo unos segundos a la vista
3. **Bodega 1 y 2** en el menú
4. Escribí `balanza` en el buscador → **Buscar**
5. Abrí **Filtros** y elegí *Nivel de stock: Crítico* → **Aplicar**

### Qué decir

> «Esta es la primera pantalla al entrar. En diez segundos se ve cuánto hay en
> cada bodega, cuánto vale, qué está por acabarse y qué anda fuera prestado.»

*(en el catálogo)*

> «Acá está el catálogo completo: **185 productos** en Bodega 1 y 2, y **252**
> en Bodega Técnica. Se buscan por código o por nombre…»

*(al aplicar el filtro)*

> «…y se pueden combinar filtros. Esto de aquí es lo que hay que reponer: son
> los que están por debajo del mínimo que la empresa definió para cada
> producto.»

**No entres a editar un producto todavía.** Eso lo vas a hacer más adelante,
cuando muestres los roles.

---

## 3 · Registrar un ingreso e imprimir la boleta *(5 min)*

Este es el bloque más importante. **Tené la boleta de papel en la mano.**

### Pasos

1. **Entradas y salidas** → **+ Ingreso**
2. En el buscador de producto escribí `balanza`, elegí uno de la lista
3. Cantidad: `10`
4. **Fijate en el precio**: se llenó solo con el del catálogo. Cambialo a otro
   valor, por ejemplo `1250`
5. **+ Agregar línea** y capturá un segundo producto, cantidad `4`
6. Abajo: **Número de boleta** → escribí el número que tenga la boleta de papel
   que llevás. *Solicitado por*: tu nombre. *No. de factura*: cualquiera
7. **Guardar**
8. En el mensaje verde, entrá a la boleta que se acaba de crear
9. **Imprimir boleta (PDF)** → se abre en otra pestaña

### Qué decir

*(al capturar)*

> «Registrar una entrada es lo mismo que llenar la boleta de papel: se escribe
> el número que trae el talonario, quién la solicitó, la factura, y luego los
> productos con su cantidad.
>
> El precio lo propone del catálogo, pero se puede corregir: si la factura del
> proveedor trae otro precio, se escribe el de la factura. **Ese precio queda
> guardado en este movimiento y no cambia nunca más**, aunque después el
> producto suba de precio.»

*(al abrir el PDF — levantá la boleta de papel al lado de la pantalla)*

> «Y esta es la misma boleta. Media carta, con el mismo formato, el mismo
> encabezado y los mismos espacios de firma. Se imprime, se firma y se archiva
> igual que siempre.
>
> La diferencia es que ahora, además, quedó registrada.»

> **Este es el momento de la demostración.** No lo apures: dejá que comparen la
> pantalla con el papel.

---

## 4 · Trazabilidad: quién, cuándo y por qué *(3 min)*

### Pasos

1. **Entradas y salidas** — mostrá la lista con el movimiento recién creado
   arriba
2. Señalá la columna **Registrado por** en alguna fila de *Ajuste* o *Baja*
3. **Bodega 1 y 2** → abrí el producto que acabás de ingresar
4. **Ver kardex completo**

### Qué decir

> «Todo movimiento queda con su número de boleta, su fecha y **quién lo
> registró**. Los ajustes y las bajas, que no llevan boleta de papel, muestran
> el usuario que los hizo — para esos es el único respaldo que existe.»

*(en el kardex)*

> «Y cada producto tiene su historial completo: cada entrada, cada salida, con
> su fecha y su responsable.
>
> Esto responde la pregunta que hoy no se puede contestar: *¿por qué este
> producto tiene esta cantidad?* Acá está, movimiento por movimiento. **La
> existencia no se escribe a mano en ninguna pantalla**: sale de sumar este
> historial. Por eso no se puede descuadrar sin dejar rastro.»

---

## 5 · Bodega Técnica: préstamo y estado *(4 min)*

### Pasos

1. **Préstamos de herramienta** — mostrá la lista; hay uno **abierto**
2. En ese renglón: **Registrar regreso**
3. Fecha: la de hoy. *Recibido por*: tu nombre
4. **Estado al regresar**: elegí **Próximo a reemplazo**
5. Observación: «Volvió con desgaste en el mango»
6. **Guardar**
7. **Bodega Técnica** → buscá esa herramienta y mostrá su chip ámbar

### Qué decir

> «Bodega Técnica es distinta: la herramienta no se vende, se presta y
> se devuelve. Acá se registra quién se la llevó, cuándo, y en qué estado
> salió.»

*(al registrar el regreso)*

> «Y cuando vuelve se anota en qué estado volvió. Hay tres: buen estado,
> **próximo a reemplazo** y mal estado.
>
> El de en medio es el que más sirve. Es el aviso de que la herramienta todavía
> funciona pero está gastada, y que hay que ir comprando la de repuesto **antes**
> de quedarse sin ella. Hoy eso queda en la cabeza de quien la usó.»

*(en el catálogo, señalando el chip)*

> «Ahí queda marcada, y sale en el reporte para que compras la vea.»

> **Nota:** prestar una herramienta **no** baja su existencia — sigue siendo de
> la bodega. Lo único que la baja es dar de baja algo que se dañó, se perdió o
> se consumió. Si alguien pregunta, esa es la respuesta.

---

## 6 · Reportes y valorización *(3 min)*

### Pasos

1. **Reportes** en el menú — mostrá las cinco tarjetas
2. **Existencias y valorización**
3. Señalá la tabla por bodega, y abajo el bloque de **Bodega Técnica**
4. **Descargar Excel** → abrilo
5. Volvé y entrá a **Alertas de stock**; bajá hasta la sección de Bodega Técnica

### Qué decir

> «Son cinco reportes y todos se descargan a Excel.»

*(en existencias)*

> «Este dice cuánto hay y cuánto vale, por bodega. Es el que se cruza contra el
> conteo físico. Hoy este número hay que sacarlo sumando a mano.»

*(al abrir el Excel)*

> «Y sale listo para trabajar: los montos son números, no texto, así que se
> pueden sumar y ordenar sin reformatear nada.»

*(en alertas)*

> «Este es el de compras: qué hay que reponer, lo más urgente primero. Bodega
> Técnica va en su propia sección porque lleva otras columnas. Y si el
> proveedor es del extranjero, sale marcado — para pedirlo con más
> anticipación.»

---

## 7 · Cada quien ve lo suyo *(3 min)*

**Pasate a la ventana de incógnito** y entrá como **`servicio`**.

### Pasos

1. Poné las **dos ventanas lado a lado**, si la pantalla lo permite
2. Señalá el menú lateral del operador: cinco opciones
3. Señalá las tarjetas del Resumen: **no hay valorización**
4. Entrá a **Bodega 1 y 2**: no aparece *+ Nuevo artículo* ni *Carga masiva*
5. En la barra de direcciones del operador, escribí a mano:
   `127.0.0.1:8001/reportes/` → sale la pantalla de permiso denegado

### Qué decir

> «El sistema tiene cuatro perfiles, y cada uno ve solamente lo suyo.
>
> Este es el operador de bodega. Registra entradas, salidas y préstamos —que es
> su trabajo— pero **no ve cuánto vale el inventario ni entra a los reportes**.
> Esa información es de la empresa y no le corresponde.
>
> Tampoco puede modificar el catálogo: consulta los productos, pero darlos de
> alta o cambiarles el precio es de administración.»

*(al escribir la dirección a mano)*

> «Y no es que solo se le esconda el botón: aunque escriba la dirección
> directamente, el sistema no lo deja entrar.»

*(volvé a la ventana del administrador)*

> «Contabilidad, en cambio, sí entra a los reportes y a la valorización, pero
> no modifica nada: consulta e imprime.»

---

## 8 · Cierre *(2 min)*

> «Resumiendo: el sistema hace lo mismo que hoy hacen en los Excel, con tres
> diferencias.
>
> **Primera:** las boletas siguen siendo de papel y se siguen firmando, pero
> ahora quedan registradas y se pueden reimprimir exactamente iguales.
>
> **Segunda:** cada movimiento tiene responsable, y la existencia se calcula
> sola desde el historial. No hay forma de que se descuadre en silencio.
>
> **Tercera:** varias personas pueden usarlo a la vez, cada una con lo que le
> toca.
>
> Corre en una computadora de la oficina y **no necesita internet**: si se cae
> el servicio, sigue funcionando.»

### Lo que conviene decir vos, antes de que lo pregunten

- **Está en pruebas todavía.** Lo que vieron es la copia de pruebas; el
  inventario real ya está cargado pero falta terminar de registrarle las
  cantidades.
- **Los manuales están escritos** —uno para administración y otro para
  operación, en el formato del sistema de gestión— y solo les faltan las
  capturas.
- **Hay respaldo automático de la base** *(o: está pendiente programarlo, según
  cómo esté ese día)*.

---

## Preguntas que probablemente les hagan

| Pregunta | Respuesta corta |
|---|---|
| ¿Y si se cae el internet? | No lo usa. Vive en una computadora de la oficina, en la red interna |
| ¿Y si se daña esa computadora? | Hay respaldos de la base con fecha. Se restaura en otra máquina |
| ¿Se pueden seguir usando las boletas de papel? | Sí, y se deben. El sistema las imprime en el mismo formato |
| ¿Alguien puede borrar un movimiento para cuadrar algo? | No. Un producto con movimientos no se puede eliminar, y cada movimiento queda con su responsable |
| ¿Se puede entrar desde el celular? | Sí, desde cualquier equipo en la red de la oficina |
| ¿Cuánto cuesta mantenerlo? | Nada en licencias: todo lo que usa es libre y corre en una computadora que ya existe |
| ¿Qué pasa si alguien se va de la empresa? | Se le desactiva el acceso el mismo día, y se conserva el registro de lo que hizo |
| ¿Se puede saber cuánto costó cada compra? | Sí. Cada movimiento guarda el precio al que se registró, y no cambia aunque el producto suba de precio después |

---

## Si algo falla en vivo

| Problema | Qué hacer |
|---|---|
| No abre la página | `docker compose ps` en la carpeta `_dev`. Si están caídos: `docker compose up -d`, esperar 15 segundos |
| Una pantalla da error | Seguí adelante con otro bloque y anotá qué pantalla fue. No la vuelvas a intentar en vivo |
| Se cerró la sesión | El navegador guarda una sola sesión por sitio; volvé a entrar |
| Te equivocaste al registrar algo | No lo intentes corregir en vivo. Decí *«esto lo corrige el administrador después»* y seguí |

**Regla general:** si algo no sale, no lo pelees frente a la gente. Seguí con
el siguiente bloque — hay ocho, y con siete la demostración funciona igual.

---

## Después de la presentación

Volvé al punto de partida, para dejar la copia lista para la próxima:

```powershell
cd ...\Proyecto_Inventario_dev
.\scripts\restaurar.ps1 -Archivo respaldos\DEMO-punto-de-partida.dump
```
