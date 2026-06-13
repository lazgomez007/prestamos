"""Agregación mensual para el dashboard de patrimonio.

Reúne, mes por mes y sumando todos los préstamos:
  - interés que es MÍO (excluye la parte de Carrillo),
  - amortización (capital que regresa),
  - saldo de capital pendiente (patrimonio: lo que aún está prestado),
  - impuesto: 5% del interés que gano de Prestamype y Carrillo (no de Propios).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .calculo import desglose_carrillo, redondear
from .modelos import FUENTE_CARRILLO, Prestamo

FUENTE_PRESTAMYPE = "Prestamype"
TASA_IMPUESTO = Decimal("0.05")


def _mes(f: date) -> str:
    return f"{f.year:04d}-{f.month:02d}"


def _mes_siguiente(mes: str) -> str:
    anio, m = int(mes[:4]), int(mes[5:7])
    m += 1
    if m > 12:
        m, anio = 1, anio + 1
    return f"{anio:04d}-{m:02d}"


def _vacio() -> dict:
    return {
        "interes_mio": Decimal(0), "interes_carrillo": Decimal(0),
        "amortizacion": Decimal(0), "base_impuesto": Decimal(0),
    }


def resumen_mensual(
    prestamos: list[Prestamo], tasa_impuesto: Decimal = TASA_IMPUESTO
) -> dict:
    flujo: dict[str, dict] = {}
    # (mes_desembolso, [(mes_cuota, saldo)], monto) por préstamo, para el saldo.
    saldos_prestamo: list[tuple[str, list[tuple[str, Decimal]], Decimal]] = []
    meses: set[str] = set()

    for p in prestamos:
        if not p.cuotas:
            continue
        es_carrillo = (
            p.fuente == FUENTE_CARRILLO and p.tasa_carrillo and p.tasa_carrillo > 0
        )
        if es_carrillo:
            pares = desglose_carrillo(p.monto, p.tasa_carrillo, p.formula, p.cuotas)
        else:
            pares = [(Decimal(0), c.interes) for c in p.cuotas]
        grava = p.fuente in (FUENTE_CARRILLO, FUENTE_PRESTAMYPE)

        for c, (ic, im) in zip(p.cuotas, pares):
            mes = _mes(c.fecha)
            meses.add(mes)
            d = flujo.setdefault(mes, _vacio())
            d["interes_mio"] += im
            d["interes_carrillo"] += ic
            d["amortizacion"] += c.amortizacion
            if grava:
                d["base_impuesto"] += im

        saldos_prestamo.append((
            _mes(p.fecha_desembolso),
            [(_mes(c.fecha), c.saldo) for c in p.cuotas],
            Decimal(p.monto),
        ))
        meses.add(_mes(p.fecha_desembolso))

    if not meses:
        return {"meses": [], "totales": _totales_cero()}

    def saldo_de(desembolso: str, saldos: list[tuple[str, Decimal]], monto: Decimal, mes: str) -> Decimal:
        if mes < desembolso:
            return Decimal(0)
        ultimo = None
        for cm, s in saldos:
            if cm <= mes:
                ultimo = s
            else:
                break
        return ultimo if ultimo is not None else monto

    filas = []
    tot = {"interes_mio": Decimal(0), "interes_carrillo": Decimal(0),
           "amortizacion": Decimal(0), "impuesto": Decimal(0)}
    mes = min(meses)
    fin = max(meses)
    while mes <= fin:
        d = flujo.get(mes, _vacio())
        impuesto = redondear(d["base_impuesto"] * tasa_impuesto)
        saldo = sum(
            (saldo_de(dm, sl, mt, mes) for dm, sl, mt in saldos_prestamo), Decimal(0)
        )
        filas.append({
            "mes": mes,
            "interes_mio": redondear(d["interes_mio"]),
            "interes_carrillo": redondear(d["interes_carrillo"]),
            "amortizacion": redondear(d["amortizacion"]),
            "impuesto": impuesto,
            "saldo_pendiente": redondear(saldo),
        })
        tot["interes_mio"] += d["interes_mio"]
        tot["interes_carrillo"] += d["interes_carrillo"]
        tot["amortizacion"] += d["amortizacion"]
        tot["impuesto"] += impuesto
        mes = _mes_siguiente(mes)

    return {
        "meses": filas,
        "totales": {
            "interes_mio": redondear(tot["interes_mio"]),
            "interes_carrillo": redondear(tot["interes_carrillo"]),
            "amortizacion": redondear(tot["amortizacion"]),
            "impuesto": redondear(tot["impuesto"]),
        },
    }


def _totales_cero() -> dict:
    z = Decimal("0.00")
    return {"interes_mio": z, "interes_carrillo": z, "amortizacion": z, "impuesto": z}
