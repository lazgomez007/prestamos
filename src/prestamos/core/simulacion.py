"""Simulación de ampliación de un préstamo.

Permite agregar dinero extra y/o cuotas a partir de una fecha elegida,
recalculando el cronograma desde esa fecha con el saldo pendiente + el monto
nuevo, SIN alterar el préstamo original (la app decide luego si lo guarda).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .calculo import construir_cronograma, fechas_de_cuotas, redondear
from .modelos import CuotaRegistro, Prestamo


@dataclass
class ResultadoSimulacion:
    cuotas: list[CuotaRegistro]      # cronograma combinado (previas + nuevas)
    cuota_fija: Decimal              # nueva cuota fija desde la ampliación
    saldo_base: Decimal             # saldo pendiente en la fecha de ampliación
    capital_nuevo: Decimal          # saldo_base + monto_extra
    indice_corte: int               # nº de cuotas previas conservadas


def simular_ampliacion(
    prestamo: Prestamo,
    fecha_ampliacion: date,
    monto_extra: Decimal,
    cuotas_agregadas: int,
) -> ResultadoSimulacion:
    """Devuelve el cronograma resultante de aplicar la ampliación."""
    monto_extra = Decimal(monto_extra)

    # Cuotas anteriores a la fecha de ampliación: se conservan tal cual.
    previas = [c for c in prestamo.cuotas if c.fecha < fecha_ampliacion]
    saldo_base = previas[-1].saldo if previas else Decimal(prestamo.monto)

    capital_nuevo = redondear(saldo_base + monto_extra)

    # Cuotas que quedaban + las que se agregan.
    cuotas_restantes = prestamo.num_cuotas - len(previas)
    nuevas_cuotas = cuotas_restantes + cuotas_agregadas
    if nuevas_cuotas < 1:
        raise ValueError("El número de cuotas resultante debe ser al menos 1.")

    fechas = [fecha_ampliacion] + fechas_de_cuotas(fecha_ampliacion, nuevas_cuotas)
    nuevas, cuota_fija = construir_cronograma(
        capital_nuevo, prestamo.tasa_mensual, fechas
    )

    # Combinar: previas (conservan su estado de pago) + nuevas, renumerando.
    combinadas: list[CuotaRegistro] = []
    for c in previas:
        combinadas.append(
            CuotaRegistro(
                numero=len(combinadas) + 1,
                fecha=c.fecha,
                dias=c.dias,
                interes=c.interes,
                amortizacion=c.amortizacion,
                cuota=c.cuota,
                saldo=c.saldo,
                pagada=c.pagada,
                fecha_pago=c.fecha_pago,
            )
        )
    for c in nuevas:
        combinadas.append(
            CuotaRegistro(
                numero=len(combinadas) + 1,
                fecha=c.fecha,
                dias=c.dias,
                interes=c.interes,
                amortizacion=c.amortizacion,
                cuota=c.cuota,
                saldo=c.saldo,
            )
        )

    return ResultadoSimulacion(
        cuotas=combinadas,
        cuota_fija=cuota_fija,
        saldo_base=saldo_base,
        capital_nuevo=capital_nuevo,
        indice_corte=len(previas),
    )
