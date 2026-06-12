# Gestor de Préstamos 💰

Aplicación de **escritorio** para gestionar préstamos personales (para el
prestamista). Corre **100% local** en tu laptop, sin nube. Los datos se guardan
en una base de datos **SQLite** local.

- Interfaz gráfica en **español** (PySide6 / Qt).
- Cálculo de amortización **francés** (cuota fija) con interés sobre saldo
  pendiente ajustado por los **días reales** de cada mes.
- Cada préstamo define su propia **tasa mensual**.
- Registro de clientes, seguimiento de pagos y estado.
- **Simulación de ampliaciones** sin alterar el préstamo original.
- **Exportación de cronogramas a Excel** (.xlsx).

---

## ▶️ Cómo ejecutarla

**Requisito:** tener Python 3.10+ instalado (descárgalo de
[python.org](https://www.python.org/downloads/) si no lo tienes).

La forma más simple en Windows:

1. Abre la carpeta del proyecto.
2. Click derecho sobre **`run.ps1`** → **Ejecutar con PowerShell**.

La primera vez creará el entorno virtual e instalará las dependencias
(PySide6, openpyxl); las siguientes veces solo abrirá la app.

> Si PowerShell bloquea el script, ábrelo desde una terminal con:
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\run.ps1
> ```

### Manualmente (alternativa)

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\prestamos\main.py
```

---

## 🧮 Lógica de cálculo

A partir de la **tasa mensual** que ingresas por préstamo:

```
tasa_anual_efectiva  = (1 + tasa_mensual) ** 12 - 1
tasa_diaria_efectiva = (1 + tasa_anual_efectiva) ** (1 / 365) - 1
interes_cuota        = saldo_pendiente * tasa_diaria_efectiva * dias_del_periodo
```

La **cuota es fija** (calculada para amortizar el total con los días reales de
cada periodo) y la **última cuota ajusta el redondeo** para dejar saldo 0. Todo
el dinero usa `Decimal` con redondeo `ROUND_HALF_UP` a 2 decimales.

**Caso de validación** (en `tests/test_calculo.py`):
S/ 18,000 · 1.4602% mensual · inicio 1/05/2026 · 12 cuotas →
cuota fija **S/ 1,645.78**, cuota 1 (31 días) interés **S/ 266.00** /
amortización **S/ 1,379.78** / saldo **S/ 16,620.22**, saldo final **S/ 0.00**.

> Nota: el *total a pagar* calculado es **S/ 19,749.34**; una referencia previa
> marcaba 19,749.33 (difiere 1 céntimo por la convención de redondeo de la
> última cuota). El modo de redondeo está aislado en `core/calculo.py`
> (`MODO_REDONDEO`) por si quieres ajustarlo.

---

## 📁 Estructura del proyecto

```
src/prestamos/
├── main.py                  # punto de entrada (lanza la ventana)
├── core/
│   ├── calculo.py           # motor de amortización (Decimal)
│   ├── modelos.py           # Cliente, Prestamo, Cuota, Ampliacion
│   └── simulacion.py        # lógica de ampliación
├── datos/
│   ├── db.py                # conexión SQLite + esquema
│   └── repositorio.py       # CRUD de préstamos/pagos/ampliaciones
├── exportar/excel.py        # cronograma → .xlsx
└── ui/                      # interfaz PySide6
    ├── ventana_principal.py
    ├── dialogo_prestamo.py
    ├── dialogo_simulacion.py
    └── comunes.py
tests/test_calculo.py        # valida el caso obligatorio
archivo/                     # prototipo anterior en PowerShell (histórico)
```

---

## 🗄️ Dónde se guardan los datos

En `C:\Users\<tu_usuario>\.gestor_prestamos\prestamos.db`.
Puedes cambiar la ruta con la variable de entorno `PRESTAMOS_DB`.

## ✅ Pruebas

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

## Licencia

MIT
