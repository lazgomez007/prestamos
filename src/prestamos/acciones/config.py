"""Carga de la configuración (config.yaml) y del estado (state.json)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parents[3]          # raíz del proyecto
CARPETA = RAIZ / "acciones"
CONFIG_POR_DEFECTO = CARPETA / "config.yaml"
ESTADO_POR_DEFECTO = CARPETA / "state.json"

REGLAS = ("any_change", "only_strong")


def ruta_config() -> Path:
    return Path(os.environ.get("ACCIONES_CONFIG", CONFIG_POR_DEFECTO))


def ruta_estado() -> Path:
    return Path(os.environ.get("ACCIONES_STATE", ESTADO_POR_DEFECTO))


def cargar_config(ruta: Path | None = None) -> dict:
    ruta = Path(ruta or ruta_config())
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró la configuración: {ruta}")
    with ruta.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    tickers = cfg.get("tickers") or []
    for t in tickers:
        t.setdefault("screener", "america")
    cfg["tickers"] = tickers
    cfg["intervalos"] = cfg.get("intervalos") or ["1D"]
    regla = cfg.get("regla", "any_change")
    if regla not in REGLAS:
        log.warning("Regla desconocida '%s'; se usa 'any_change'.", regla)
        regla = "any_change"
    cfg["regla"] = regla
    return cfg


ENCABEZADO = """\
# Configuración del monitor de análisis técnico (TradingView / tipo Investing.com)
#
# tickers    : símbolos a vigilar. Bolsas de EE.UU. (Nueva York): NASDAQ, NYSE, AMEX.
# intervalos : 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1D, 1W, 1M
# regla      : any_change  -> avisa ante cualquier cambio de señal
#              only_strong -> avisa solo al entrar/salir de STRONG_BUY / STRONG_SELL
#
# Telegram: el token y el chat_id se leen de las variables de entorno
# TELEGRAM_TOKEN y TELEGRAM_CHAT_ID (nunca los guardes aquí).
"""


def guardar_config(cfg: dict, ruta: Path | None = None) -> None:
    ruta = Path(ruta or ruta_config())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        f.write(ENCABEZADO)
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def agregar_ticker(cfg: dict, symbol: str, exchange: str,
                   screener: str = "america") -> bool:
    """Agrega un ticker si no existe ya. Devuelve True si se agregó."""
    symbol = symbol.strip().upper()
    exchange = exchange.strip().upper()
    if any(t["symbol"].upper() == symbol for t in cfg["tickers"]):
        return False
    cfg["tickers"].append(
        {"symbol": symbol, "exchange": exchange, "screener": screener}
    )
    return True


def quitar_ticker(cfg: dict, symbol: str) -> bool:
    """Quita un ticker de la configuración. Devuelve True si se quitó."""
    symbol = symbol.strip().upper()
    antes = len(cfg["tickers"])
    cfg["tickers"] = [t for t in cfg["tickers"] if t["symbol"].upper() != symbol]
    return len(cfg["tickers"]) < antes


def limpiar_estado_de(symbol: str, ruta: Path | None = None) -> None:
    """Borra del estado las entradas de un símbolo que ya no se vigila."""
    symbol = symbol.strip().upper()
    estado = cargar_estado(ruta)
    nuevo = {k: v for k, v in estado.items() if k.split(":")[0].upper() != symbol}
    if nuevo != estado:
        guardar_estado(nuevo, ruta)


def cargar_estado(ruta: Path | None = None) -> dict[str, str]:
    ruta = Path(ruta or ruta_estado())
    if not ruta.exists():
        return {}
    try:
        with ruta.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error("No se pudo leer el estado (%s); se empieza vacío.", e)
        return {}


def guardar_estado(estado: dict[str, str], ruta: Path | None = None) -> None:
    ruta = Path(ruta or ruta_estado())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False, sort_keys=True)
