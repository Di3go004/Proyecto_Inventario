# Respaldos de la base de datos (RNF-08)

La base de datos es la única fuente de verdad del inventario: si se pierde,
se pierde todo lo que hoy está en los dos Excel más lo que se ha registrado
desde entonces. Estos scripts la respaldan y la restauran.

## Uso manual

```powershell
# Crear un respaldo ahora
.\scripts\respaldo.ps1

# Ver los respaldos que existen
.\scripts\restaurar.ps1

# Comprobar que un respaldo sirve, SIN tocar los datos reales
.\scripts\restaurar.ps1 -Archivo respaldos\bodega_2026-08-19_1700.dump -SoloProbar

# Restaurar de verdad (pide confirmación escrita)
.\scripts\restaurar.ps1 -Archivo respaldos\bodega_2026-08-19_1700.dump
```

Los respaldos se guardan en `respaldos\` y se conservan **30 días**; los más
viejos se borran solos. Para cambiarlo: `.\scripts\respaldo.ps1 -DiasDeRetencion 60`.

Esa carpeta está excluida de git a propósito: contiene datos reales de la
empresa y no debe subirse al repositorio.

## Programarlo para que corra solo (en el equipo servidor)

1. Abre el **Programador de tareas** de Windows (`taskschd.msc`).
2. **Crear tarea** (no "tarea básica").
3. Pestaña **General**:
   - Nombre: `Respaldo Bodega`
   - Marca **Ejecutar tanto si el usuario inició sesión como si no**.
4. Pestaña **Desencadenadores** → Nuevo → Diariamente, a una hora en que la
   empresa no esté trabajando (ej. 11:00 p.m.).
5. Pestaña **Acciones** → Nueva:
   - Acción: `Iniciar un programa`
   - Programa: `powershell.exe`
   - Argumentos:
     ```
     -NoProfile -ExecutionPolicy Bypass -File "C:\ruta\al\Proyecto_Inventario\scripts\respaldo.ps1"
     ```
     (usa la ruta real del proyecto en el servidor)
6. Pestaña **Condiciones**: desmarca "Iniciar la tarea solo si el equipo está
   conectado a la corriente alterna" si el servidor es una laptop.

Docker Desktop debe estar corriendo para que el respaldo funcione; conviene
dejarlo configurado para que **arranque solo al encender el equipo**.

## Recomendaciones importantes

- **Sacar una copia fuera del servidor.** Un respaldo guardado en el mismo
  disco que la base no protege contra que ese disco falle. Copia la carpeta
  `respaldos\` a OneDrive, a un disco externo o a otro equipo.
- **Probar la restauración de vez en cuando** (con `-SoloProbar`). Un respaldo
  que nunca se ha restaurado no es un respaldo comprobado.
- **Antes de cualquier cambio grande** (actualizar el sistema, importar un
  Excel grande), corre un respaldo manual primero.

## Después de restaurar

Comprueba que el stock cuadre con el historial de movimientos:

```powershell
docker compose exec web python manage.py recalcular_stock --solo-revisar
```

Si reporta artículos descuadrados, corrígelos quitando `--solo-revisar`.
