"""Acceso a datos: crear/leer/editar préstamos, pagos y ampliaciones."""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from ..core.calculo import generar_cronograma
from ..core.modelos import (
    Ampliacion,
    Cliente,
    CuotaRegistro,
    Prestamo,
)
from ..core.simulacion import simular_ampliacion
from .db import conectar


def _d(valor) -> Decimal:
    return Decimal(str(valor))


def _fecha(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


class Repositorio:
    """Fachada sobre la base de datos SQLite."""

    def __init__(self, con: sqlite3.Connection | None = None):
        self.con = con or conectar()

    def cerrar(self) -> None:
        self.con.close()

    # --- Clientes ----------------------------------------------------------
    def _guardar_cliente(self, cliente: Cliente) -> int:
        if cliente.id is None:
            cur = self.con.execute(
                "INSERT INTO clientes (nombre, telefono, email) VALUES (?, ?, ?)",
                (cliente.nombre, cliente.telefono, cliente.email),
            )
            cliente.id = cur.lastrowid
        else:
            self.con.execute(
                "UPDATE clientes SET nombre=?, telefono=?, email=? WHERE id=?",
                (cliente.nombre, cliente.telefono, cliente.email, cliente.id),
            )
        return cliente.id

    # --- Cuotas ------------------------------------------------------------
    def _insertar_cuotas(self, prestamo_id: int, cuotas: list[CuotaRegistro]) -> None:
        self.con.executemany(
            """INSERT INTO cuotas
               (prestamo_id, numero, fecha, dias, interes, amortizacion,
                cuota, saldo, pagada, fecha_pago)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    prestamo_id, c.numero, c.fecha.isoformat(), c.dias,
                    str(c.interes), str(c.amortizacion), str(c.cuota),
                    str(c.saldo), int(c.pagada),
                    c.fecha_pago.isoformat() if c.fecha_pago else None,
                )
                for c in cuotas
            ],
        )

    def _cuotas_de(self, prestamo_id: int) -> list[CuotaRegistro]:
        filas = self.con.execute(
            "SELECT * FROM cuotas WHERE prestamo_id=? ORDER BY numero", (prestamo_id,)
        ).fetchall()
        return [
            CuotaRegistro(
                id=f["id"],
                numero=f["numero"],
                fecha=_fecha(f["fecha"]),
                dias=f["dias"],
                interes=_d(f["interes"]),
                amortizacion=_d(f["amortizacion"]),
                cuota=_d(f["cuota"]),
                saldo=_d(f["saldo"]),
                pagada=bool(f["pagada"]),
                fecha_pago=_fecha(f["fecha_pago"]),
            )
            for f in filas
        ]

    # --- Préstamos ---------------------------------------------------------
    def crear_prestamo(self, prestamo: Prestamo) -> Prestamo:
        """Inserta el préstamo, su cliente y genera/guarda el cronograma."""
        cliente_id = self._guardar_cliente(prestamo.cliente)
        creado = (prestamo.creado_en or date.today()).isoformat()
        cur = self.con.execute(
            """INSERT INTO prestamos
               (cliente_id, monto, tasa_mensual, fecha_inicio, num_cuotas,
                notas, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                cliente_id, str(prestamo.monto), str(prestamo.tasa_mensual),
                prestamo.fecha_inicio.isoformat(), prestamo.num_cuotas,
                prestamo.notas, creado,
            ),
        )
        prestamo.id = cur.lastrowid

        cuotas_calc, _ = generar_cronograma(
            prestamo.monto, prestamo.tasa_mensual,
            prestamo.fecha_inicio, prestamo.num_cuotas,
        )
        registros = [
            CuotaRegistro(
                numero=c.numero, fecha=c.fecha, dias=c.dias, interes=c.interes,
                amortizacion=c.amortizacion, cuota=c.cuota, saldo=c.saldo,
            )
            for c in cuotas_calc
        ]
        self._insertar_cuotas(prestamo.id, registros)
        self.con.commit()
        # Recargar para que las cuotas en memoria tengan su id de la BD.
        prestamo.cuotas = self._cuotas_de(prestamo.id)
        return prestamo

    def actualizar_datos_basicos(self, prestamo: Prestamo, regenerar: bool) -> None:
        """Actualiza datos del préstamo y cliente. Si ``regenerar`` es True,
        recrea el cronograma (al cambiar monto/tasa/fecha/nº de cuotas)."""
        self._guardar_cliente(prestamo.cliente)
        self.con.execute(
            """UPDATE prestamos
               SET cliente_id=?, monto=?, tasa_mensual=?, fecha_inicio=?,
                   num_cuotas=?, notas=? WHERE id=?""",
            (
                prestamo.cliente.id, str(prestamo.monto), str(prestamo.tasa_mensual),
                prestamo.fecha_inicio.isoformat(), prestamo.num_cuotas,
                prestamo.notas, prestamo.id,
            ),
        )
        if regenerar:
            self.con.execute("DELETE FROM cuotas WHERE prestamo_id=?", (prestamo.id,))
            cuotas_calc, _ = generar_cronograma(
                prestamo.monto, prestamo.tasa_mensual,
                prestamo.fecha_inicio, prestamo.num_cuotas,
            )
            registros = [
                CuotaRegistro(
                    numero=c.numero, fecha=c.fecha, dias=c.dias, interes=c.interes,
                    amortizacion=c.amortizacion, cuota=c.cuota, saldo=c.saldo,
                )
                for c in cuotas_calc
            ]
            self._insertar_cuotas(prestamo.id, registros)
            prestamo.cuotas = self._cuotas_de(prestamo.id)
        self.con.commit()

    def listar_prestamos(self) -> list[Prestamo]:
        filas = self.con.execute(
            "SELECT * FROM prestamos ORDER BY id"
        ).fetchall()
        return [self._cargar_prestamo(f) for f in filas]

    def obtener_prestamo(self, prestamo_id: int) -> Prestamo | None:
        f = self.con.execute(
            "SELECT * FROM prestamos WHERE id=?", (prestamo_id,)
        ).fetchone()
        return self._cargar_prestamo(f) if f else None

    def _cargar_prestamo(self, f: sqlite3.Row) -> Prestamo:
        c = self.con.execute(
            "SELECT * FROM clientes WHERE id=?", (f["cliente_id"],)
        ).fetchone()
        cliente = Cliente(
            id=c["id"], nombre=c["nombre"], telefono=c["telefono"], email=c["email"],
        )
        prestamo = Prestamo(
            id=f["id"],
            cliente=cliente,
            monto=_d(f["monto"]),
            tasa_mensual=_d(f["tasa_mensual"]),
            fecha_inicio=_fecha(f["fecha_inicio"]),
            num_cuotas=f["num_cuotas"],
            notas=f["notas"],
            creado_en=_fecha(f["creado_en"]),
        )
        prestamo.cuotas = self._cuotas_de(f["id"])
        prestamo.ampliaciones = self._ampliaciones_de(f["id"])
        prestamo.estado = prestamo.calcular_estado()
        return prestamo

    def eliminar_prestamo(self, prestamo_id: int) -> None:
        self.con.execute("DELETE FROM prestamos WHERE id=?", (prestamo_id,))
        self.con.commit()

    # --- Pagos -------------------------------------------------------------
    def marcar_cuota(
        self, cuota_id: int, pagada: bool, fecha_pago: date | None = None
    ) -> None:
        self.con.execute(
            "UPDATE cuotas SET pagada=?, fecha_pago=? WHERE id=?",
            (
                int(pagada),
                fecha_pago.isoformat() if (pagada and fecha_pago) else None,
                cuota_id,
            ),
        )
        self.con.commit()

    # --- Ampliaciones ------------------------------------------------------
    def _ampliaciones_de(self, prestamo_id: int) -> list[Ampliacion]:
        filas = self.con.execute(
            "SELECT * FROM ampliaciones WHERE prestamo_id=? ORDER BY id", (prestamo_id,)
        ).fetchall()
        return [
            Ampliacion(
                id=f["id"],
                fecha=_fecha(f["fecha"]),
                monto_extra=_d(f["monto_extra"]),
                cuotas_agregadas=f["cuotas_agregadas"],
                detalle=f["detalle"],
                creada_en=_fecha(f["creada_en"]),
            )
            for f in filas
        ]

    def aplicar_ampliacion(
        self,
        prestamo: Prestamo,
        fecha_ampliacion: date,
        monto_extra: Decimal,
        cuotas_agregadas: int,
        detalle: str = "",
    ) -> Prestamo:
        """Guarda la ampliación como la nueva versión del préstamo."""
        resultado = simular_ampliacion(
            prestamo, fecha_ampliacion, monto_extra, cuotas_agregadas
        )
        # Reemplazar el cronograma por el combinado.
        self.con.execute("DELETE FROM cuotas WHERE prestamo_id=?", (prestamo.id,))
        self._insertar_cuotas(prestamo.id, resultado.cuotas)
        # Actualizar nº de cuotas total.
        nuevo_total = len(resultado.cuotas)
        self.con.execute(
            "UPDATE prestamos SET num_cuotas=? WHERE id=?",
            (nuevo_total, prestamo.id),
        )
        # Registrar en el historial.
        self.con.execute(
            """INSERT INTO ampliaciones
               (prestamo_id, fecha, monto_extra, cuotas_agregadas, detalle, creada_en)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                prestamo.id, fecha_ampliacion.isoformat(), str(monto_extra),
                cuotas_agregadas, detalle, date.today().isoformat(),
            ),
        )
        self.con.commit()
        return self.obtener_prestamo(prestamo.id)
