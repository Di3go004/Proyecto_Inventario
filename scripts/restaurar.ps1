# Restaura la base de datos desde un respaldo (RNF-08).
#
# Ver los respaldos disponibles:
#     .\scripts\restaurar.ps1
#
# Restaurar uno:
#     .\scripts\restaurar.ps1 -Archivo respaldos\bodega_2026-08-19_1700.dump
#
# Probar un respaldo SIN tocar los datos reales (recomendado hacerlo de vez
# en cuando: restaura en una base aparte y luego la borra):
#     .\scripts\restaurar.ps1 -Archivo respaldos\... -SoloProbar
#
# ATENCION: sin -SoloProbar, esto REEMPLAZA el contenido actual de la base.

param(
    [string]$Archivo,
    [switch]$SoloProbar
)

$ErrorActionPreference = "Stop"

$RaizProyecto = Split-Path -Parent $PSScriptRoot
Set-Location $RaizProyecto

function Mostrar-Disponibles {
    Write-Host "Respaldos disponibles:" -ForegroundColor Cyan
    $lista = Get-ChildItem "respaldos" -Filter "bodega_*.dump" -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending
    if (-not $lista) {
        Write-Host "  (ninguno todavia - genera uno con .\scripts\respaldo.ps1)"
        return
    }
    $lista | ForEach-Object {
        $mb = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  $($_.Name)   $mb MB   $($_.LastWriteTime)"
    }
}

if (-not $Archivo) {
    Mostrar-Disponibles
    Write-Host ""
    Write-Host "Uso: .\scripts\restaurar.ps1 -Archivo respaldos\<nombre>.dump"
    exit 0
}

if (-not (Test-Path $Archivo)) {
    Write-Host "No existe el archivo: $Archivo" -ForegroundColor Red
    Mostrar-Disponibles
    exit 1
}

$valores = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') {
        $valores[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$baseDatos = $valores["POSTGRES_DB"]
$usuario   = $valores["POSTGRES_USER"]

$rutaCompleta = (Get-Item $Archivo).FullName
docker compose cp $rutaCompleta "db:/tmp/restaurar.dump" | Out-Null

if ($SoloProbar) {
    # Modo seguro: se restaura en una base aparte solo para comprobar que el
    # respaldo sirve, y se borra al terminar. No toca los datos reales.
    $basePrueba = "prueba_restauracion"
    Write-Host "Probando el respaldo en una base temporal (no se tocan los datos reales)..." -ForegroundColor Cyan

    docker compose exec -T db psql -U $usuario -d postgres -c "DROP DATABASE IF EXISTS $basePrueba;" | Out-Null
    docker compose exec -T db psql -U $usuario -d postgres -c "CREATE DATABASE $basePrueba;" | Out-Null
    docker compose exec -T db pg_restore -U $usuario -d $basePrueba /tmp/restaurar.dump

    Write-Host ""
    Write-Host "Contenido recuperado del respaldo:" -ForegroundColor Green
    docker compose exec -T db psql -U $usuario -d $basePrueba -t -c "SELECT 'articulos: '||count(*) FROM ventas_articulo UNION ALL SELECT 'activos: '||count(*) FROM tecnica_activo UNION ALL SELECT 'movimientos: '||count(*) FROM ventas_movimientoventa;"

    docker compose exec -T db psql -U $usuario -d postgres -c "DROP DATABASE $basePrueba;" | Out-Null
    Write-Host "Prueba terminada, base temporal eliminada. Los datos reales no se tocaron." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "Vas a REEMPLAZAR todo el contenido de la base '$baseDatos'" -ForegroundColor Yellow
Write-Host "con el respaldo: $Archivo" -ForegroundColor Yellow
Write-Host "Los datos actuales que no esten en ese respaldo SE PIERDEN." -ForegroundColor Yellow
Write-Host ""
$confirmacion = Read-Host "Escribe RESTAURAR (en mayusculas) para continuar"

if ($confirmacion -cne "RESTAURAR") {
    Write-Host "Cancelado. No se toco nada." -ForegroundColor Green
    exit 0
}

Write-Host "Vaciando la base actual..."
docker compose exec -T db psql -U $usuario -d $baseDatos -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | Out-Null

Write-Host "Cargando el respaldo..."
docker compose exec -T db pg_restore -U $usuario -d $baseDatos /tmp/restaurar.dump

Write-Host ""
Write-Host "Restauracion terminada." -ForegroundColor Green
Write-Host "Comprueba que el stock cuadre con:" -ForegroundColor Cyan
Write-Host "   docker compose exec web python manage.py recalcular_stock --solo-revisar"
