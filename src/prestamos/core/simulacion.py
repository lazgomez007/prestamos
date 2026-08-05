"""Simulación de ampliación de un préstamo.

Permite agregar dinero extra y/o cuotas a partir de una fecha elegida,
recalculando el cronograma desde esa fecha (saldo pendiente + monto nuevo) SIN
alterar el préstamo original.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .calculo import construir_cronograma, redondear, sumar_meses
from .modelos import CuotaRegistro, Prestamo


@dataclass
class ResultadoSimulacion:
    cuotas: list[CuotaRegistro]
    cuota_fija: Decimal
    saldo_base: Decimal
    capital_nuevo: Decimal
    indice_corte: int


def simular_ampliacion(
    prestamo: Prestamo,
    fecha_ampliacion: date,
    monto_extra: Decimal,
    cuotas_agregadas: int,
) -> ResultadoSimulacion:
    monto_extra = Decimal(monto_extra)

    # Las cuotas cuyo vencimiento cae en o antes de la fecha de ampliación se
    # conservan; el recálculo arranca con la siguiente fecha (evita periodos de
    # 0 días cuando la fecha elegida coincide con un vencimiento).
    previas = [c for c in prestamo.cuotas if c.fecha <= fecha_ampliacion]
    saldo_base = previas[-1].saldo if previas else Decimal(prestamo.monto)
    capital_nuevo = redondear(saldo_base + monto_extra)

    cuotas_restantes = prestamo.num_cuotas - len(previas)
    nuevas_cuotas = cuotas_restantes + cuotas_agregadas
    if nuevas_cuotas < 1:
        raise ValueError("El número de cuotas resultante debe ser al menos 1.")

    # Las nuevas cuotas continúan la cadencia mensual original (mismo día del mes).
    p = len(previas)
    nuevas_fechas = [
        sumar_meses(prestamo.fecha_primer_vencimiento, k)
        for k in range(p, p + nuevas_cuotas)
    ]
    fechas = [fecha_ampliacion] + nuevas_fechas

    nuevas, cuota_fija = construir_cronograma(
        capital_nuevo, prestamo.tasa_mensual, prestamo.formula, fechas
    )

    combinadas: list[CuotaRegistro] = []
    for c in previas:
        combinadas.append(
            CuotaRegistro(
                numero=len(combinadas) + 1, fecha=c.fecha, dias=c.dias,
                interes=c.interes, amortizacion=c.amortizacion, cuota=c.cuota,
                saldo=c.saldo, pagada=c.pagada, fecha_pago=c.fecha_pago,
            )
        )
    for c in nuevas:
        combinadas.append(
            CuotaRegistro(
                numero=len(combinadas) + 1, fecha=c.fecha, dias=c.dias,
                interes=c.interes, amortizacion=c.amortizacion, cuota=c.cuota,
                saldo=c.saldo,
            )
        )

    return ResultadoSimulacion(
        cuotas=combinadas, cuota_fija=cuota_fija, saldo_base=saldo_base,
        capital_nuevo=capital_nuevo, indice_corte=len(previas),
    )
