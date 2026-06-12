"""Conexión a SQLite y creación del esquema (todo local, sin nube)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def ruta_bd() -> Path:
    """Ubicación del archivo SQLite. Configurable con la variable de entorno
    ``PRESTAMOS_DB``; por defecto en la carpeta del usuario."""
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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id   INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    monto        TEXT NOT NULL,        -- Decimal serializado como texto
    tasa_mensual TEXT NOT NULL,        -- Decimal (ej. '0.014602')
    fecha_inicio TEXT NOT NULL,        -- ISO 'YYYY-MM-DD'
    num_cuotas   INTEGER NOT NULL,
    notas        TEXT DEFAULT '',
    creado_en    TEXT NOT NULL
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
"""


def conectar() -> sqlite3.Connection:
    """Abre la conexión, crea la carpeta/esquema si no existen."""
    ruta = ruta_bd()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    return con
