"""Monitor de señales técnicas: avisa por Telegram cuando cambia el semáforo.

Uso:
    python monitor_acciones.py

Requiere las variables de entorno TELEGRAM_TOKEN y TELEGRAM_CHAT_ID para
notificar (si faltan, igual registra los cambios en el log).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from prestamos.acciones.monitor import configurar_log, ejecutar  # noqa: E402


def main() -> int:
    configurar_log()
    try:
        _, cambios = ejecutar()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"ERROR inesperado: {type(e).__name__}: {e}")
        return 1
    print(f"Listo. Cambios notificados: {len(cambios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
