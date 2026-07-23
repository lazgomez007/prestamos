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
