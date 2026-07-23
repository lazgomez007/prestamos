"""Consulta del resumen técnico de TradingView (semáforo tipo Investing.com).

Usa la librería `tradingview-ta` (gratis, sin API key). Agrupa las consultas por
temporalidad para pedir todos los tickers en una sola llamada.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

# Algunos antivirus (p. ej. Norton) interceptan HTTPS con su propio certificado.
# truststore usa el almacén de certificados del sistema y evita el error SSL.
try:  # pragma: no cover - depende del entorno
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    pass

import tradingview_ta.main as _tv_main
from tradingview_ta import Interval, get_multiple_analysis

log = logging.getLogger(__name__)

# La librería envía "User-Agent: tradingview_ta/x.y" en TODAS sus instalaciones,
# así que su cuota la comparten miles de usuarios y devuelve 429 casi siempre.
# Identificamos nuestra app con su propio nombre (sin suplantar a un navegador)
# y mantenemos un volumen bajo (caché + monitor por hora).
USER_AGENT = "GestorPrestamos/1.0 (monitor personal)"


class LimiteTradingView(Exception):
    """TradingView respondió 429 (demasiadas consultas)."""


class _ClienteHTTP:
    """Envuelve `requests` para fijar nuestro User-Agent y detectar el 429."""

    def __init__(self, real):
        self._real = real

    def post(self, url, **kw):
        cabeceras = dict(kw.pop("headers", None) or {})
        cabeceras["User-Agent"] = USER_AGENT
        respuesta = self._real.post(url, headers=cabeceras, **kw)
        if respuesta.status_code == 429:
            espera = respuesta.headers.get("Retry-After")
            raise LimiteTradingView(
                f"429 Too Many Requests{f' (reintentar en {espera}s)' if espera else ''}"
            )
        return respuesta

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)


_tv_main.requests = _ClienteHTTP(_tv_main.requests)

INTERVALOS = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "30m": Interval.INTERVAL_30_MINUTES,
    "1h": Interval.INTERVAL_1_HOUR,
    "2h": Interval.INTERVAL_2_HOURS,
    "4h": Interval.INTERVAL_4_HOURS,
    "1D": Interval.INTERVAL_1_DAY,
    "1W": Interval.INTERVAL_1_WEEK,
    "1M": Interval.INTERVAL_1_MONTH,
}

# Nombres amigables de cada temporalidad (estilo Investing.com).
ETIQUETAS_INTERVALO = {
    "1m": "1 min", "5m": "5 min", "15m": "15 min", "30m": "30 min",
    "1h": "1 hora", "2h": "2 horas", "4h": "4 horas",
    "1D": "Diario", "1W": "Semanal", "1M": "Mensual",
}

SENALES = ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
SENALES_FUERTES = {"STRONG_BUY", "STRONG_SELL"}

ETIQUETAS = {
    "STRONG_BUY": "Compra fuerte",
    "BUY": "Compra",
    "NEUTRAL": "Neutral",
    "SELL": "Venta",
    "STRONG_SELL": "Venta fuerte",
}


@dataclass
class Lectura:
    """Resultado del resumen técnico de un ticker en una temporalidad."""
    symbol: str
    exchange: str
    intervalo: str
    recomendacion: str | None = None
    compra: int = 0
    neutral: int = 0
    venta: int = 0
    error: str = ""

    @property
    def clave(self) -> str:
        return f"{self.symbol}:{self.intervalo}"

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS.get(self.recomendacion or "", "—")

    def como_dict(self) -> dict:
        return {
            "symbol": self.symbol, "exchange": self.exchange,
            "intervalo": self.intervalo, "recomendacion": self.recomendacion,
            "etiqueta": self.etiqueta, "compra": self.compra,
            "neutral": self.neutral, "venta": self.venta, "error": self.error,
        }


# Bolsas de EE.UU. (todas con sede en Nueva York). NASDAQ y NYSE son distintas;
# AMEX es la antigua American Stock Exchange (hoy NYSE American).
EXCHANGES_US = ["NASDAQ", "NYSE", "AMEX"]


def detectar_exchange(symbol: str, screener: str = "america") -> str | None:
    """Averigua en qué bolsa de EE.UU. cotiza un símbolo.

    Prueba NASDAQ / NYSE / AMEX en una sola llamada. Devuelve el exchange donde
    hay datos, o None si no se encontró.
    """
    symbol = symbol.strip().upper()
    simbolos = [f"{e}:{symbol}" for e in EXCHANGES_US]
    try:
        res = get_multiple_analysis(
            screener=screener, interval=Interval.INTERVAL_1_DAY, symbols=simbolos
        )
    except Exception as e:
        log.error("Error buscando %s: %s", symbol, e)
        return None
    for exch in EXCHANGES_US:
        analisis = res.get(f"{exch}:{symbol}")
        if analisis is not None and getattr(analisis, "summary", None):
            return exch
    return None


def _mensaje_error(e: Exception) -> str:
    """Traduce errores técnicos a algo entendible."""
    if isinstance(e, LimiteTradingView):
        return "TradingView limitó las consultas (429). Espera un momento y actualiza."
    if isinstance(e, json.JSONDecodeError):
        return "TradingView no respondió (límite de consultas). Espera unos segundos."
    nombre = type(e).__name__
    if "SSL" in nombre:
        return "Error SSL (antivirus interceptando HTTPS)."
    if "Timeout" in nombre or "Connection" in nombre:
        return "Sin conexión con TradingView."
    return f"{nombre}: {e}"


def _consultar_lote(screener: str, iv: str, simbolos: list[str], reintentos: int = 2):
    """Llama a TradingView reintentando con espera creciente si falla."""
    for intento in range(reintentos + 1):
        try:
            return get_multiple_analysis(screener=screener, interval=iv, symbols=simbolos)
        except Exception as e:
            if intento >= reintentos:
                raise
            espera = 1.5 * (intento + 1)
            log.warning("Reintento %d en %.1fs (%s)", intento + 1, espera, e)
            time.sleep(espera)


def consultar(
    tickers: list[dict], intervalos: list[str], pausa: float = 1.0
) -> list[Lectura]:
    """Consulta el resumen técnico de cada (ticker, intervalo).

    ``tickers``: [{"symbol": "SPY", "exchange": "AMEX", "screener": "america"}, ...]
    Devuelve una lista de :class:`Lectura` (con ``error`` si algo falló).
    """
    lecturas: list[Lectura] = []
    for intervalo in intervalos:
        iv = INTERVALOS.get(intervalo)
        if iv is None:
            log.error("Intervalo no soportado: %s", intervalo)
            for t in tickers:
                lecturas.append(Lectura(t["symbol"], t["exchange"], intervalo,
                                        error=f"intervalo no soportado: {intervalo}"))
            continue

        por_screener: dict[str, list[dict]] = {}
        for t in tickers:
            por_screener.setdefault(t.get("screener", "america"), []).append(t)

        for screener, grupo in por_screener.items():
            simbolos = [f"{t['exchange']}:{t['symbol']}" for t in grupo]
            try:
                res = _consultar_lote(screener, iv, simbolos)
            except Exception as e:  # red, timeout, límite de consultas...
                log.error("Error consultando %s %s: %s", screener, intervalo, e)
                mensaje = _mensaje_error(e)
                for t in grupo:
                    lecturas.append(Lectura(t["symbol"], t["exchange"], intervalo,
                                            error=mensaje))
                continue

            for t in grupo:
                analisis = res.get(f"{t['exchange']}:{t['symbol']}")
                resumen = getattr(analisis, "summary", None) if analisis else None
                if not resumen:
                    log.warning("Sin datos para %s:%s (%s)",
                                t["exchange"], t["symbol"], intervalo)
                    lecturas.append(Lectura(t["symbol"], t["exchange"], intervalo,
                                            error="sin datos (símbolo o mercado)"))
                    continue
                lecturas.append(Lectura(
                    symbol=t["symbol"], exchange=t["exchange"], intervalo=intervalo,
                    recomendacion=resumen.get("RECOMMENDATION"),
                    compra=int(resumen.get("BUY", 0)),
                    neutral=int(resumen.get("NEUTRAL", 0)),
                    venta=int(resumen.get("SELL", 0)),
                ))
            if pausa:
                time.sleep(pausa)
    return lecturas
