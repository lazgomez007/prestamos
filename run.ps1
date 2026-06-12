# Lanzador de la aplicación Gestor de Préstamos.
# Crea el entorno virtual e instala dependencias la primera vez, luego abre la app.
#
# Uso:  click derecho -> "Ejecutar con PowerShell"   (o)   .\run.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venv = Join-Path $PSScriptRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creando entorno virtual (solo la primera vez)..." -ForegroundColor Cyan
    $base = Get-Command py -ErrorAction SilentlyContinue
    if ($base) { & py -3 -m venv $venv } else { & python -m venv $venv }
    Write-Host "Instalando dependencias..." -ForegroundColor Cyan
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
}

Write-Host "Abriendo Gestor de Préstamos..." -ForegroundColor Green
& $python (Join-Path $PSScriptRoot "src\prestamos\main.py")
