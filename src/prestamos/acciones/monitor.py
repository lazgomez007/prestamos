"""Monitor: compara la señal actual con la última guardada y notifica los cambios."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from . import historial, telegram
from .config import CARPETA, cargar_config, cargar_estado, guardar_estado
from .tv import SENALES_FUERTES, Lectura, consultar

log = logging.getLogger(__name__)


@dataclass
class Cambio:
    lectura: Lectura
    anterior: str

    def mensaje(self) -> str:
        l = self.lectura
        return f"⚠️ {l.symbol} ({l.intervalo}) cambió: {self.anterior} → {l.recomendacion}"


def debe_alertar(anterior: str | None, actual: str | None, regla: str) -> bool:
    """¿Este cambio merece alerta, según la regla configurada?

    - ``any_change``: cualquier cambio de recomendación.
    - ``only_strong``: solo cuando ENTRA o SALE de STRONG_BUY / STRONG_SELL
      (incluye pasar de una señal fuerte a la otra).
    """
    if actual is None or anterior is None or anterior == actual:
        return False
    if regla == "only_strong":
        ant_fuerte = anterior in SENALES_FUERTES
        act_fuerte = actual in SENALES_FUERTES
        return ant_fuerte or act_fuerte
    return True


def evaluar(
    lecturas: list[Lectura], estado: dict[str, str], regla: str
) -> tuple[list[Cambio], dict[str, str]]:
    """Devuelve (cambios que ameritan alerta, estado actualizado)."""
    nuevo = dict(estado)
    cambios: list[Cambio] = []
    for l in lecturas:
        if l.recomendacion is None:      # error o sin datos: no tocar el estado
            continue
        anterior = nuevo.get(l.clave)
        if anterior is None:
            log.info("Primera lectura de %s: %s (sin alerta)", l.clave, l.recomendacion)
        elif debe_alertar(anterior, l.recomendacion, regla):
            cambios.append(Cambio(l, anterior))
        nuevo[l.clave] = l.recomendacion
    return cambios, nuevo


def configurar_log(archivo: Path | None = None) -> None:
    archivo = archivo or (CARPETA / "monitor.log")
    archivo.parent.mkdir(parents=True, exist_ok=True)
    # La consola de Windows usa cp1252 y falla con emojis/flechas de los mensajes.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(archivo, encoding="utf-8"),
                  logging.StreamHandler()],
    )


def ejecutar(notificar: bool = True, pausa: float = 1.0) -> tuple[list[Lectura], list[Cambio]]:
    """Una corrida completa: consulta, compara, notifica y guarda el estado."""
    cfg = cargar_config()
    estado = cargar_estado()
    log.info("Consultando %d tickers en %s (regla: %s)",
             len(cfg["tickers"]), cfg["intervalos"], cfg["regla"])

    lecturas = consultar(cfg["tickers"], cfg["intervalos"], pausa=pausa)
    inflexiones = historial.registrar(lecturas)   # línea de tiempo por temporalidad
    if inflexiones:
        log.info("Se registraron %d inflexiones en el historial.", inflexiones)
    cambios, nuevo_estado = evaluar(lecturas, estado, cfg["regla"])

    for l in lecturas:
        if l.error:
            log.warning("%s (%s): %s", l.symbol, l.intervalo, l.error)
        else:
            log.info("%s (%s): %s", l.symbol, l.intervalo, l.recomendacion)

    if cambios:
        for c in cambios:
            log.info("CAMBIO: %s", c.mensaje())
            if notificar:
                telegram.enviar(c.mensaje())
    else:
        log.info("Sin cambios que alertar.")

    guardar_estado(nuevo_estado)
    return lecturas, cambios
