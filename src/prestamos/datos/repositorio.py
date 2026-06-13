"""Acceso a datos: crear/leer/editar préstamos, pagos y ampliaciones."""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from ..core.calculo import generar_cronograma
from ..core.modelos import Ampliacion, Cliente, CuotaRegistro, Prestamo
from ..core.simulacion import simular_ampliacion
from .db import conectar


def _d(valor) -> Decimal:
    return Decimal(str(valor))


def _fecha(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


def _registros(cuotas) -> list[CuotaRegistro]:
    return [
        CuotaRegistro(
            numero=c.numero, fecha=c.fecha, dias=c.dias, interes=c.interes,
            amortizacion=c.amortizacion, cuota=c.cuota, saldo=c.saldo,
        )
        for c in cuotas
    ]


class Repositorio:
    def __init__(self, con: sqlite3.Connection | None = None):
        self.con = con or conectar()

    def cerrar(self) -> None:
        self.con.close()

    # --- Preferencias ------------------------------------------------------
    def obtener_preferencia(self, clave: str, por_defecto: str = "") -> str:
        f = self.con.execute(
            "SELECT valor FROM preferencias WHERE clave=?", (clave,)
        ).fetchone()
        return f["valor"] if f else por_defecto

    def guardar_preferencia(self, clave: str, valor: str) -> None:
        self.con.execute(
            "INSERT INTO preferencias (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, valor),
        )
        self.con.commit()

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
                id=f["id"], numero=f["numero"], fecha=_fecha(f["fecha"]),
                dias=f["dias"], interes=_d(f["interes"]),
                amortizacion=_d(f["amortizacion"]), cuota=_d(f["cuota"]),
                saldo=_d(f["saldo"]), pagada=bool(f["pagada"]),
                fecha_pago=_fecha(f["fecha_pago"]),
            )
            for f in filas
        ]

    def _generar_registros(self, p: Prestamo) -> list[CuotaRegistro]:
        cuotas, _ = generar_cronograma(
            p.monto, p.tasa_mensual, p.formula,
            p.fecha_desembolso, p.fecha_primer_vencimiento, p.num_cuotas,
        )
        return _registros(cuotas)

    # --- Préstamos ---------------------------------------------------------
    def crear_prestamo(self, p: Prestamo) -> Prestamo:
        cliente_id = self._guardar_cliente(p.cliente)
        creado = (p.creado_en or date.today()).isoformat()
        cur = self.con.execute(
            """INSERT INTO prestamos
               (cliente_id, monto, tasa_mensual, formula, fuente, fecha_desembolso,
                fecha_primer_vencimiento, num_cuotas, notas, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cliente_id, str(p.monto), str(p.tasa_mensual), p.formula, p.fuente,
                p.fecha_desembolso.isoformat(), p.fecha_primer_vencimiento.isoformat(),
                p.num_cuotas, p.notas, creado,
            ),
        )
        p.id = cur.lastrowid
        self._insertar_cuotas(p.id, self._generar_registros(p))
        self.con.commit()
        p.cuotas = self._cuotas_de(p.id)
        return p

    def actualizar_datos_basicos(self, p: Prestamo, regenerar: bool) -> None:
        self._guardar_cliente(p.cliente)
        self.con.execute(
            """UPDATE prestamos
               SET cliente_id=?, monto=?, tasa_mensual=?, formula=?, fuente=?,
                   fecha_desembolso=?, fecha_primer_vencimiento=?, num_cuotas=?,
                   notas=? WHERE id=?""",
            (
                p.cliente.id, str(p.monto), str(p.tasa_mensual), p.formula, p.fuente,
                p.fecha_desembolso.isoformat(), p.fecha_primer_vencimiento.isoformat(),
                p.num_cuotas, p.notas, p.id,
            ),
        )
        if regenerar:
            self.con.execute("DELETE FROM cuotas WHERE prestamo_id=?", (p.id,))
            self._insertar_cuotas(p.id, self._generar_registros(p))
            p.cuotas = self._cuotas_de(p.id)
        self.con.commit()

    def listar_prestamos(self) -> list[Prestamo]:
        filas = self.con.execute("SELECT * FROM prestamos ORDER BY id").fetchall()
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
        p = Prestamo(
            id=f["id"], cliente=cliente, monto=_d(f["monto"]),
            tasa_mensual=_d(f["tasa_mensual"]), formula=f["formula"],
            fuente=f["fuente"],
            fecha_desembolso=_fecha(f["fecha_desembolso"]),
            fecha_primer_vencimiento=_fecha(f["fecha_primer_vencimiento"]),
            num_cuotas=f["num_cuotas"], notas=f["notas"],
            creado_en=_fecha(f["creado_en"]),
        )
        p.cuotas = self._cuotas_de(f["id"])
        p.ampliaciones = self._ampliaciones_de(f["id"])
        p.estado = p.calcular_estado()
        return p

    def eliminar_prestamo(self, prestamo_id: int) -> None:
        self.con.execute("DELETE FROM prestamos WHERE id=?", (prestamo_id,))
        self.con.commit()

    # --- Pagos -------------------------------------------------------------
    def marcar_cuota(self, cuota_id: int, pagada: bool, fecha_pago: date | None = None) -> None:
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
                id=f["id"], fecha=_fecha(f["fecha"]), monto_extra=_d(f["monto_extra"]),
                cuotas_agregadas=f["cuotas_agregadas"], detalle=f["detalle"],
                creada_en=_fecha(f["creada_en"]),
            )
            for f in filas
        ]

    def aplicar_ampliacion(
        self, prestamo: Prestamo, fecha_ampliacion: date,
        monto_extra: Decimal, cuotas_agregadas: int, detalle: str = "",
    ) -> Prestamo:
        resultado = simular_ampliacion(
            prestamo, fecha_ampliacion, monto_extra, cuotas_agregadas
        )
        self.con.execute("DELETE FROM cuotas WHERE prestamo_id=?", (prestamo.id,))
        self._insertar_cuotas(prestamo.id, resultado.cuotas)
        self.con.execute(
            "UPDATE prestamos SET num_cuotas=? WHERE id=?",
            (len(resultado.cuotas), prestamo.id),
        )
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
