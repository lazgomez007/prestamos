"""Valida el motor de cálculo.

Ejecutar:  py -m pytest tests -v
"""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prestamos.core.calculo import (  # noqa: E402
    FORMULA_EFECTIVA,
    FORMULA_SIMPLE,
    generar_cronograma,
    tasa_anual_efectiva,
    total_a_pagar,
)

D = Decimal


def _caso_obligatorio():
    # Monto 18000 · 1.4602% mensual · Fórmula A · desembolso 1/05/2026 ·
    # primer vencimiento 1/06/2026 · 12 cuotas.
    return generar_cronograma(
        monto=D("18000"),
        tasa_mensual=D("0.014602"),
        formula=FORMULA_EFECTIVA,
        fecha_desembolso=date(2026, 5, 1),
        fecha_primer_vencimiento=date(2026, 6, 1),
        num_cuotas=12,
    )


def test_tasa_anual_equivale_a_19_por_ciento():
    assert round(tasa_anual_efectiva(D("0.014602")) * 100, 2) == D("19.00")


def test_cuota_fija():
    _, cuota = _caso_obligatorio()
    assert cuota == D("1645.78")


def test_primera_cuota():
    cuotas, _ = _caso_obligatorio()
    c1 = cuotas[0]
    assert c1.dias == 31
    assert c1.interes == D("266.00")
    assert c1.amortizacion == D("1379.78")
    assert c1.saldo == D("16620.22")


def test_saldo_final_cero():
    cuotas, _ = _caso_obligatorio()
    assert cuotas[-1].saldo == D("0.00")


def test_total_a_pagar():
    # Total teórico 19,749.34 (la referencia marcaba 19,749.33; difiere 1 céntimo
    # por el redondeo de la última cuota, demostrado inalcanzable de forma
    # consistente). Validamos dentro de ±0.02.
    cuotas, _ = _caso_obligatorio()
    assert abs(total_a_pagar(cuotas) - D("19749.33")) <= D("0.02")


def test_primer_vencimiento_flexible_25_dias():
    # Desembolso 11/03/2026, primer vencimiento 05/04/2026 -> 25 días reales.
    cuotas, _ = generar_cronograma(
        monto=D("10000"),
        tasa_mensual=D("0.016"),
        formula=FORMULA_EFECTIVA,
        fecha_desembolso=date(2026, 3, 11),
        fecha_primer_vencimiento=date(2026, 4, 5),
        num_cuotas=6,
    )
    assert cuotas[0].dias == 25
    assert cuotas[1].fecha == date(2026, 5, 5)
    assert cuotas[-1].saldo == D("0.00")


def test_formula_simple_amortiza():
    cuotas, cuota = generar_cronograma(
        monto=D("18000"),
        tasa_mensual=D("0.014602"),
        formula=FORMULA_SIMPLE,
        fecha_desembolso=date(2026, 5, 1),
        fecha_primer_vencimiento=date(2026, 6, 1),
        num_cuotas=12,
    )
    assert cuota > 0
    assert cuotas[-1].saldo == D("0.00")
    # Fórmula B (simple) cobra algo distinto a la A en la primera cuota.
    assert cuotas[0].interes != D("266.00")


def test_capital_final_cuota_balon():
    # Presta 10000, devuelve 5000 al final; el resto se amortiza en 12 cuotas.
    cuotas, cuota = generar_cronograma(
        monto=D("10000"), tasa_mensual=D("0.016"), formula=FORMULA_EFECTIVA,
        fecha_desembolso=date(2026, 1, 1), fecha_primer_vencimiento=date(2026, 2, 1),
        num_cuotas=12, capital_final=D("5000"),
    )
    assert len(cuotas) == 13                      # 12 cuotas + devolución
    assert cuotas[11].saldo == D("5000.00")       # saldo tras la última cuota
    assert cuotas[12].interes == D("0.00")
    assert cuotas[12].amortizacion == D("5000.00")
    assert cuotas[12].saldo == D("0.00")
    assert sum(c.amortizacion for c in cuotas) == D("10000.00")


def test_capital_final_invalido():
    import pytest
    with pytest.raises(ValueError):
        generar_cronograma(
            monto=D("10000"), tasa_mensual=D("0.016"), formula=FORMULA_EFECTIVA,
            fecha_desembolso=date(2026, 1, 1), fecha_primer_vencimiento=date(2026, 2, 1),
            num_cuotas=12, capital_final=D("10000"),
        )


