"""Modelos de dominio de la aplicación."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .calculo import FORMULA_EFECTIVA

ESTADO_AL_DIA = "Al día"
ESTADO_ATRASADO = "Atrasado"
ESTADO_PAGADO = "Pagado"

# Fuente / entidad que origina el préstamo.
FUENTE_PROPIOS = "Propios"
FUENTES = [FUENTE_PROPIOS, "Carrillo Royalti", "Prestamype"]


@dataclass
class Cliente:
    nombre: str
    telefono: str = ""
    email: str = ""
    id: int | None = None


@dataclass
class CuotaRegistro:
    numero: int
    fecha: date                 # fecha de vencimiento
    dias: int
    interes: Decimal
    amortizacion: Decimal
    cuota: Decimal
    saldo: Decimal
    pagada: bool = False
    fecha_pago: date | None = None
    id: int | None = None


@dataclass
class Ampliacion:
    fecha: date
    monto_extra: Decimal
    cuotas_agregadas: int
    detalle: str = ""
    creada_en: date | None = None
    id: int | None = None


@dataclass
class Prestamo:
    cliente: Cliente
    monto: Decimal
    tasa_mensual: Decimal
    fecha_desembolso: date
    fecha_primer_vencimiento: date
    num_cuotas: int
    formula: str = FORMULA_EFECTIVA
    fuente: str = FUENTE_PROPIOS
    capital_final: Decimal = Decimal("0")
    notas: str = ""
    estado: str = ESTADO_AL_DIA
    creado_en: date | None = None
    id: int | None = None
    cuotas: list[CuotaRegistro] = field(default_factory=list)
    ampliaciones: list[Ampliacion] = field(default_factory=list)

    def calcular_estado(self, hoy: date | None = None) -> str:
        hoy = hoy or date.today()
        if self.cuotas and all(c.pagada for c in self.cuotas):
            return ESTADO_PAGADO
        if any((not c.pagada) and c.fecha < hoy for c in self.cuotas):
            return ESTADO_ATRASADO
        return ESTADO_AL_DIA

    @property
    def saldo_pendiente(self) -> Decimal:
        for idx, c in enumerate(self.cuotas):
            if not c.pagada:
                return self.monto if idx == 0 else self.cuotas[idx - 1].saldo
        return Decimal("0.00")
