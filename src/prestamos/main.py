"""Punto de entrada de la aplicación de escritorio."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar como script: añade 'src' al path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from prestamos.ui.ventana_principal import VentanaPrincipal  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Gestor de Préstamos")
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