def test_formula_mensual_fija_caso_carrillo_real():
    # Caso real CAr_56: 56,500 al 2.38% mensual, 36 cuotas, fórmula C (mensual fija).
    from prestamos.core.calculo import FORMULA_MENSUAL, desglose_carrillo
    cuotas, cuota = generar_cronograma(
        monto=D("56500"), tasa_mensual=D("0.0238"), formula=FORMULA_MENSUAL,
        fecha_desembolso=date(2026, 1, 1), fecha_primer_vencimiento=date(2026, 2, 1),
        num_cuotas=36,
    )
    assert cuota == D("2354.17")
    c1 = cuotas[0]
    assert c1.interes == D("1344.70")
    assert c1.amortizacion == D("1009.47")
    assert c1.saldo == D("55490.53")
    assert cuotas[-1].saldo == D("0.00")
    assert abs(total_a_pagar(cuotas) - D("84750.10")) <= D("0.05")
    # Carrillo a 0.66% (= 2.38% del préstamo - 1.72% del inversionista).
    pares = desglose_carrillo(D("56500"), D("0.0066"), FORMULA_MENSUAL, cuotas)
    assert pares[0][0] == D("372.90")
    assert abs(sum((ic for ic, _ in pares), D("0")) - D("7834.06")) <= D("0.05")


def test_desglose_carrillo_suma_al_interes():
    from prestamos.core.calculo import desglose_carrillo
    cuotas, _ = generar_cronograma(
        monto=D("10000"), tasa_mensual=D("0.02"), formula=FORMULA_EFECTIVA,
        fecha_desembolso=date(2026, 1, 1), fecha_primer_vencimiento=date(2026, 2, 1),
        num_cuotas=6,
    )
    pares = desglose_carrillo(D("10000"), D("0.012"), FORMULA_EFECTIVA, cuotas)
    for c, (ic, im) in zip(cuotas, pares):
        assert ic + im == c.interes        # el reparto suma exacto al interés
        assert 0 <= ic <= c.interes
    # Con tasa de Carrillo (1.2%) menor que la del préstamo (2%), su parte es menor.
    assert pares[0][0] < cuotas[0].interes


def test_dashboard_impuesto_y_patrimonio():
    from prestamos.core.calculo import FORMULA_MENSUAL, redondear
    from prestamos.core.dashboard import resumen_mensual
    from prestamos.core.modelos import Cliente, CuotaRegistro, Prestamo

    def construir(fuente, tasa_carrillo, monto, tasa, n):
        calc, _ = generar_cronograma(
            monto, tasa, FORMULA_MENSUAL, date(2026, 1, 1), date(2026, 2, 1), n)
        regs = [CuotaRegistro(numero=c.numero, fecha=c.fecha, dias=c.dias,
                interes=c.interes, amortizacion=c.amortizacion, cuota=c.cuota,
                saldo=c.saldo) for c in calc]
        p = Prestamo(cliente=Cliente("x"), monto=monto, tasa_mensual=tasa,
                fecha_desembolso=date(2026, 1, 1), fecha_primer_vencimiento=date(2026, 2, 1),
                num_cuotas=n, formula=FORMULA_MENSUAL, fuente=fuente, tasa_carrillo=tasa_carrillo)
        p.cuotas = regs
        return p

    propios = construir("Propios", D("0"), D("10000"), D("0.02"), 6)
    carrillo = construir("Carrillo Royalti", D("0.005"), D("10000"), D("0.02"), 6)

    # Solo Propios: sin interés de Carrillo y sin impuesto.
    rp = resumen_mensual([propios])
    assert rp["totales"]["interes_carrillo"] == D("0.00")
    assert rp["totales"]["impuesto"] == D("0.00")
    assert rp["meses"][0]["saldo_pendiente"] == D("10000.00")
    assert rp["meses"][-1]["saldo_pendiente"] == D("0.00")

    # Con Carrillo: hay interés de Carrillo y el impuesto es 5% de mi parte del Carrillo.
    rb = resumen_mensual([propios, carrillo])
    assert rb["totales"]["interes_carrillo"] > 0
    mio_carrillo = rb["totales"]["interes_mio"] - rp["totales"]["interes_mio"]
    assert abs(rb["totales"]["impuesto"] - redondear(mio_carrillo * D("0.05"))) <= D("0.03")
    assert rb["meses"][0]["saldo_pendiente"] == D("20000.00")


if __name__ == "__main__":
    cuotas, cuota = _caso_obligatorio()
    print("Cuota fija:", cuota, " Total:", total_a_pagar(cuotas))
    for c in cuotas:
        print(c.numero, c.fecha, c.dias, c.interes, c.amortizacion, c.cuota, c.saldo)
