# Sistema de Control de Bodega — Soluciones Exactas, S.A.

Django 5 + PostgreSQL 16 en Docker, corriendo en la red local de la empresa.
Reemplaza dos libros de Excel: `FO-SE-053` (Bodega 1 y 2, venta) y `FO-SE-065`
(Bodega Técnica, herramienta interna).

## ⚠️ Antes de tocar nada: ¿en qué carpeta estoy?

Hay **dos carpetas de trabajo del mismo repositorio** (`git worktree`):

| Carpeta | Rama | Puerto | Qué es |
|---|---|---|---|
| `Proyecto_Inventario` | `main` | `0.0.0.0:8000` | **PRODUCCIÓN.** La usa el personal |
| `Proyecto_Inventario_dev` | `feature/faseN` | `127.0.0.1:8001` | Banco de pruebas |

```bash
git rev-parse --abbrev-ref HEAD   # main = producción, feature/* = pruebas
```

Reglas:

- **El trabajo se hace en `_dev`.** La carpeta de producción solo recibe
  merges de cambios ya probados.
- **La carpeta de producción no cambia de rama.** Git ya lo impide (una rama
  no puede estar sacada en dos worktrees), pero no hay que forzarlo.
- Cada carpeta tiene **su propia base de datos**. La de `_dev` es una copia; lo
  que se borre ahí no afecta al personal.
- Ojo con los scripts destructivos (`scripts/restaurar.ps1`): funcionan igual
  en las dos carpetas y leen el `.env` de la suya. Verificar la carpeta antes.

Todo el flujo está en `Docs/PUESTA_EN_MARCHA.md`, sección *"Trabajar sin tocar
lo que está en uso"*.

## Cómo correr las cosas

Siempre dentro del contenedor, desde la carpeta correspondiente:

```bash
docker compose exec -T web python manage.py test          # 390 pruebas
docker compose exec -T web python manage.py migrate
docker compose exec -T web python manage.py shell -c "..."
```

Después de cambiar el `.env` va `docker compose up -d`, **no** `restart`:
`restart` reusa las variables viejas.

## Invariantes que es fácil romper

- **La existencia se deriva de los movimientos**, nunca se acumula. Si algo
  descuadra, se recalcula desde el historial (`recalcular_stock`). Los borrados
  se ajustan con señales `post_delete`, no sobrescribiendo `delete()`: un
  borrado por queryset no llama al método del modelo.
- **El folio se escribe a mano.** Viene del talonario físico, no se genera.
- **`numero_serie` vacío se guarda como NULL**, nunca como texto. `S/S` es solo
  la forma de mostrarlo (`Articulo.serial` y el filtro `serial`). Guardarlo
  rompería el índice único y las búsquedas. Ver `ventas/test_serial.py`.
- **Bodega Técnica solo recibe ingresos.** Lo único que baja la existencia es
  dar de baja; los préstamos no la mueven porque la herramienta sigue siendo de
  la bodega.
- **FKs de catálogo (categoría, proveedor) son `SET_NULL`**; las que llevan
  historial son `PROTECT`. Nunca se pierde un movimiento por borrar un catálogo.
- Las columnas de los reportes en Excel se buscan **por título**, no por número:
  insertar una columna corre todas las que siguen.

## Verificación

El estándar del proyecto es no dar algo por bueno sin comprobarlo:

- Correr la suite completa, no solo las pruebas nuevas.
- **Verificación por mutación**: romper a propósito lo que se acaba de escribir
  y confirmar que alguna prueba falla. Una prueba que pasa igual no prueba nada.
- Para cambios de pantalla, verificar en navegador real con Playwright
  (`npx playwright`, desde el host) y borrar después los datos de prueba.

## Idioma

Todo en español de Guatemala, con voseo: código, comentarios, mensajes de
commit, documentación y pantallas. Los comentarios explican **por qué**, no
qué hace la línea.
