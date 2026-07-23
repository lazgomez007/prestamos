# Gestor de Préstamos 💰

Aplicación de **escritorio** para gestionar préstamos personales (para el
prestamista). Corre **100% local** en tu laptop, sin nube, con una interfaz
**moderna** (claro/oscuro) y los datos en una base de datos **SQLite** local.

- Interfaz web moderna (HTML/CSS/JS) dentro de una ventana de escritorio.
- **Modo claro y oscuro** con un botón.
- Amortización **francesa** (cuota fija) con interés sobre saldo ajustado por los
  **días reales** de cada periodo.
- Dos **fórmulas de interés por préstamo**: A (efectiva, por defecto) y B (simple).
- **Primer vencimiento flexible** (eliges desembolso y primer vencimiento por separado).
- Registro de clientes, seguimiento de pagos y estado (al día / atrasado / pagado).
- **Simulación de ampliaciones** sin alterar el préstamo original.
- **Exportación de cronogramas a Excel** (.xlsx).

---

## ▶️ Cómo ejecutarla (paso a paso, sencillo)

**Solo la primera vez** necesitas tener Python instalado (3.10 o superior).
Si no lo tienes, descárgalo de [python.org](https://www.python.org/downloads/) y,
en el instalador, marca la casilla **“Add Python to PATH”**.

Luego, para abrir la app:

1. Abre la carpeta del proyecto en el Explorador de Windows.
2. Haz **doble clic** en **`Abrir Gestor de Prestamos.bat`**.
   - La **primera vez** preparará todo solo (puede tardar 1–2 minutos) y abrirá la ventana.
   - Las siguientes veces abrirá la app al instante.

> 💡 Consejo: para tenerla a mano, haz click derecho sobre
> `Abrir Gestor de Prestamos.bat` → **Enviar a → Escritorio (crear acceso directo)**.

Eso es todo. Se abrirá una ventana con la aplicación. Arriba a la derecha tienes
el botón 🌙 / ☀️ para cambiar entre **modo claro y oscuro**.

> Si prefieres la terminal: `powershell -ExecutionPolicy Bypass -File .\run.ps1`

---

## 🧮 Lógica de cálculo

A partir de la **tasa mensual** que ingresas por préstamo, eliges la fórmula:

**Fórmula A (efectiva, por defecto):**
```
tasa_anual = (1 + tasa_mensual) ** 12 - 1
tasa_dia   = (1 + tasa_anual) ** (1 / 365) - 1
interes    = saldo * tasa_dia * dias_del_periodo
```

**Fórmula B (simple):**
```
interes    = saldo * (tasa_mensual / 30) * dias_del_periodo
```

`dias_del_periodo` = días reales entre la fecha anterior (o el desembolso, en la
primera cuota) y el vencimiento. La **cuota es fija** y la **última cuota ajusta el
redondeo** para dejar saldo 0. Todo el dinero usa `Decimal` con `ROUND_HALF_UP`.

**Caso de validación** (`tests/test_calculo.py`, Fórmula A):
S/ 18,000 · 1.4602% mensual · desembolso 1/05/2026 · 1er venc. 1/06/2026 · 12 cuotas →
cuota fija **1,645.78**, cuota 1 (31 días) interés **266.00** / amort **1,379.78** /
saldo **16,620.22**, saldo final **0.00**.

> Nota: el *total a pagar* calculado es **19,749.34**; una referencia previa marcaba
> 19,749.33 (difiere 1 céntimo por el redondeo de la última cuota; se demostró que ese
> valor no es alcanzable con una convención de redondeo consistente). El modo de
> redondeo está aislado en `core/calculo.py` (`MODO_REDONDEO`).

---

## 🏗️ Arquitectura y estructura

**pywebview** (ventana de escritorio con Edge WebView2) + **FastAPI** local
(127.0.0.1, en un hilo) + frontend web sin compilación + **SQLite** + **openpyxl**.

```
src/prestamos/
├── core/        calculo.py · modelos.py · simulacion.py   # motor (Decimal)
├── datos/       db.py · repositorio.py                     # SQLite + CRUD
├── exportar/    excel.py                                   # cronograma → .xlsx
├── api/         app.py                                     # API REST (FastAPI)
├── web/         index.html · styles.css · app.js           # interfaz moderna
├── escritorio.py    # arranca FastAPI + abre la ventana (fallback a navegador)
└── main.py          # punto de entrada
tests/  test_calculo.py · test_api.py
archivo/             # prototipo inicial en PowerShell (histórico)
```

## 📈 Acciones — alertas de análisis técnico

Además de los préstamos, la app incluye una pestaña **Acciones** que muestra el
**resumen técnico** de tus tickers (el semáforo `Compra fuerte / Compra / Neutral /
Venta / Venta fuerte`, equivalente al de Investing.com) usando la librería
gratuita `tradingview-ta`.

También hay un **monitor automático** que avisa por **Telegram solo cuando la
señal cambia**.

### Configurar tickers y temporalidades
Edita [`acciones/config.yaml`](acciones/config.yaml):

```yaml
tickers:
  - {symbol: SPY,  exchange: AMEX,   screener: america}
  - {symbol: META, exchange: NASDAQ, screener: america}
intervalos: ["1D", "1h"]     # 1m 5m 15m 30m 1h 2h 4h 1D 1W 1M
regla: any_change            # any_change | only_strong
```

- `any_change`: avisa ante cualquier cambio (BUY → NEUTRAL, etc.).
- `only_strong`: avisa solo cuando entra o sale de `STRONG_BUY` / `STRONG_SELL`.

El último estado se guarda en `acciones/state.json` (clave `"SIMBOLO:INTERVALO"`).

### Configurar Telegram
1. Habla con **@BotFather** en Telegram → `/newbot` → te da un **token**.
2. Habla con **@userinfobot** → te da tu **chat id**.
3. Define las variables de entorno (nunca las guardes en el repo):

```powershell
setx TELEGRAM_TOKEN "12345:AAxxxxxx"
setx TELEGRAM_CHAT_ID "123456789"
```

### Ejecutar el monitor

```powershell
.venv\Scripts\python.exe monitor_acciones.py
```

Registra todo en `acciones/monitor.log`. Para que corra solo:
- **PC local:** Programador de tareas de Windows → ejecuta ese comando cada hora.
- **En la nube:** el workflow [`.github/workflows/monitor-acciones.yml`](.github/workflows/monitor-acciones.yml)
  ya está listo (cron cada hora). Guarda `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`
  como *repository secrets* en GitHub y el workflow persiste `state.json` solo.

> Nota: si tu antivirus intercepta HTTPS (p. ej. Norton), la app usa `truststore`
> para leer el almacén de certificados de Windows y evitar errores SSL.

## 🗄️ Dónde se guardan los datos

En `C:\Users\<tu_usuario>\.gestor_prestamos\prestamos.db`.
Cámbialo con la variable de entorno `PRESTAMOS_DB`.

## ✅ Pruebas

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

## Licencia

MIT
