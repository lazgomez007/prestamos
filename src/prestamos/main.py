"""Punto de entrada de la aplicación de escritorio."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar como script: añade 'src' al path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prestamos.escritorio import main  # noqa: E402

if __name__ == "__main__":
    main()
