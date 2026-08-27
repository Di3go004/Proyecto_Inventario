# Puesta en marcha — empezar de cero con los datos reales

Guía para el día que se carguen los inventarios reales y el sistema pase a
usarse de verdad. Hasta ahora todo lo que hay en la base son pruebas.

**Léela completa antes de empezar.** Son unas 2 horas con calma, y hay dos
pasos (fijar la IP y programar el respaldo) que dependen del router y de
Windows, no del sistema.

---

## Antes de nada: dónde se corre cada cosa

Todo se ejecuta **desde la carpeta del proyecto**, abriendo PowerShell ahí:

```
C:\Users\proye\OneDrive\Desktop\Diego\Sistema_Inventario_SE\Proyecto_Inventario
```

Hay dos clases de comando y conviene no confundirlas:

| Empieza con | Dónde corre | Ejemplo |
|---|---|---|
| `.\scripts\...` | En Windows, directo | `.\scripts\respaldo.ps1` |
| `docker compose exec web ...` | Dentro del contenedor | `docker compose exec web python manage.py ...` |

Y el sistema tiene que estar levantado para lo segundo:

```powershell
docker compose up -d
```

Para comprobar que está arriba: `docker compose ps` — los dos servicios
(`db` y `web`) deben decir **Up**.

---

## Paso 1 — Respaldo antes de tocar nada

```powershell
.\scripts\respaldo.ps1
```

