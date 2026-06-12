"""Arranca el servidor local (FastAPI) y abre la app en una ventana de escritorio.

Si el componente de ventana (pywebview / WebView2) no estuviera disponible, abre
la aplicación en el navegador por defecto como alternativa.
"""
from __future__ import annotations

import socket
import threading
import time
import webbrowser

import uvicorn

from .api.app import app

HOST = "127.0.0.1"


def _puerto_libre() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


def _esperar_servidor(puerto: int, timeout: float = 20.0) -> bool:
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with socket.create_connection((HOST, puerto), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    puerto = _puerto_libre()
    config = uvicorn.Config(app, host=HOST, port=puerto, log_level="warning")
    servidor = uvicorn.Server(config)
    # Evita instalar manejadores de señales (no funcionan fuera del hilo principal).
    servidor.install_signal_handlers = lambda: None
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()

    url = f"http://{HOST}:{puerto}"
    if not _esperar_servidor(puerto):
        raise RuntimeError("El servidor local no respondió a tiempo.")

    try:
        import webview

        webview.create_window(
            "Gestor de Préstamos",
            url,
            width=1240,
            height=820,
            min_size=(960, 640),
        )
        webview.start()  # bloquea hasta cerrar la ventana
    except Exception as e:  # noqa: BLE001 - fallback robusto al navegador
        print(f"Ventana de escritorio no disponible ({e}). Abriendo en el navegador...")
        webbrowser.open(url)
        try:
            hilo.join()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
