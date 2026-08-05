"""Envío de notificaciones por Telegram.

Las credenciales se leen de variables de entorno (nunca se guardan en el repo):
    TELEGRAM_TOKEN    -> token del bot (de @BotFather)
    TELEGRAM_CHAT_ID  -> tu chat id (de @userinfobot)
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

TIMEOUT = 20


def configurado() -> bool:
    return bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def enviar(texto: str) -> bool:
    """Envía un mensaje. Devuelve True si se entregó."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning(
            "Telegram no configurado (faltan TELEGRAM_TOKEN / TELEGRAM_CHAT_ID). "
            "Mensaje no enviado: %s", texto,
        )
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": texto},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            log.error("Telegram respondió %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:  # red, timeout...
        log.error("No se pudo enviar a Telegram: %s", e)
        return False
