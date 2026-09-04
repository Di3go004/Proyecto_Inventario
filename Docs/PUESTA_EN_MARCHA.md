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

**Ya está hecho: el servidor quedó en `192.168.1.200`.** Lo que sigue explica
cómo quedó y qué hacer si algún día hay que cambiarlo.

El router asigna las IP por DHCP y ya la cambió dos veces (`192.168.1.17` →
`192.168.1.6` → se fijó en `192.168.1.200`). Cuando cambia se rompen dos
cosas a la vez: el enlace que la gente tiene guardado deja de responder, y el
sistema rechaza la conexión con un **error 400**.

### Por qué se fijó desde Windows y no desde el router

Lo normal sería una **reserva DHCP** en el router: se le indica que a esa PC
siempre le dé la misma IP. Pero el ARRIS que entrega el proveedor **tiene esa
opción bloqueada**, así que se fijó desde Windows.

### Por qué `.200` y no un número bajo

Porque el router reparte **desde `.2` hacia arriba**. Al momento de
configurarlo había 17 dispositivos ocupando de `.2` a `.29`.

Fijar la PC en un número bajo —como el `.6` que tenía— es peligroso
justamente porque el router también reparte ahí: un fin de semana con la PC
apagada, el router le entrega esa misma dirección a un celular, y el lunes
hay dos equipos peleando la misma IP. Falla de forma intermitente y cuesta
días encontrar el motivo.

`.200` está muy por encima de donde va el router, así que tendría que haber
unos 200 dispositivos conectados a la vez para llegar ahí. Evitar del `.250`
en adelante: ahí hay equipo del propio proveedor.

### Cómo se configuró (y cómo cambiarlo)

1. `Windows + R` → escribir `ncpa.cpl` → Enter
2. Clic derecho sobre el adaptador activo → **Propiedades**
3. Seleccionar **Protocolo de Internet versión 4 (TCP/IPv4)** → **Propiedades**
4. Marcar **"Usar la siguiente dirección IP"** y llenar:

   | Campo | Valor |
   |---|---|
   | Dirección IP | `192.168.1.200` |
   | Máscara de subred | `255.255.255.0` |
   | Puerta de enlace predeterminada | `192.168.1.1` |
   | DNS preferido | `8.8.8.8` |
   | DNS alternativo | `8.8.4.4` |

5. **Aceptar** en las dos ventanas

Para confirmar que quedó fija (tiene que decir `Manual`, no `Dhcp`):

```powershell
Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.IPv4DefaultGateway } |
  ForEach-Object { $_.InterfaceAlias; $_.IPv4Address.IPAddress;
    (Get-NetIPAddress -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4).PrefixOrigin }
```

### Avisarle al sistema (este paso NO se puede saltar)

En el archivo `.env` de la carpeta del proyecto:

```
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.200
```

Y después:

```powershell
docker compose up -d
```

> ⚠️ **`up -d`, no `restart`.** Es la trampa en la que ya se cayó una vez:
> `docker compose restart` reinicia el proceso pero **el contenedor conserva
> las variables con las que se creó**, así que sigue usando la IP vieja
> aunque el archivo `.env` ya diga la nueva — y la pantalla sigue dando error
> 400 sin explicación. `up -d` recrea el contenedor leyendo el `.env` de
> nuevo. Esto aplica a **cualquier** cambio del `.env`, no solo a la IP.
>
> Para comprobar que el contenedor sí agarró el cambio:
> ```powershell
> docker compose exec web printenv DJANGO_ALLOWED_HOSTS
> ```

### El enlace para el personal

**`http://192.168.1.200:8000`**

Solo hace falta estar en la misma red (`Administracion 2`). No se necesita
internet: el sistema funciona completo dentro de la red local (RNF-02).

### Si algún día se pasa a cable (recomendado)

Hoy el servidor está conectado por **Wi-Fi**. Para la PC de la que dependen
4 a 10 personas conviene un cable: es más estable y arranca antes al encender
el equipo.

Ojo: la configuración de IP es **por tarjeta de red**, no por computadora. Al
pasar a cable hay que repetir los pasos de arriba en *esa* tarjeta y volver a
correr `docker compose up -d`.

### Si alguna PC no conecta

El firewall y el perfil de red ya están configurados —regla **"Control de
Bodega - Django 8000"** (TCP entrante, habilitada) y red en **Privada**—.
Si aun así una PC no entra, revisar en este orden:

```powershell
# 1. ¿El perfil de red sigue en Privada? Con "Pública" el firewall bloquea
#    aunque la regla exista.
Get-NetConnectionProfile

# 2. ¿La regla del firewall sigue activa?
netsh advfirewall firewall show rule name="Control de Bodega - Django 8000"

# 3. ¿El sistema está autorizando la IP correcta?
docker compose exec web printenv DJANGO_ALLOWED_HOSTS
```

Y desde la PC que no conecta, para ver si el problema es de red o del sistema:

```powershell
Test-NetConnection 192.168.1.200 -Port 8000
```

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

## Trabajar sin tocar lo que está en uso

Docker monta **la carpeta**, no la rama (`- .:/app` en `docker-compose.yml`).
Por eso corre siempre lo que esté sacado en el disco: si en la carpeta de la
empresa cambiás de rama, el sistema que usa el personal cambia con vos, a
medio terminar. Por eso hay **dos carpetas**, cada una con su rama:

| Carpeta | Rama | Puerto | Quién entra |
|---|---|---|---|
| `Proyecto_Inventario` | `main` | 8000 | **El personal**, desde toda la red |
| `Proyecto_Inventario_dev` | `feature/faseN` | 8001 | Solo vos, solo desde esta PC |

