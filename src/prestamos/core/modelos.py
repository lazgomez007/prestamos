"""Modelos de dominio de la aplicación."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# Estados posibles de un préstamo.
ESTADO_AL_DIA = "Al día"
ESTADO_ATRASADO = "Atrasado"
ESTADO_PAGADO = "Pagado"


@dataclass
class Cliente:
    nombre: str
    telefono: str = ""
    email: str = ""
    id: int | None = None


@dataclass
class CuotaRegistro:
    """Una cuota del cronograma tal como se guarda y se sigue su pago."""
    numero: int
    fecha: date
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
    """Registro histórico de una ampliación aplicada a un préstamo."""
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
    fecha_inicio: date
    num_cuotas: int
    notas: str = ""
    estado: str = ESTADO_AL_DIA
    creado_en: date | None = None
    id: int | None = None
    cuotas: list[CuotaRegistro] = field(default_factory=list)
    ampliaciones: list[Ampliacion] = field(default_factory=list)

    def calcular_estado(self, hoy: date | None = None) -> str:
        """Estado calculado a partir de las cuotas y la fecha actual."""
        hoy = hoy or date.today()
        if self.cuotas and all(c.pagada for c in self.cuotas):
            return ESTADO_PAGADO
        if any((not c.pagada) and c.fecha < hoy for c in self.cuotas):
            return ESTADO_ATRASADO
        return ESTADO_AL_DIA

    @property
    def saldo_pendiente(self) -> Decimal:
        """Saldo de la última cuota no pagada (lo que aún debe el cliente)."""
        for c in self.cuotas:
            if not c.pagada:
                # saldo previo a esta cuota = saldo de la cuota anterior
                idx = self.cuotas.index(c)
                if idx == 0:
                    return self.monto
                return self.cuotas[idx - 1].saldo
        return Decimal("0.00")
