"""Punto de entrada de la aplicación de escritorio.

Registra cualquier error de arranque en ``~/.gestor_prestamos/error.log`` para
poder diagnosticar fallos incluso cuando se ejecuta sin consola (pythonw).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Bajo pythonw (sin consola), sys.stdout/sys.stderr son None y rompen librerías
# que llaman a stdout.isatty() (p. ej. uvicorn). Los enviamos a un sumidero.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Permite ejecutar como script: añade 'src' al path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _registrar_error(texto: str) -> None:
    try:
        log = Path.home() / ".gestor_prestamos" / "error.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(texto, encoding="utf-8")
    except Exception:
        pass


def _arrancar() -> None:
    from prestamos.escritorio import main
    main()


if __name__ == "__main__":
    import traceback

    try:
        _arrancar()
    except Exception:
        _registrar_error(traceback.format_exc())
        raise