Guarda un `.dump` en `respaldos\` con la fecha en el nombre.

Aunque lo que haya sean pruebas, hacelo igual: si la importación real sale
mal a media carga, este archivo es la única forma de volver atrás.

Para comprobar que el respaldo sirve **sin tocar los datos**:

```powershell
.\scripts\restaurar.ps1 -Archivo respaldos\<el-archivo>.dump -SoloProbar
```

---

## Paso 2 — Vaciar el catálogo

Primero, **sin borrar nada**, para ver qué se llevaría por delante:

```powershell
docker compose exec web python manage.py limpiar_catalogo --que todo
```

Muestra el conteo y no toca la base. Si el número cuadra con lo que
esperás, entonces sí:

```powershell
docker compose exec web python manage.py limpiar_catalogo --que todo --si-estoy-seguro
```

**Qué borra:** artículos, activos, movimientos y préstamos. Los folios
vuelven a empezar en `ING-00001` / `SAL-00001`.

**Qué NO borra:** usuarios, proveedores y categorías. Los proveedores se
dejan a propósito — la carga masiva los reutiliza por nombre y así no se
duplican.

> `--que ventas` o `--que tecnica` limpian solo un módulo, por si hay que
> rehacer uno sin tocar el otro.

---

## Paso 3 — Importar los dos Excel

Esto se hace **desde el navegador**, entrando como administrador.

1. **Bodega 1 y 2** → menú **Bodega 1 y 2** → botón *Carga masiva desde Excel*
   → subir `01 FO-SE-053 INVENTARIO 2025.xlsx`
2. Elegir la hoja del mes que corresponda
3. Revisar el mapeo de columnas que propone y la vista previa
4. Confirmar
5. Repetir en **Bodega Técnica** con `FO-SE-065 ... Bodega Técnica 2025.xlsx`

Al terminar avisa cuántos creó, cuántos actualizó y cuántos omitió. **Leé
los avisos amarillos**: las filas que no tienen bodega reconocible (las que
dicen `N/A`) se omiten y se listan ahí.

> El código interno se genera solo con el estándar `SE-MODELO-capacidad`; el
> que venga en el Excel se ignora porque está inconsistente. El
> administrador puede cambiarlo a mano después, artículo por artículo. En
> Bodega Técnica es al revés: ahí el código sí se importa tal cual, porque lo
> asigna la empresa.

**Revisá que la columna de existencia sea la correcta.** El sistema propone
`TOTAL EXISTENCIA MENSUAL`, que es la buena. Los dos Excel traen otras
columnas parecidas —`EXISTENCIA INICIO SEMANA`, `EXISTENCIA POR SEMANA`,
`VIENE MES ANTERIOR`— que son saldos parciales y en enero vienen vacíos. Si
en la vista previa las cantidades salen todas en cero, es porque quedó
elegida una de esas: cambiala en el mapeo.

Volver a importar el mismo archivo no duplica nada: se guarda la diferencia
contra lo que ya había, no el total.

---

## Paso 4 — Comprobar que el stock cuadra

```powershell
docker compose exec web python manage.py recalcular_stock --solo-revisar
```

Tiene que decir: **"Todo cuadra: ningún artículo tiene el stock
descuadrado."**

Si reporta diferencias, el mismo comando **sin** `--solo-revisar` las
corrige recalculando desde los movimientos.

---

## Paso 5 — Revisar los umbrales de alerta

Todos los artículos entran con los umbrales por defecto: **crítico 2 /
alerta 5 / óptimo 20**.

Eso está bien para lo que rota normal, pero va a dar alertas raras en dos
casos: lo que siempre se tiene de a uno (una báscula grande en alerta
permanente) y lo que se maneja por cientos (un rollo de cable que nunca
avisa).

Andá a **Reportes → Alertas de stock**, mirá la lista y ajustá los que no
tengan sentido desde **Editar** en cada artículo. No hace falta hacerlos
todos de una: se puede ir corrigiendo sobre la marcha.

---

## Paso 6 — Revisar Bodega Técnica

Esta bodega funciona distinto a la 1 y 2, y conviene tenerlo claro antes de
arrancar:

- **Solo entran cosas.** El ingreso se registra en **Movimientos → Entradas y
  salidas → Registrar ingreso**, con el mismo FO-SE-013 de las otras bodegas:
  el buscador ofrece los tres catálogos y una misma boleta puede llevar
  productos de venta y herramienta juntos. El folio es una sola serie, como el
  talonario de papel.
- **Lo único que baja la existencia es dar de baja**: descartar lo que ya no
  sirve. Se hace desde la herramienta → *Dar de baja*. No se imprime boleta,
  pero queda registrado cuántas, por qué y quién.
- **Los préstamos no mueven la existencia.** La herramienta sale y vuelve:
  sigue siendo de la bodega, solo que no está en el estante.

Andá a **Reportes → Inventario de Bodega Técnica** y revisá que las cantidades
calcen con el Excel. Desde ahí también se baja en Excel.

Si hay cosas que se gastan —bombillos, flejes, pintura— marcalas como
**consumible** al editarlas. En esas la cantidad se puede corregir
escribiéndola directamente, sin registrar una baja por cada una; el ajuste
igual queda en el historial.

---

## Paso 7 — Revisar las categorías

El sistema ya trae categorías creadas para las dos bodegas (celdas de carga,
indicadores, masas patrón… y del lado técnico herramienta manual, brocas,
ferretería…). Salieron de agrupar los productos reales de los Excel de 2025,
así que la mayoría del catálogo va a caer en alguna.

Andá a **Administración → Categorías** y ajustalas a como les dicen ustedes:
se pueden renombrar, agregar y quitar.

Dos cosas que conviene saber:

- **Renombrar no desclasifica nada**: los productos siguen apuntando a la
  misma categoría con el nombre nuevo.
- **Quitar una que esté en uso no borra los productos**, pero los deja sin
  categoría, y volver a asignarlos es uno por uno. Si solo querés cambiarle
  el nombre, usá *Editar*, no *Quitar*.

La categoría de cada producto se asigna al editarlo en el catálogo. El Excel
no la trae, así que al importar entran sin categoría — abajo de la lista de
categorías te dice cuántos van sin clasificar.

---

## Paso 8 — Crear los usuarios reales

Desde el navegador: **Administración → Usuarios → + Nuevo usuario**.

Para cada persona: usuario para entrar, nombre, rol, y dejar marcado
*Generar una contraseña segura*. **La contraseña se muestra una sola vez**
al guardar — anotala y entregásela en persona.

| Rol | Qué puede hacer |
|---|---|
| **Administrador** | Todo: catálogos, carga masiva, movimientos y usuarios |
| **Operador** | Registra entradas, salidas y préstamos. No toca el catálogo |
| **Contabilidad** | Consulta e imprime todo, no modifica nada |

Cosas a tener en cuenta:

- El nombre de usuario **se guarda en minúsculas** y al entrar da igual cómo
  se escriba. La contraseña sí distingue mayúsculas.
- Si preferís escribir vos la contraseña en vez de generarla, escribila en
  el campo: al hacerlo, la casilla de *Generar* se desmarca sola.
- Que haya **al menos dos administradores**. El sistema no deja que el
  último se quite el rol, pero si solo hay uno y se olvida la contraseña,
  hay que rescatarlo desde la terminal.

Cuando ya existan las personas reales, **borrá los usuarios que se crearon
solo para probar**. En la lista se distinguen porque no tienen ningún
registro a su nombre.

---

## Paso 9 — Cambiar las contraseñas que quedaron de las pruebas

Las contraseñas que se pusieron durante las pruebas quedaron escritas en la
conversación donde se configuró el sistema, así que **hay que cambiarlas
todas antes de arrancar en real** — no solo las de las cuentas que se siguen
usando.

Andá a **Administración → Usuarios** y usá **Contraseña** en cada una. La
columna *Última entrada* te ayuda a ver cuáles siguen en uso.

Si alguna vez nadie puede entrar, la salida de emergencia es desde la
terminal:

```powershell
docker compose exec web python manage.py cambiar_clave admin --generar
```

---

## Paso 10 — Fijar la IP del servidor

⚠️ **Esto hay que hacerlo antes de repartir el enlace al personal.**

Hoy el router asigna la IP por DHCP y **ya cambió una vez** (de
`192.168.1.17` a `192.168.1.6`). Cuando cambia se rompen dos cosas a la vez:
el enlace guardado deja de responder, y el sistema empieza a rechazar la
conexión con un error 400.

Dos formas de resolverlo:

- **Reserva DHCP en el router** (recomendado): se le indica que a esa PC
  siempre le dé la misma IP. No hay que tocar nada en Windows.
- **IP estática en Windows**: se configura a mano en el adaptador de red.
  Funciona, pero hay que elegir una IP fuera del rango que reparte el router
  o dos equipos pueden terminar con la misma.

Para ver la IP actual:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' }
```

