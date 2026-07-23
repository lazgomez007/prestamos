"""API REST local (FastAPI) que conecta el frontend web con el núcleo Python."""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..core.calculo import (
    FORMULA_EFECTIVA,
    FORMULA_MENSUAL,
    FORMULA_SIMPLE,
    desglose_carrillo,
    generar_cronograma,
    redondear,
    total_a_pagar,
    total_interes,
)
from ..core.dashboard import resumen_mensual
from ..core.modelos import FUENTE_CARRILLO, FUENTE_PROPIOS, FUENTES, Cliente, Prestamo
from ..core.simulacion import simular_ampliacion
from ..datos.repositorio import Repositorio
from ..exportar.excel import exportar_cronograma
from ..exportar.pdf import exportar_estado_cuenta

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# --- Exportación de archivos a disco (app local) ----------------------------
def _slug(nombre: str) -> str:
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre or "").strip("_")
    return limpio or "cliente"


def _carpeta_descargas() -> Path:
    """Carpeta donde se guardan los archivos exportados (Descargas por defecto)."""
    env = os.environ.get("PRESTAMOS_EXPORT_DIR")
    if env:
        return Path(env)
    descargas = Path.home() / "Downloads"
    return descargas if descargas.exists() else Path.home()


def _abrir_archivo(ruta: Path) -> None:
    """Abre el archivo con la aplicación predeterminada (Windows)."""
    if os.environ.get("PRESTAMOS_NO_ABRIR"):
        return
    try:
        os.startfile(str(ruta))  # type: ignore[attr-defined]
    except Exception:
        pass


# --- Utilidades de conversión ----------------------------------------------
def _dec(valor) -> Decimal:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        raise HTTPException(400, f"Número inválido: {valor!r}")


def _pct_a_fraccion(pct) -> Decimal:
    return _dec(pct) / Decimal(100)


