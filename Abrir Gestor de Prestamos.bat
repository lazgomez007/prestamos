@echo off
rem Lanzador de doble clic para el Gestor de Prestamos.
rem Usa pythonw.exe (sin ventana de consola). Si falta el entorno, lo crea.
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "src\prestamos\main.py"
) else (
    echo Primer uso: preparando el entorno, espera un momento...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
)
