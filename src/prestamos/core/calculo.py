"""Motor de amortización de préstamos.

Sistema francés (cuota fija) con interés sobre saldo pendiente, ajustado por los
DÍAS REALES de cada periodo. La tasa se ingresa MENSUAL y por préstamo, y se
elige por préstamo una de dos fórmulas para el interés:

FÓRMULA A (efectiva, por defecto):
    tasa_anual = (1 + tasa_mensual) ** 12 - 1
    tasa_dia   = (1 + tasa_anual) ** (1 / 365) - 1
    interes    = saldo * tasa_dia * dias_periodo

FÓRMULA B (simple):
    interes    = saldo * (tasa_mensual / 30) * dias_periodo

``dias_periodo`` = días reales entre la fecha anterior (o la fecha de desembolso,
para la primera cuota) y la fecha de vencimiento de la cuota.

La cuota es fija para todas las mensualidades (calculada para amortizar el total)
y la última cuota absorbe el redondeo para dejar saldo 0. El dinero se maneja con
``Decimal`` y se redondea a 2 decimales con ``ROUND_HALF_UP`` (``MODO_REDONDEO``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, getcontext, ROUND_HALF_UP

getcontext().prec = 50

CENTIMO = Decimal("0.01")
MODO_REDONDEO = ROUND_HALF_UP
DIAS_ANIO = Decimal(365)
MESES_ANIO = 12
DIAS_MES_SIMPLE = Decimal(30)

FORMULA_EFECTIVA = "A"
FORMULA_SIMPLE = "B"


def redondear(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTIMO, rounding=MODO_REDONDEO)


# --- Tasas ------------------------------------------------------------------
def tasa_anual_efectiva(tasa_mensual: Decimal) -> Decimal:
    uno = Decimal(1)
    return (uno + Decimal(tasa_mensual)) ** MESES_ANIO - uno


def tasa_por_dia(tasa_mensual: Decimal, formula: str) -> Decimal:
    """Tasa de interés por UN día, según la fórmula elegida."""
    tasa_mensual = Decimal(tasa_mensual)
    if formula == FORMULA_SIMPLE:
        return tasa_mensual / DIAS_MES_SIMPLE
    # Fórmula A (efectiva), por defecto.
    uno = Decimal(1)
    anual = tasa_anual_efectiva(tasa_mensual)
    return ((uno + anual).ln() / DIAS_ANIO).exp() - uno


# --- Fechas -----------------------------------------------------------------
def sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses conservando el día; ajusta al último día si el mes es más corto."""
    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    if mes == 12:
        ultimo = 31
    else:
        ultimo = (date(anio, mes + 1, 1) - date(anio, mes, 1)).days
    return date(anio, mes, min(fecha.day, ultimo))


def fechas_vencimiento(primer_vencimiento: date, num_cuotas: int) -> list[date]:
    """Fechas de cuotas: la primera es la elegida; las siguientes el mismo día
    de cada mes."""
    return [sumar_meses(primer_vencimiento, k) for k in range(num_cuotas)]


# --- Cronograma -------------------------------------------------------------
@dataclass
class Cuota:
    numero: int
    fecha: date          # fecha de vencimiento
    dias: int
    interes: Decimal
    amortizacion: Decimal
    cuota: Decimal
    saldo: Decimal


def calcular_cuota_fija(saldo_inicial: Decimal, tasas_periodo: list[Decimal]) -> Decimal:
    """Cuota fija que amortiza el saldo con las tasas por periodo r_i.

        C = saldo * Π(1 + r_i) / Σ_i [ Π_{j>i}(1 + r_j) ]
    """
    factores = [Decimal(1) + r for r in tasas_periodo]
    sufijo = Decimal(1)
    suma = Decimal(0)
    for f in reversed(factores):
        suma += sufijo
        sufijo *= f
    producto_total = sufijo
    return redondear(saldo_inicial * producto_total / suma)


def construir_cronograma(
    saldo_inicial: Decimal,
    tasa_mensual: Decimal,
    formula: str,
    fechas: list[date],
) -> tuple[list[Cuota], Decimal]:
    """Genera el cronograma. ``fechas[0]`` es la fecha base (desembolso o fecha
    de ampliación) y ``fechas[1:]`` son las fechas de vencimiento de cada cuota.
    """
    if len(fechas) < 2:
        raise ValueError("Se requieren al menos una fecha base y una de cuota.")

    saldo_inicial = Decimal(saldo_inicial)
    dias_periodos = [(fechas[i + 1] - fechas[i]).days for i in range(len(fechas) - 1)]
    if any(d <= 0 for d in dias_periodos):
        raise ValueError("Las fechas deben ser crecientes (días de periodo > 0).")

    diaria = tasa_por_dia(tasa_mensual, formula)
    tasas_periodo = [diaria * Decimal(d) for d in dias_periodos]
    n = len(dias_periodos)
    cuota_fija = calcular_cuota_fija(saldo_inicial, tasas_periodo)

    filas: list[Cuota] = []
    saldo = saldo_inicial
    for i in range(n):
        interes = redondear(saldo * tasas_periodo[i])
        if i == n - 1:
            amortizacion = saldo
            cuota = redondear(amortizacion + interes)
        else:
            cuota = cuota_fija
            amortizacion = redondear(cuota - interes)
        saldo = redondear(saldo - amortizacion)
        filas.append(
            Cuota(i + 1, fechas[i + 1], dias_periodos[i], interes, amortizacion, cuota, saldo)
        )
    return filas, cuota_fija


def generar_cronograma(
    monto: Decimal,
    tasa_mensual: Decimal,
    formula: str,
    fecha_desembolso: date,
    fecha_primer_vencimiento: date,
    num_cuotas: int,
) -> tuple[list[Cuota], Decimal]:
    """Cronograma de un préstamo nuevo, con primer vencimiento flexible."""
    fechas = [fecha_desembolso] + fechas_vencimiento(fecha_primer_vencimiento, num_cuotas)
    return construir_cronograma(monto, tasa_mensual, formula, fechas)


def total_a_pagar(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.cuota for c in cuotas), Decimal(0)))


def total_interes(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.interes for c in cuotas), Decimal(0)))
