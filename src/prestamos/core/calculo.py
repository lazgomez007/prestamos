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
FORMULA_MENSUAL = "C"   # mensual fija: interés = saldo * tasa_mensual (sin días)


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


def tasas_de_periodo(
    tasa_mensual: Decimal, formula: str, dias_periodos: list[int]
) -> list[Decimal]:
    """Tasa aplicada en cada periodo, según la fórmula.

    - A / B: tasa por día * días reales del periodo.
    - C (mensual fija): la tasa mensual completa por periodo, sin contar días.
    """
    tasa_mensual = Decimal(tasa_mensual)
    if formula == FORMULA_MENSUAL:
        return [tasa_mensual for _ in dias_periodos]
    diaria = tasa_por_dia(tasa_mensual, formula)
    return [diaria * Decimal(d) for d in dias_periodos]


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


def calcular_cuota_fija(
    saldo_inicial: Decimal,
    tasas_periodo: list[Decimal],
    capital_final: Decimal = Decimal(0),
) -> Decimal:
    """Cuota fija que amortiza el saldo hasta ``capital_final`` con las tasas r_i.

        C = (saldo * Π(1 + r_i) - capital_final) / Σ_i [ Π_{j>i}(1 + r_j) ]

    Con ``capital_final = 0`` amortiza por completo (préstamo normal).
    """
    factores = [Decimal(1) + r for r in tasas_periodo]
    sufijo = Decimal(1)
    suma = Decimal(0)
    for f in reversed(factores):
        suma += sufijo
        sufijo *= f
    producto_total = sufijo
    return redondear((saldo_inicial * producto_total - Decimal(capital_final)) / suma)


def construir_cronograma(
    saldo_inicial: Decimal,
    tasa_mensual: Decimal,
    formula: str,
    fechas: list[date],
    capital_final: Decimal = Decimal(0),
) -> tuple[list[Cuota], Decimal]:
    """Genera el cronograma. ``fechas[0]`` es la fecha base (desembolso o fecha
    de ampliación) y ``fechas[1:]`` son las fechas de vencimiento de cada cuota.

    Si ``capital_final > 0``, las cuotas amortizan hasta ese saldo y se añade una
    fila final de "devolución de capital" (cuota balón) que lo cancela.
    """
    if len(fechas) < 2:
        raise ValueError("Se requieren al menos una fecha base y una de cuota.")

    saldo_inicial = Decimal(saldo_inicial)
    capital_final = Decimal(capital_final)
    if capital_final < 0:
        raise ValueError("La devolución de capital no puede ser negativa.")
    if capital_final >= saldo_inicial:
        raise ValueError("La devolución de capital debe ser menor que el monto.")

    dias_periodos = [(fechas[i + 1] - fechas[i]).days for i in range(len(fechas) - 1)]
    if any(d <= 0 for d in dias_periodos):
        raise ValueError("Las fechas deben ser crecientes (días de periodo > 0).")

    tasas_periodo = tasas_de_periodo(tasa_mensual, formula, dias_periodos)
    n = len(dias_periodos)
    cuota_fija = calcular_cuota_fija(saldo_inicial, tasas_periodo, capital_final)

    filas: list[Cuota] = []
    saldo = saldo_inicial
    for i in range(n):
        interes = redondear(saldo * tasas_periodo[i])
        if i == n - 1:
            # Última cuota regular: deja el saldo justo en capital_final.
            amortizacion = redondear(saldo - capital_final)
            cuota = redondear(amortizacion + interes)
        else:
            cuota = cuota_fija
            amortizacion = redondear(cuota - interes)
        saldo = redondear(saldo - amortizacion)
        filas.append(
            Cuota(i + 1, fechas[i + 1], dias_periodos[i], interes, amortizacion, cuota, saldo)
        )

    # Fila final de devolución del saldo de capital (cuota balón).
    if capital_final > 0:
        filas.append(
            Cuota(n + 1, fechas[n], 0, Decimal("0.00"), saldo, saldo, Decimal("0.00"))
        )

    return filas, cuota_fija


def generar_cronograma(
    monto: Decimal,
    tasa_mensual: Decimal,
    formula: str,
    fecha_desembolso: date,
    fecha_primer_vencimiento: date,
    num_cuotas: int,
    capital_final: Decimal = Decimal(0),
) -> tuple[list[Cuota], Decimal]:
    """Cronograma de un préstamo nuevo, con primer vencimiento flexible."""
    fechas = [fecha_desembolso] + fechas_vencimiento(fecha_primer_vencimiento, num_cuotas)
    return construir_cronograma(monto, tasa_mensual, formula, fechas, capital_final)


def desglose_carrillo(
    saldo_inicial: Decimal,
    tasa_carrillo: Decimal,
    formula: str,
    cuotas: list[Cuota],
) -> list[tuple[Decimal, Decimal]]:
    """Reparte el interés de cada cuota entre Carrillo y el prestamista.

    El interés de Carrillo se calcula igual que el del préstamo (misma fórmula)
    pero con su tasa mensual, sobre el mismo saldo. Devuelve
    [(interes_carrillo, interes_mio)].
    """
    dias = [c.dias for c in cuotas]
    tasas = tasas_de_periodo(tasa_carrillo, formula, dias)
    saldo_prev = Decimal(saldo_inicial)
    salida: list[tuple[Decimal, Decimal]] = []
    for c, r in zip(cuotas, tasas):
        ic = redondear(saldo_prev * r)
        if ic > c.interes:  # no puede exceder el interés total cobrado
            ic = c.interes
        salida.append((ic, redondear(c.interes - ic)))
        saldo_prev = c.saldo
    return salida


def total_a_pagar(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.cuota for c in cuotas), Decimal(0)))


def total_interes(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.interes for c in cuotas), Decimal(0)))
