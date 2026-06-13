"""Prueba de integración de la API REST (sin interfaz gráfica)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# BD temporal aislada ANTES de importar la app.
_DB = Path(tempfile.gettempdir()) / "_test_api_prestamos.db"
if _DB.exists():
    _DB.unlink()
os.environ["PRESTAMOS_DB"] = str(_DB)
# Exportaciones a una carpeta temporal y sin abrir archivos durante las pruebas.
os.environ["PRESTAMOS_EXPORT_DIR"] = tempfile.mkdtemp(prefix="_test_export_")
os.environ["PRESTAMOS_NO_ABRIR"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient  # noqa: E402

from prestamos.api.app import app  # noqa: E402

cliente = TestClient(app)

CASO = {
    "cliente": {"nombre": "Juan Pérez", "telefono": "999", "email": "j@e.com"},
    "monto": 18000,
    "tasa_mensual_pct": 1.4602,
    "formula": "A",
    "fecha_desembolso": "2026-05-01",
    "fecha_primer_vencimiento": "2026-06-01",
    "num_cuotas": 12,
    "notas": "préstamo de prueba",
}


def test_calcular_caso_obligatorio():
    r = cliente.post("/api/calcular", json=CASO)
    assert r.status_code == 200
    d = r.json()
    assert d["cuota_fija"] == "1645.78"
    c1 = d["cuotas"][0]
    assert c1["dias"] == 31
    assert c1["interes"] == "266.00"
    assert c1["amortizacion"] == "1379.78"
    assert c1["saldo"] == "16620.22"
    assert d["cuotas"][-1]["saldo"] == "0.00"


def test_flujo_completo():
    # Crear
    r = cliente.post("/api/prestamos", json=CASO)
    assert r.status_code == 200
    p = r.json()
    pid = p["id"]
    assert len(p["cuotas"]) == 12

    # Aparece en la lista
    assert any(x["id"] == pid for x in cliente.get("/api/prestamos").json())

    # Marcar la primera cuota como pagada
    cuota1 = p["cuotas"][0]
    r = cliente.post(f"/api/prestamos/{pid}/pagos", json={"cuota_id": cuota1["id"], "pagada": True})
    assert r.status_code == 200
    assert r.json()["resumen"]["cuotas_pagadas"] == 1

    # Simular ampliación: +5000 y +6 cuotas desde 2026-09-01
    r = cliente.post(f"/api/prestamos/{pid}/simular",
                     json={"fecha": "2026-09-01", "monto_extra": 5000, "cuotas_agregadas": 6})
    assert r.status_code == 200
    sim = r.json()
    assert sim["cuotas"][-1]["saldo"] == "0.00"
    assert len(sim["cuotas"]) == 18

    # Aplicar ampliación
    r = cliente.post(f"/api/prestamos/{pid}/ampliar",
                     json={"fecha": "2026-09-01", "monto_extra": 5000, "cuotas_agregadas": 6})
    assert r.status_code == 200
    assert r.json()["num_cuotas"] == 18
    assert len(r.json()["ampliaciones"]) == 1

    # Exportar Excel: guarda el archivo y devuelve la ruta
    r = cliente.get(f"/api/prestamos/{pid}/excel")
    assert r.status_code == 200
    ruta_xlsx = Path(r.json()["ruta"])
    assert ruta_xlsx.suffix == ".xlsx" and ruta_xlsx.exists()
    assert ruta_xlsx.stat().st_size > 2000

    # Exportar PDF (estado de cuenta)
    r = cliente.get(f"/api/prestamos/{pid}/pdf")
    assert r.status_code == 200
    ruta_pdf = Path(r.json()["ruta"])
    assert ruta_pdf.suffix == ".pdf" and ruta_pdf.exists()
    assert ruta_pdf.read_bytes()[:5] == b"%PDF-"


def test_editar_preserva_pagos():
    # Pagar una cuota, luego editar términos (regenera) y verificar que sigue pagada.
    pid = cliente.post("/api/prestamos", json=CASO).json()["id"]
    p = cliente.get(f"/api/prestamos/{pid}").json()
    cliente.post(f"/api/prestamos/{pid}/pagos",
                 json={"cuota_id": p["cuotas"][0]["id"], "pagada": True})
    r = cliente.put(f"/api/prestamos/{pid}", json=dict(CASO, tasa_mensual_pct=2.0))
    assert r.status_code == 200
    assert r.json()["cuotas"][0]["pagada"] is True
    assert r.json()["resumen"]["cuotas_pagadas"] == 1


def test_dashboard_endpoint():
    cliente.post("/api/prestamos", json=CASO)
    d = cliente.get("/api/dashboard").json()
    assert "meses" in d and "totales" in d
    assert all({"mes", "interes_mio", "amortizacion", "impuesto", "saldo_pendiente"} <= set(m)
               for m in d["meses"])
    assert "impuesto" in d["totales"] and "interes_carrillo" in d["totales"]


def test_formula_simple_y_validaciones():
    caso_b = dict(CASO, formula="B")
    assert cliente.post("/api/calcular", json=caso_b).status_code == 200
    # Primer vencimiento anterior al desembolso -> error 400
    malo = dict(CASO, fecha_primer_vencimiento="2026-04-01")
    assert cliente.post("/api/calcular", json=malo).status_code == 400
