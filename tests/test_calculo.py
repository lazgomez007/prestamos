"""Valida el motor de cálculo contra el caso obligatorio del prestamista.

Caso:
    Monto S/ 18,000.00 | Tasa mensual 1.4602% | Inicio 1/05/2026 | 12 cuotas
Esperado:
    Cuota fija 1,645.78 | Cuota 1 (31 días): interés 266.00, amort 1,379.78,
    saldo 16,620.22 | Saldo final 0.00

Ejecutar:  py -m pytest tests -v      (o)      py tests/test_calculo.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prestamos.core.calculo import (  # noqa: E402
    generar_cronograma,
    tasa_anual_efectiva,
    total_a_pagar,
)

D = Decimal


def _caso():
    return generar_cronograma(
        monto=D("18000"),
        tasa_mensual=D("0.014602"),
        fecha_inicio=date(2026, 5, 1),
        num_cuotas=12,
    )


def test_tasa_anual_equivale_a_19_por_ciento():
    anual = tasa_anual_efectiva(D("0.014602"))
    assert round(anual * 100, 2) == D("19.00")


def test_cuota_fija():
    _, cuota = _caso()
    assert cuota == D("1645.78")


def test_primera_cuota():
    cuotas, _ = _caso()
    c1 = cuotas[0]
    assert c1.dias == 31
    assert c1.interes == D("266.00")
    assert c1.amortizacion == D("1379.78")
    assert c1.saldo == D("16620.22")


def test_saldo_final_cero():
    cuotas, _ = _caso()
    assert cuotas[-1].saldo == D("0.00")


def test_total_a_pagar_dentro_de_tolerancia():
    # El total teórico es 19,749.34; la referencia del prestamista marca
    # 19,749.33 (difiere 1 céntimo por la convención de redondeo de la última
    # cuota). Validamos que esté dentro de ±0.02 de la referencia.
    cuotas, _ = _caso()
    total = total_a_pagar(cuotas)
    assert abs(total - D("19749.33")) <= D("0.02")


if __name__ == "__main__":
    cuotas, cuota = _caso()
    print(f"Cuota fija: {cuota}")
    print(f"{'N°':>3} {'Fecha':>12} {'Días':>5} {'Interés':>10} "
          f"{'Amort.':>10} {'Cuota':>10} {'Saldo':>12}")
    for c in cuotas:
        print(f"{c.numero:>3} {c.fecha.isoformat():>12} {c.dias:>5} "
              f"{c.interes:>10} {c.amortizacion:>10} {c.cuota:>10} {c.saldo:>12}")
    print(f"Total a pagar: {total_a_pagar(cuotas)}")
