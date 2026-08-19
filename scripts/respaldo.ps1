# Respaldo de la base de datos del Sistema de Control de Bodega (RNF-08).
#
# Uso normal (desde la carpeta del proyecto):
#     .\scripts\respaldo.ps1
#
# Guarda un archivo .dump en respaldos\ con la fecha en el nombre y borra
# automaticamente los que superen los dias de retencion.
#
# Para que corra solo todos los dias, ver scripts\PROGRAMAR_RESPALDO.md
#
# Nota tecnica: se usa el formato propio de PostgreSQL (-Fc), que ya viene
# comprimido, y el archivo se saca del contenedor con "docker compose cp".
# NO se canaliza la salida con "|" ni ">" de PowerShell a proposito: eso
# corrompe los datos binarios (PowerShell los reescribe como texto).

param(
    [int]$DiasDeRetencion = 30,
    [string]$CarpetaDestino = "respaldos"
)

$ErrorActionPreference = "Stop"

# Siempre trabajar desde la carpeta del proyecto, sin importar desde donde
# se invoque el script (el Programador de tareas arranca en otra ruta).
$RaizProyecto = Split-Path -Parent $PSScriptRoot
Set-Location $RaizProyecto

if (-not (Test-Path $CarpetaDestino)) {
    New-Item -ItemType Directory -Path $CarpetaDestino | Out-Null
}

# Leer credenciales del .env, para no repetirlas aqui.
$valores = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') {
        $valores[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$baseDatos = $valores["POSTGRES_DB"]
$usuario   = $valores["POSTGRES_USER"]

$marca   = Get-Date -Format "yyyy-MM-dd_HHmm"
$nombre  = "bodega_$marca.dump"
$destino = Join-Path $CarpetaDestino $nombre

Write-Host "Respaldando la base '$baseDatos'..."

# 1) pg_dump escribe el archivo DENTRO del contenedor.
docker compose exec -T db pg_dump -U $usuario -d $baseDatos -Fc -f "/tmp/$nombre"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FALLO pg_dump. Revisa que los contenedores esten arriba (docker compose ps)." -ForegroundColor Red
    exit 1
}

# 2) Se copia al disco del servidor y se borra la copia del contenedor.
docker compose cp "db:/tmp/$nombre" $destino
if ($LASTEXITCODE -ne 0) {
    Write-Host "FALLO al copiar el respaldo fuera del contenedor." -ForegroundColor Red
    exit 1
}
docker compose exec -T db rm -f "/tmp/$nombre" | Out-Null

# 3) Comprobar que el archivo sirve de verdad, no solo que existe.
if (-not (Test-Path $destino)) {
    Write-Host "FALLO: no se genero el archivo de respaldo." -ForegroundColor Red
    exit 1
}
$tamanioMB = [math]::Round((Get-Item $destino).Length / 1MB, 2)
if ((Get-Item $destino).Length -lt 1024) {
    Write-Host "AVISO: el respaldo quedo practicamente vacio. Revisalo antes de confiar en el." -ForegroundColor Yellow
    exit 1
}

# pg_restore -l solo lista el contenido: si el archivo estuviera corrupto, falla aqui.
docker compose cp $destino "db:/tmp/verificar.dump" | Out-Null
$listado = docker compose exec -T db pg_restore -l "/tmp/verificar.dump" 2>&1
docker compose exec -T db rm -f "/tmp/verificar.dump" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "FALLO: el respaldo se genero pero esta corrupto." -ForegroundColor Red
    exit 1
}
$tablas = ($listado | Select-String "TABLE DATA").Count

Write-Host "Listo: $destino ($tamanioMB MB, $tablas tablas con datos)" -ForegroundColor Green

# Limpieza de respaldos viejos
$limite = (Get-Date).AddDays(-$DiasDeRetencion)
$viejos = Get-ChildItem $CarpetaDestino -Filter "bodega_*.dump" | Where-Object { $_.LastWriteTime -lt $limite }
if ($viejos) {
    $viejos | Remove-Item -Force
    Write-Host "Se borraron $($viejos.Count) respaldo(s) con mas de $DiasDeRetencion dias."
}

$total = (Get-ChildItem $CarpetaDestino -Filter "bodega_*.dump").Count
Write-Host "Respaldos guardados actualmente: $total"