Ya fijada, ponerla en el archivo `.env`:

```
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.6
```

y reiniciar:

```powershell
docker compose restart web
```

El resto de las computadoras y tablets entran a **`http://192.168.1.6:8000`**
(con la IP que haya quedado).

> El firewall y el perfil de red ya están configurados. Si alguna PC no
> conecta, revisar que el perfil de red de la PC servidor siga en
> **Privada** — con "Pública" el firewall bloquea aunque la regla exista:
> `Get-NetConnectionProfile`

---

## Paso 11 — Pasar a modo producción

Hasta ahora el sistema corre con el servidor de desarrollo de Django, que es
de un solo hilo y no aguanta a varias personas registrando a la vez.

1. En el archivo `.env`, cambiar:

   ```
   DJANGO_DEBUG=False
   ```

   Con `True`, cualquiera que provoque un error ve la traza completa con
   rutas y configuración del servidor.

2. Levantar con la configuración de producción:

   ```powershell
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

3. Comprobar que la configuración está sana:

   ```powershell
   docker compose exec web python manage.py check --deploy
   ```

   Tiene que decir **"no issues (4 silenced)"**. Los 4 silenciados piden
   HTTPS y están desactivados a propósito: el sistema corre por HTTP en la
   red local, y activarlos dejaría a todos afuera.

> **Para actualizar el sistema en el futuro** es esa misma línea del punto 2:
> aplica migraciones, recopila los archivos estáticos y reinicia.

---

## Paso 12 — Dejar el respaldo automático

Los scripts funcionan y están probados, pero **hoy hay que ejecutarlos a
mano**. El paso a paso para dejarlos en el Programador de tareas de Windows
está en [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md).

Se conservan **30 días** de respaldos; los más viejos se borran solos.

Si se salta este paso, el sistema funciona igual — pero el día que se dañe
el disco se pierde todo el inventario, que es exactamente lo que este
proyecto vino a evitar.

---

## Resumen para tachar

- [ ] 1. Respaldo (`.\scripts\respaldo.ps1`)
- [ ] 2. Vaciar el catálogo (`limpiar_catalogo --que todo --si-estoy-seguro`)
- [ ] 3. Importar los dos Excel desde el navegador
- [ ] 4. Verificar el stock (`recalcular_stock --solo-revisar`)
- [ ] 5. Revisar los umbrales de alerta
- [ ] 6. Revisar Bodega Técnica (Reportes → Inventario de Bodega Técnica)
- [ ] 7. Revisar las categorías (Administración → Categorías)
- [ ] 8. Crear los usuarios reales y borrar los de prueba
- [ ] 9. Cambiar las contraseñas de prueba
- [ ] 10. **Fijar la IP** y ponerla en `DJANGO_ALLOWED_HOSTS`
- [ ] 11. Pasar a producción (`DJANGO_DEBUG=False` + `docker-compose.prod.yml`)
- [ ] 12. Programar el respaldo automático

---

## Si algo sale mal

**La página no carga desde otra computadora**
Revisar, en este orden: que la IP en `DJANGO_ALLOWED_HOSTS` sea la actual,
que el perfil de red siga en "Privada", y que Docker esté corriendo
(`docker compose ps`).

**Cambié algo y no se ve el cambio**
Si tocaste `.env` o la configuración, reiniciá el contenedor: el proceso
guarda la configuración en memoria al arrancar.
`docker compose restart web`

**Se importó mal y quiero repetir**
Volvé al paso 1. La importación se puede rehacer las veces que haga falta.

**Necesito volver a un respaldo**

```powershell
.\scripts\restaurar.ps1
.\scripts\restaurar.ps1 -Archivo respaldos\<archivo>.dump
```

El primero lista los respaldos disponibles; el segundo restaura y pide
confirmación escrita antes de hacerlo.

---

## Para leer después

- [PLAN.md](PLAN.md) — cómo funciona el sistema por dentro y por qué se
  tomó cada decisión
- [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md) — respaldos
  automáticos
- [REQUERIMIENTOS_FUNCIONALES.md](REQUERIMIENTOS_FUNCIONALES.md) — qué tiene
  que hacer el sistema, punto por punto
