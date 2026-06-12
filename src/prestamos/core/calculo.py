"""Motor de amortización de préstamos.

Sistema francés (cuota fija) con interés sobre saldo pendiente, ajustado por los
DÍAS REALES de cada periodo mensual.

Conversión de la tasa mensual que ingresa el prestamista:
    tasa_anual_efectiva  = (1 + tasa_mensual) ** 12 - 1
    tasa_diaria_efectiva = (1 + tasa_anual_efectiva) ** (1 / 365) - 1

Interés de cada cuota:
    interes = saldo_pendiente * tasa_diaria_efectiva * dias_del_periodo

La cuota es fija para todas las mensualidades (calculada para que el préstamo se
amortice por completo). La última cuota absorbe el redondeo para dejar saldo 0.

Todo el dinero se maneja con ``Decimal`` y se redondea a 2 decimales con
``ROUND_HALF_UP`` (constante :data:`MODO_REDONDEO`, fácil de ajustar).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, getcontext, ROUND_HALF_UP

# Precisión alta para los cálculos internos de tasas (la presentación se
# redondea aparte a 2 decimales).
getcontext().prec = 50

# --- Constantes de redondeo del dinero -------------------------------------
CENTIMO = Decimal("0.01")
MODO_REDONDEO = ROUND_HALF_UP
DIAS_ANIO = Decimal(365)
MESES_ANIO = 12


def redondear(valor: Decimal) -> Decimal:
    """Redondea un importe a 2 decimales con el modo configurado."""
    return Decimal(valor).quantize(CENTIMO, rounding=MODO_REDONDEO)


# --- Conversión de tasas ----------------------------------------------------
def tasa_anual_efectiva(tasa_mensual: Decimal) -> Decimal:
    """(1 + tasa_mensual) ** 12 - 1."""
    uno = Decimal(1)
    return (uno + Decimal(tasa_mensual)) ** MESES_ANIO - uno


def tasa_diaria_efectiva(tasa_mensual: Decimal) -> Decimal:
    """(1 + tasa_anual_efectiva) ** (1 / 365) - 1."""
    uno = Decimal(1)
    anual = tasa_anual_efectiva(tasa_mensual)
    # x ** (1/365) = exp(ln(x) / 365), exacto en la precisión del contexto.
    return ((uno + anual).ln() / DIAS_ANIO).exp() - uno


# --- Utilidades de fechas ---------------------------------------------------
def sumar_meses(fecha: date, meses: int) -> date:
    """Suma ``meses`` a ``fecha`` conservando el día; si el mes destino no tiene
    ese día (p. ej. 31 de enero + 1 mes), usa el último día del mes."""
    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    # Último día del mes destino.
    if mes == 12:
        ultimo = 31
    else:
        ultimo = (date(anio, mes + 1, 1) - date(anio, mes, 1)).days
    dia = min(fecha.day, ultimo)
    return date(anio, mes, dia)


def fechas_de_cuotas(fecha_inicio: date, num_cuotas: int) -> list[date]:
    """Lista de fechas de pago: el mismo día de cada mes a partir del inicio."""
    return [sumar_meses(fecha_inicio, k) for k in range(1, num_cuotas + 1)]


# --- Estructura de una fila del cronograma ----------------------------------
@dataclass
class Cuota:
    numero: int
    fecha: date
    dias: int
    interes: Decimal
    amortizacion: Decimal
    cuota: Decimal
    saldo: Decimal


def calcular_cuota_fija(
    saldo_inicial: Decimal, tasa_diaria: Decimal, dias_periodos: list[int]
) -> Decimal:
    """Cuota fija que amortiza ``saldo_inicial`` en los periodos dados.

    Con tasas por periodo r_i = tasa_diaria * dias_i, el saldo evoluciona como
    B_i = B_{i-1} * (1 + r_i) - C. Imponiendo B_n = 0:

        C = saldo_inicial * Π(1 + r_i) / Σ_i [ Π_{j>i}(1 + r_j) ]
    """
    factores = [Decimal(1) + tasa_diaria * Decimal(d) for d in dias_periodos]
    sufijo = Decimal(1)  # producto de los factores posteriores al periodo i
    suma = Decimal(0)
    for f in reversed(factores):
        suma += sufijo
        sufijo *= f
    producto_total = sufijo  # Π de todos los factores
    return redondear(saldo_inicial * producto_total / suma)


def construir_cronograma(
    saldo_inicial: Decimal, tasa_mensual: Decimal, fechas: list[date]
) -> tuple[list[Cuota], Decimal]:
    """Genera el cronograma a partir de un saldo y una lista de fechas.

    ``fechas[0]`` es la fecha base (inicio del primer periodo) y ``fechas[1:]``
    son las fechas de cada cuota. Devuelve ``(cuotas, cuota_fija)``.
    """
    if len(fechas) < 2:
        raise ValueError("Se requieren al menos una fecha base y una de cuota.")

    saldo_inicial = Decimal(saldo_inicial)
    tasa_mensual = Decimal(tasa_mensual)
    d = tasa_diaria_efectiva(tasa_mensual)

    dias_periodos = [(fechas[i + 1] - fechas[i]).days for i in range(len(fechas) - 1)]
    n = len(dias_periodos)
    cuota_fija = calcular_cuota_fija(saldo_inicial, d, dias_periodos)

    filas: list[Cuota] = []
    saldo = saldo_inicial
    for i in range(n):
        interes = redondear(saldo * d * Decimal(dias_periodos[i]))
        if i == n - 1:
            # La última cuota amortiza todo el saldo restante.
            amortizacion = saldo
            cuota = redondear(amortizacion + interes)
        else:
            cuota = cuota_fija
            amortizacion = redondear(cuota - interes)
        saldo = redondear(saldo - amortizacion)
        filas.append(
            Cuota(
                numero=i + 1,
                fecha=fechas[i + 1],
                dias=dias_periodos[i],
                interes=interes,
                amortizacion=amortizacion,
                cuota=cuota,
                saldo=saldo,
            )
        )
    return filas, cuota_fija


def generar_cronograma(
    monto: Decimal, tasa_mensual: Decimal, fecha_inicio: date, num_cuotas: int
) -> tuple[list[Cuota], Decimal]:
    """Cronograma de un préstamo nuevo (cuotas mensuales desde la fecha de inicio)."""
    fechas = [fecha_inicio] + fechas_de_cuotas(fecha_inicio, num_cuotas)
    return construir_cronograma(monto, tasa_mensual, fechas)


def total_a_pagar(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.cuota for c in cuotas), Decimal(0)))


def total_interes(cuotas: list[Cuota]) -> Decimal:
    return redondear(sum((c.interes for c in cuotas), Decimal(0)))
