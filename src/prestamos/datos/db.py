"""Conexión a SQLite y creación del esquema (todo local, sin nube)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def ruta_bd() -> Path:
    """Ubicación del archivo SQLite. Configurable con ``PRESTAMOS_DB``."""
    env = os.environ.get("PRESTAMOS_DB")
    if env:
        return Path(env)
    return Path.home() / ".gestor_prestamos" / "prestamos.db"


ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    telefono TEXT DEFAULT '',
    email    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS prestamos (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id               INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    monto                    TEXT NOT NULL,
    tasa_mensual             TEXT NOT NULL,
    formula                  TEXT NOT NULL DEFAULT 'A',
    fecha_desembolso         TEXT NOT NULL,
    fecha_primer_vencimiento TEXT NOT NULL,
    num_cuotas               INTEGER NOT NULL,
    notas                    TEXT DEFAULT '',
    creado_en                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cuotas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    prestamo_id  INTEGER NOT NULL REFERENCES prestamos(id) ON DELETE CASCADE,
    numero       INTEGER NOT NULL,
    fecha        TEXT NOT NULL,
    dias         INTEGER NOT NULL,
    interes      TEXT NOT NULL,
    amortizacion TEXT NOT NULL,
    cuota        TEXT NOT NULL,
    saldo        TEXT NOT NULL,
    pagada       INTEGER NOT NULL DEFAULT 0,
    fecha_pago   TEXT
);

CREATE TABLE IF NOT EXISTS ampliaciones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    prestamo_id      INTEGER NOT NULL REFERENCES prestamos(id) ON DELETE CASCADE,
    fecha            TEXT NOT NULL,
    monto_extra      TEXT NOT NULL,
    cuotas_agregadas INTEGER NOT NULL,
    detalle          TEXT DEFAULT '',
    creada_en        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferencias (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""


def _columnas(con: sqlite3.Connection, tabla: str) -> set[str]:
    return {r["name"] for r in con.execute(f"PRAGMA table_info({tabla})")}


def _migrar(con: sqlite3.Connection) -> None:
    """Actualiza esquemas antiguos (p. ej. de la versión previa) sin perder datos."""
    cols = _columnas(con, "prestamos")
    if not cols:
        return
    if "formula" not in cols:
        con.execute("ALTER TABLE prestamos ADD COLUMN formula TEXT NOT NULL DEFAULT 'A'")
    if "fecha_desembolso" not in cols:
        con.execute("ALTER TABLE prestamos ADD COLUMN fecha_desembolso TEXT")
    if "fecha_primer_vencimiento" not in cols:
        con.execute("ALTER TABLE prestamos ADD COLUMN fecha_primer_vencimiento TEXT")
    # Esquema viejo usaba 'fecha_inicio': lo usamos como desembolso y 1er venc.
    if "fecha_inicio" in cols:
        con.execute(
            "UPDATE prestamos SET fecha_desembolso = COALESCE(fecha_desembolso, fecha_inicio)"
        )
        con.execute(
            "UPDATE prestamos SET fecha_primer_vencimiento = "
            "COALESCE(fecha_primer_vencimiento, fecha_inicio)"
        )
    con.commit()


def conectar() -> sqlite3.Connection:
    ruta = ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    _migrar(con)
    return con