No son dos copias sueltas: son el **mismo repositorio** (`git worktree`), así
que las ramas y los commits se ven desde las dos. Lo que no comparten es la
base de datos — cada una tiene la suya, y por eso podés borrar, importar y
romper en la de pruebas sin que el personal se entere.

> ⚠️ **La carpeta de la empresa se queda en `main` y no se cambia de rama.**
> Es la única regla que importa de todo esto.

### Cómo se logró

Lo hacen tres variables del `.env` de la carpeta de desarrollo — y como el
`.env` no se versiona, cada carpeta tiene el suyo:

```
COMPOSE_PROJECT_NAME=inventario_dev   # contenedores y volumen aparte
PUERTO_WEB=127.0.0.1:8001             # solo esta PC, no la red
PUERTO_DB=5433
```

La carpeta de la empresa **no tiene ninguna de las tres**, y sin ellas quedan
los valores de siempre (proyecto por el nombre de la carpeta, puertos 8000 y
5432). Es decir: no hubo que cambiarle nada.

### El día a día

Trabajás en `Proyecto_Inventario_dev` y probás en <http://localhost:8001>.
Cuando algo ya está listo y probado:

```powershell
# 1. En la carpeta de desarrollo: guardar y subir
cd ...\Proyecto_Inventario_dev
git add -A
git commit -m "lo que se hizo"
git push origin feature/fase5

# 2. En la carpeta de la empresa: traerlo a main
cd ...\Proyecto_Inventario
git merge feature/fase5
git push origin main
```

Después del `merge`, solo hace falta más si el cambio tocó ciertas cosas:

- **Migraciones nuevas** → `docker compose exec web python manage.py migrate`
- **`requirements.txt` o `docker-compose.yml`** → `docker compose up -d --build`
- **Solo código o plantillas** → nada: `runserver` recarga solo

### Empezar otra fase

Cuando `feature/fase5` ya esté en `main` y quieras arrancar la siguiente,
desde la carpeta de desarrollo:

```powershell
cd ...\Proyecto_Inventario_dev
git fetch origin
git checkout -b feature/fase6 origin/main
```

**No** hagas `git checkout main` aquí para actualizarte antes: `main` está
sacada en la carpeta de la empresa y git no deja tener la misma rama en dos
carpetas a la vez. Te va a responder:

```
fatal: 'main' is already used by worktree at ...\Proyecto_Inventario
```

No es un error tuyo ni algo que haya que arreglar — es la red de seguridad que
impide que la carpeta de la empresa y la de pruebas terminen en la misma rama.
Por eso se arranca desde `origin/main`, que es la copia de GitHub y no está
amarrada a ninguna carpeta.

### Entrar en los dos al mismo tiempo

Si abrímos los dos como `localhost:8000` y `localhost:8001`, al entrar en uno
**se cierra la sesión del otro** (en realidad de los dos). No es una falla del
sistema: las cookies del navegador se reparten por **host**, y el puerto no
cuenta. Para el navegador los dos son el mismo sitio, `localhost`, así que
comparten una sola cookie de sesión y la segunda pisa a la primera.

La solución no cuesta nada: usar **un nombre distinto para cada uno**.

| | Dirección |
|---|---|
| Empresa | <http://localhost:8000> |
| Pruebas | <http://127.0.0.1:8001> |

`localhost` y `127.0.0.1` llevan a la misma máquina, pero para el navegador son
dos sitios distintos, así que cada uno guarda su propia sesión y se puede estar
dentro de los dos a la vez. No hay que configurar nada: `DJANGO_ALLOWED_HOSTS`
de la carpeta de la empresa ya acepta las dos formas.

Sirve igual usar una ventana de incógnito para uno de los dos, o dos navegadores
distintos.

### Refrescar los datos de prueba

La base de desarrollo es una **foto** de la real del día que se creó; no se
actualiza sola. Para volver a copiarla se usan los mismos dos scripts de
siempre, sin nada especial:

```powershell
# 1. En la carpeta de la empresa: generar un respaldo
cd ...\Proyecto_Inventario
.\scripts
espaldo.ps1

# 2. En la carpeta de desarrollo: restaurar ESE archivo
cd ...\Proyecto_Inventario_dev
.\scripts
estaurar.ps1 -Archivo ..\Proyecto_Inventario
espaldosodega_<fecha>.dump
```

Funciona porque cada script lee el `.env` de **su** carpeta: corrido desde
`_dev` apunta a la base de pruebas, no a la real. Y `respaldo.ps1` solo lee,
así que el paso 1 **nunca** toca los datos del personal.

El paso 2 pide escribir `RESTAURAR` en mayúsculas antes de hacer nada, y
antes de eso dice a qué base va a entrar. Leé esa línea: debe decir
`inventario_dev-db-1`.

> Es el mismo comando que en la carpeta de la empresa reemplazaría los datos
> reales del personal — **fijate siempre en qué carpeta estás.**

### Si algún día querés quitar la carpeta de desarrollo

```powershell
cd ...\Proyecto_Inventario_dev
docker compose down -v          # borra su base de pruebas
cd ...\Proyecto_Inventario
git worktree remove ..\Proyecto_Inventario_dev
```

---

## Para leer después

- [PLAN.md](PLAN.md) — cómo funciona el sistema por dentro y por qué se
  tomó cada decisión
- [scripts/PROGRAMAR_RESPALDO.md](scripts/PROGRAMAR_RESPALDO.md) — respaldos
  automáticos
- [REQUERIMIENTOS_FUNCIONALES.md](REQUERIMIENTOS_FUNCIONALES.md) — qué tiene
  que hacer el sistema, punto por punto
