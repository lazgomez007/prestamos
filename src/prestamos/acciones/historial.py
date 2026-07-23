"""Historial de señales por (ticker, temporalidad) para ver la tendencia.

Se guarda un punto cada vez que la señal CAMBIA (inflexión), con su fecha, la
recomendación y el valor numérico (Recommend.All, -1 a +1). Así se puede dibujar
una línea de tiempo y detectar cuándo se dio la vuelta.

Archivo: acciones/history.json
    { "SPY:1D": [ {"t": "2026-07-23T05:00:00", "r": "BUY", "s": 0.47}, ... ] }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import CARPETA

log = logging.getLogger(__name__)

MAX_PUNTOS = 1000  # por serie, por seguridad


def ruta_historial(ruta: Path | None = None) -> Path:
    return Path(ruta or (CARPETA / "history.json"))


def cargar(ruta: Path | None = None) -> dict[str, list[dict]]:
    ruta = ruta_historial(ruta)
    if not ruta.exists():
        return {}
    try:
        with ruta.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error("No se pudo leer el historial (%s); se empieza vacío.", e)
        return {}


def guardar(hist: dict[str, list[dict]], ruta: Path | None = None) -> None:
    ruta = ruta_historial(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2, sort_keys=True)


def registrar(lecturas, ruta: Path | None = None, ahora: datetime | None = None) -> int:
    """Agrega un punto por cada señal que cambió respecto al último registro.

    Devuelve cuántas inflexiones nuevas se guardaron.
    """
    ahora = ahora or datetime.now()
    hist = cargar(ruta)
    nuevos = 0
    for l in lecturas:
        if l.recomendacion is None:      # error / sin datos: no registrar
            continue
        serie = hist.setdefault(l.clave, [])
        if serie and serie[-1]["r"] == l.recomendacion:
            continue                     # sin cambio: no duplicar
        serie.append({
            "t": ahora.replace(microsecond=0).isoformat(),
            "r": l.recomendacion,
            "s": l.score,
        })
        del serie[:-MAX_PUNTOS]
        nuevos += 1
    if nuevos:
        guardar(hist, ruta)
    return nuevos
