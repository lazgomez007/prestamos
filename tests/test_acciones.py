"""Pruebas del monitor de acciones (lógica pura, sin llamadas de red)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prestamos.acciones.config import cargar_config, cargar_estado, guardar_estado  # noqa: E402
from prestamos.acciones.monitor import debe_alertar, evaluar  # noqa: E402
from prestamos.acciones.tv import Lectura  # noqa: E402


def _lectura(symbol, intervalo, recomendacion):
    return Lectura(symbol=symbol, exchange="NASDAQ", intervalo=intervalo,
                   recomendacion=recomendacion, compra=1, neutral=1, venta=1)


# --- Regla any_change -------------------------------------------------------
def test_any_change_alerta_cualquier_cambio():
    assert debe_alertar("BUY", "NEUTRAL", "any_change") is True
    assert debe_alertar("NEUTRAL", "STRONG_SELL", "any_change") is True


def test_sin_cambio_no_alerta():
    assert debe_alertar("BUY", "BUY", "any_change") is False
    assert debe_alertar("BUY", "BUY", "only_strong") is False


def test_primera_lectura_no_alerta():
    assert debe_alertar(None, "BUY", "any_change") is False


# --- Regla only_strong ------------------------------------------------------
def test_only_strong_ignora_cambios_suaves():
    assert debe_alertar("BUY", "NEUTRAL", "only_strong") is False
    assert debe_alertar("SELL", "NEUTRAL", "only_strong") is False


def test_only_strong_alerta_al_entrar_o_salir():
    assert debe_alertar("BUY", "STRONG_BUY", "only_strong") is True      # entra
    assert debe_alertar("STRONG_SELL", "SELL", "only_strong") is True    # sale
    assert debe_alertar("STRONG_BUY", "STRONG_SELL", "only_strong") is True


# --- Evaluación completa ----------------------------------------------------
def test_evaluar_actualiza_estado_y_detecta_cambios():
    lecturas = [_lectura("SPY", "1D", "SELL"), _lectura("NVDA", "1D", "BUY")]
    estado = {"SPY:1D": "BUY"}          # NVDA no tiene registro previo
    cambios, nuevo = evaluar(lecturas, estado, "any_change")
    assert len(cambios) == 1
    assert cambios[0].lectura.symbol == "SPY"
    assert cambios[0].anterior == "BUY"
    assert "cambió: BUY → SELL" in cambios[0].mensaje()
    assert nuevo == {"SPY:1D": "SELL", "NVDA:1D": "BUY"}


def test_evaluar_ignora_lecturas_con_error():
    fallida = Lectura(symbol="XXX", exchange="NASDAQ", intervalo="1D",
                      recomendacion=None, error="sin datos")
    cambios, nuevo = evaluar([fallida], {"XXX:1D": "BUY"}, "any_change")
    assert cambios == []
    assert nuevo == {"XXX:1D": "BUY"}   # no se pisa el estado bueno


# --- Config y estado --------------------------------------------------------
def test_config_del_proyecto_es_valida():
    cfg = cargar_config()
    assert cfg["regla"] in ("any_change", "only_strong")
    assert cfg["intervalos"]
    simbolos = {t["symbol"] for t in cfg["tickers"]}
    assert {"SPY", "META", "SPCX", "NVDA"} <= simbolos
    for t in cfg["tickers"]:
        assert t["exchange"] and t["screener"]


def test_agregar_y_quitar_ticker():
    from prestamos.acciones.config import agregar_ticker, quitar_ticker
    cfg = {"tickers": [{"symbol": "SPY", "exchange": "AMEX", "screener": "america"}]}
    assert agregar_ticker(cfg, "aapl", "nasdaq") is True      # normaliza a mayúsculas
    assert cfg["tickers"][-1] == {"symbol": "AAPL", "exchange": "NASDAQ", "screener": "america"}
    assert agregar_ticker(cfg, "AAPL", "NASDAQ") is False     # duplicado
    assert quitar_ticker(cfg, "aapl") is True
    assert [t["symbol"] for t in cfg["tickers"]] == ["SPY"]
    assert quitar_ticker(cfg, "NOEXISTE") is False


def test_guardar_y_recargar_config():
    from prestamos.acciones.config import cargar_config, guardar_config
    ruta = Path(tempfile.mkdtemp()) / "config.yaml"
    cfg = {
        "tickers": [{"symbol": "NVDA", "exchange": "NASDAQ", "screener": "america"}],
        "intervalos": ["1D"], "regla": "only_strong",
    }
    guardar_config(cfg, ruta)
    assert "# Configuración" in ruta.read_text(encoding="utf-8")  # conserva la ayuda
    recargada = cargar_config(ruta)
    assert recargada["tickers"] == cfg["tickers"]
    assert recargada["regla"] == "only_strong"


def test_limpiar_estado_de_simbolo():
    from prestamos.acciones.config import guardar_estado, limpiar_estado_de
    ruta = Path(tempfile.mkdtemp()) / "state.json"
    guardar_estado({"SPY:1D": "BUY", "SPY:1h": "SELL", "NVDA:1D": "BUY"}, ruta)
    limpiar_estado_de("spy", ruta)
    assert cargar_estado(ruta) == {"NVDA:1D": "BUY"}


def test_estado_ida_y_vuelta():
    ruta = Path(tempfile.mkdtemp()) / "state.json"
    guardar_estado({"SPY:1D": "BUY"}, ruta)
    assert cargar_estado(ruta) == {"SPY:1D": "BUY"}
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"SPY:1D": "BUY"}


def test_estado_corrupto_no_rompe():
    ruta = Path(tempfile.mkdtemp()) / "state.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    assert cargar_estado(ruta) == {}