def _fecha(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Fecha inválida (use AAAA-MM-DD): {texto!r}")


def _m(valor: Decimal) -> str:
    """Importe redondeado a 2 decimales como texto (preserva precisión)."""
    return str(redondear(valor))


def _cuota_dict(c) -> dict:
    return {
        "id": getattr(c, "id", None),
        "numero": c.numero,
        "fecha": c.fecha.isoformat(),
        "dias": c.dias,
        "interes": _m(c.interes),
        "amortizacion": _m(c.amortizacion),
        "cuota": _m(c.cuota),
        "saldo": _m(c.saldo),
        "pagada": bool(getattr(c, "pagada", False)),
        "fecha_pago": c.fecha_pago.isoformat() if getattr(c, "fecha_pago", None) else None,
    }


def _resumen(cuotas) -> dict:
    total = sum((c.cuota for c in cuotas), Decimal(0))
    pagado = sum((c.cuota for c in cuotas if getattr(c, "pagada", False)), Decimal(0))
    pagadas = sum(1 for c in cuotas if getattr(c, "pagada", False))
    return {
        "num_cuotas": len(cuotas),
        "cuotas_pagadas": pagadas,
        "total": _m(total),
        "total_interes": _m(total_interes(cuotas)) if cuotas else "0.00",
        "pagado": _m(pagado),
        "por_cobrar": _m(total - pagado),
    }


def _enriquecer_carrillo(p: Prestamo, cuota_objs, cuota_dicts, resumen: dict) -> None:
    """Si el préstamo tiene tasa de Carrillo, agrega el desglose del interés
    (Carrillo / mío) a cada cuota y los totales al resumen."""
    if not (p.tasa_carrillo and p.tasa_carrillo > 0):
        return
    pares = desglose_carrillo(p.monto, p.tasa_carrillo, p.formula, cuota_objs)
    tot_c, tot_m = Decimal(0), Decimal(0)
    for cd, (ic, im) in zip(cuota_dicts, pares):
        cd["interes_carrillo"] = _m(ic)
        cd["interes_mio"] = _m(im)
        tot_c += ic
        tot_m += im
    resumen["interes_carrillo"] = _m(tot_c)
    resumen["interes_mio"] = _m(tot_m)


def _prestamo_resumen(p: Prestamo) -> dict:
    return {
        "id": p.id,
        "cliente": p.cliente.nombre,
        "monto": _m(p.monto),
        "tasa_mensual_pct": str((p.tasa_mensual * 100).normalize()),
        "formula": p.formula,
        "fuente": p.fuente,
        "num_cuotas": p.num_cuotas,
        "estado": p.estado,
    }


def _prestamo_detalle(p: Prestamo) -> dict:
    d = {
        "id": p.id,
        "cliente": {
            "id": p.cliente.id, "nombre": p.cliente.nombre,
            "telefono": p.cliente.telefono, "email": p.cliente.email,
        },
        "monto": _m(p.monto),
        "tasa_mensual_pct": str((p.tasa_mensual * 100).normalize()),
        "formula": p.formula,
        "fuente": p.fuente,
        "capital_final": _m(p.capital_final),
        "tasa_carrillo_pct": str((p.tasa_carrillo * 100).normalize()),
        "fecha_desembolso": p.fecha_desembolso.isoformat(),
        "fecha_primer_vencimiento": p.fecha_primer_vencimiento.isoformat(),
        "num_cuotas": p.num_cuotas,
        "notas": p.notas,
        "estado": p.estado,
        "cuotas": [_cuota_dict(c) for c in p.cuotas],
        "ampliaciones": [
            {
                "fecha": a.fecha.isoformat(), "monto_extra": _m(a.monto_extra),
                "cuotas_agregadas": a.cuotas_agregadas,
                "creada_en": a.creada_en.isoformat() if a.creada_en else None,
            }
            for a in p.ampliaciones
        ],
        "resumen": _resumen(p.cuotas),
    }
    _enriquecer_carrillo(p, p.cuotas, d["cuotas"], d["resumen"])
    if p.capital_final and p.capital_final > 0 and d["cuotas"]:
        d["cuotas"][-1]["es_balon"] = True
    return d


def _prestamo_desde_payload(data: dict, base: Prestamo | None = None) -> Prestamo:
    formula = data.get("formula", FORMULA_EFECTIVA)
    if formula not in (FORMULA_EFECTIVA, FORMULA_SIMPLE, FORMULA_MENSUAL):
        raise HTTPException(400, "Fórmula debe ser 'A', 'B' o 'C'.")
    cliente_data = data.get("cliente", {})
    if not cliente_data.get("nombre", "").strip():
        raise HTTPException(400, "El nombre del cliente es obligatorio.")
    cliente = base.cliente if base else Cliente(nombre="")
    cliente.nombre = cliente_data["nombre"].strip()
    cliente.telefono = cliente_data.get("telefono", "").strip()
    cliente.email = cliente_data.get("email", "").strip()

    p = base or Prestamo(
        cliente=cliente, monto=Decimal(0), tasa_mensual=Decimal(0),
        fecha_desembolso=date.today(), fecha_primer_vencimiento=date.today(),
        num_cuotas=1,
    )
    p.cliente = cliente
    p.monto = _dec(data["monto"])
    p.tasa_mensual = _pct_a_fraccion(data["tasa_mensual_pct"])
    p.formula = formula
    p.fuente = (data.get("fuente") or FUENTE_PROPIOS).strip() or FUENTE_PROPIOS
    # La tasa de Carrillo solo aplica a préstamos de esa fuente.
    p.tasa_carrillo = (
        _pct_a_fraccion(data.get("tasa_carrillo_pct") or 0)
        if p.fuente == FUENTE_CARRILLO else Decimal(0)
    )
    p.capital_final = _dec(data.get("capital_final") or 0)
    p.fecha_desembolso = _fecha(data["fecha_desembolso"])
    p.fecha_primer_vencimiento = _fecha(data["fecha_primer_vencimiento"])
    p.num_cuotas = int(data["num_cuotas"])
    p.notas = data.get("notas", "").strip()
    if p.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor que 0.")
    if p.capital_final < 0:
        raise HTTPException(400, "La devolución de capital no puede ser negativa.")
    if p.capital_final >= p.monto:
        raise HTTPException(400, "La devolución de capital debe ser menor que el monto.")
    if p.num_cuotas < 1:
        raise HTTPException(400, "El número de cuotas debe ser al menos 1.")
    if p.fecha_primer_vencimiento <= p.fecha_desembolso:
        raise HTTPException(400, "El primer vencimiento debe ser posterior al desembolso.")
    return p


# --- App --------------------------------------------------------------------
app = FastAPI(title="Gestor de Préstamos")


@app.get("/api/preferencias/{clave}")
def get_pref(clave: str):
    repo = Repositorio()
    try:
        return {"valor": repo.obtener_preferencia(clave, "")}
    finally:
        repo.cerrar()


@app.put("/api/preferencias/{clave}")
def set_pref(clave: str, data: dict = Body(...)):
    repo = Repositorio()
    try:
        repo.guardar_preferencia(clave, str(data.get("valor", "")))
        return {"ok": True}
    finally:
        repo.cerrar()


@app.get("/api/fuentes")
def fuentes():
    return {"fuentes": FUENTES}


@app.get("/api/acciones")
def acciones():
    """Semáforo técnico en vivo de los tickers configurados."""
    from ..acciones import telegram as tg
    from ..acciones.config import cargar_config, cargar_estado
    from ..acciones.tv import consultar

    try:
        cfg = cargar_config()
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    estado = cargar_estado()
    lecturas = consultar(cfg["tickers"], cfg["intervalos"], pausa=0.5)
    return {
        "config": {
            "intervalos": cfg["intervalos"], "regla": cfg["regla"],
            "tickers": cfg["tickers"],
        },
        "telegram_configurado": tg.configurado(),
        "lecturas": [
            dict(l.como_dict(), ultima_registrada=estado.get(l.clave))
            for l in lecturas
        ],
    }


@app.get("/api/dashboard")
def dashboard():
    repo = Repositorio()
    try:
        data = resumen_mensual(repo.listar_prestamos())
        return {
            "meses": [
                {k: (str(v) if isinstance(v, Decimal) else v) for k, v in f.items()}
                for f in data["meses"]
            ],
            "totales": {k: str(v) for k, v in data["totales"].items()},
        }
    finally:
        repo.cerrar()


@app.get("/api/prestamos")
def listar():
    repo = Repositorio()
    try:
        return [_prestamo_resumen(p) for p in repo.listar_prestamos()]
    finally:
        repo.cerrar()


@app.post("/api/calcular")
def calcular(data: dict = Body(...)):
    """Vista previa del cronograma sin guardar (para el formulario)."""
    p = _prestamo_desde_payload(data)
    cuotas, cuota = generar_cronograma(
        p.monto, p.tasa_mensual, p.formula,
        p.fecha_desembolso, p.fecha_primer_vencimiento, p.num_cuotas, p.capital_final,
    )
    dicts = [_cuota_dict(c) for c in cuotas]
    resumen = _resumen(cuotas)
    _enriquecer_carrillo(p, cuotas, dicts, resumen)
    if p.capital_final and p.capital_final > 0 and dicts:
        dicts[-1]["es_balon"] = True
    return {"cuota_fija": _m(cuota), "cuotas": dicts, "resumen": resumen}


@app.post("/api/prestamos")
def crear(data: dict = Body(...)):
    p = _prestamo_desde_payload(data)
    repo = Repositorio()
    try:
        p = repo.crear_prestamo(p)
        return _prestamo_detalle(repo.obtener_prestamo(p.id))
    finally:
        repo.cerrar()


@app.get("/api/prestamos/{pid}")
def detalle(pid: int):
    repo = Repositorio()
    try:
        p = repo.obtener_prestamo(pid)
        if not p:
            raise HTTPException(404, "Préstamo no encontrado.")
        return _prestamo_detalle(p)
    finally:
        repo.cerrar()


@app.put("/api/prestamos/{pid}")
def actualizar(pid: int, data: dict = Body(...)):
    repo = Repositorio()
    try:
        actual = repo.obtener_prestamo(pid)
        if not actual:
            raise HTTPException(404, "Préstamo no encontrado.")
        previo = (
            actual.monto, actual.tasa_mensual, actual.formula,
            actual.fecha_desembolso, actual.fecha_primer_vencimiento, actual.num_cuotas,
        )
        p = _prestamo_desde_payload(data, base=actual)
        nuevo = (
            p.monto, p.tasa_mensual, p.formula,
            p.fecha_desembolso, p.fecha_primer_vencimiento, p.num_cuotas,
        )
        repo.actualizar_datos_basicos(p, regenerar=(nuevo != previo))
        return _prestamo_detalle(repo.obtener_prestamo(pid))
    finally:
        repo.cerrar()


@app.delete("/api/prestamos/{pid}")
def eliminar(pid: int):
    repo = Repositorio()
    try:
        repo.eliminar_prestamo(pid)
        return {"ok": True}
    finally:
        repo.cerrar()


@app.post("/api/prestamos/{pid}/pagos")
def marcar_pago(pid: int, data: dict = Body(...)):
    repo = Repositorio()
    try:
        cuota_id = int(data["cuota_id"])
        pagada = bool(data["pagada"])
        repo.marcar_cuota(cuota_id, pagada, date.today() if pagada else None)
        return _prestamo_detalle(repo.obtener_prestamo(pid))
    finally:
        repo.cerrar()


@app.post("/api/prestamos/{pid}/simular")
def simular(pid: int, data: dict = Body(...)):
    repo = Repositorio()
    try:
        p = repo.obtener_prestamo(pid)
        if not p:
            raise HTTPException(404, "Préstamo no encontrado.")
        try:
            res = simular_ampliacion(
                p, _fecha(data["fecha"]), _dec(data["monto_extra"]),
                int(data["cuotas_agregadas"]),
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        restantes = res.cuotas[res.indice_corte:]
        return {
            "cuotas": [_cuota_dict(c) for c in res.cuotas],
            "indice_corte": res.indice_corte,
            "cuota_fija": _m(res.cuota_fija),
            "saldo_base": _m(res.saldo_base),
            "capital_nuevo": _m(res.capital_nuevo),
            "total_restante": _m(sum((c.cuota for c in restantes), Decimal(0))),
            "cuotas_restantes": len(restantes),
        }
    finally:
        repo.cerrar()


@app.post("/api/prestamos/{pid}/ampliar")
def ampliar(pid: int, data: dict = Body(...)):
    repo = Repositorio()
    try:
        p = repo.obtener_prestamo(pid)
        if not p:
            raise HTTPException(404, "Préstamo no encontrado.")
        p = repo.aplicar_ampliacion(
            p, _fecha(data["fecha"]), _dec(data["monto_extra"]),
            int(data["cuotas_agregadas"]),
        )
        return _prestamo_detalle(p)
    finally:
        repo.cerrar()


@app.get("/api/prestamos/{pid}/excel")
def exportar_excel(pid: int):
    repo = Repositorio()
    try:
        p = repo.obtener_prestamo(pid)
        if not p:
            raise HTTPException(404, "Préstamo no encontrado.")
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = _carpeta_descargas() / f"cronograma_{pid}_{_slug(p.cliente.nombre)}_{sello}.xlsx"
        exportar_cronograma(p, destino)
        _abrir_archivo(destino)
        return {"ok": True, "ruta": str(destino)}
    finally:
        repo.cerrar()


@app.get("/api/prestamos/{pid}/pdf")
def exportar_pdf(pid: int):
    repo = Repositorio()
    try:
        p = repo.obtener_prestamo(pid)
        if not p:
            raise HTTPException(404, "Préstamo no encontrado.")
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = _carpeta_descargas() / f"estado_cuenta_{pid}_{_slug(p.cliente.nombre)}_{sello}.pdf"
        exportar_estado_cuenta(p, destino)
        _abrir_archivo(destino)
        return {"ok": True, "ruta": str(destino)}
    finally:
        repo.cerrar()


@app.exception_handler(HTTPException)
def http_error(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


# Servir el frontend (debe ir al final para no tapar /api/*).
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
