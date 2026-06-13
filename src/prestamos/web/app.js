"use strict";

/* ===== Estado ===== */
const estado = {
  prestamos: [], actual: null, tab: "crono",
  filtro: "", filtroFuente: "", fuentes: ["Propios"],
};

function nombreFormula(f) {
  return { A: "A (efectiva)", B: "B (simple)", C: "C (mensual fija)" }[f] || "A (efectiva)";
}

function slugFuente(f) {
  const sinAcentos = (f || "").toLowerCase().normalize("NFD")
    .replace(new RegExp("[\\u0300-\\u036f]", "g"), "");
  return "fuente-" + sinAcentos.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/* ===== Utilidades ===== */
const $ = (sel) => document.querySelector(sel);

async function api(metodo, url, cuerpo) {
  const opt = { method: metodo, headers: { "Content-Type": "application/json" } };
  if (cuerpo !== undefined) opt.body = JSON.stringify(cuerpo);
  const res = await fetch(url, opt);
  const datos = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(datos.error || `Error ${res.status}`);
  return datos;
}

function fmtMoneda(valor) {
  const n = Number(valor);
  return "S/ " + n.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtFecha(iso) {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

function escapar(t) {
  const div = document.createElement("div");
  div.textContent = t == null ? "" : String(t);
  return div.innerHTML;
}

let avisoTimer;
function avisar(msg, esError = false) {
  const el = $("#aviso");
  el.textContent = msg;
  el.className = "aviso" + (esError ? " error" : "");
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => el.classList.add("oculto"), 3200);
}

async function exportarArchivo(url, etiqueta) {
  try {
    avisar(`Generando ${etiqueta}...`);
    const r = await api("GET", url);
    avisar(`${etiqueta} guardado en Descargas (se abrió automáticamente).`);
    console.log("Archivo guardado en:", r.ruta);
  } catch (err) {
    avisar(err.message, true);
  }
}

/* ===== Tema (claro / oscuro) ===== */
async function initTema() {
  let tema = "light";
  try {
    const r = await api("GET", "/api/preferencias/tema");
    if (r.valor) tema = r.valor;
  } catch (_) {}
  aplicarTema(tema);
  $("#btn-tema").addEventListener("click", () => {
    const nuevo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    aplicarTema(nuevo);
    api("PUT", "/api/preferencias/tema", { valor: nuevo }).catch(() => {});
  });
}
function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema;
  $("#btn-tema").textContent = tema === "dark" ? "☀️" : "🌙";
}

/* ===== Lista de préstamos ===== */
async function cargarLista(seleccionar) {
  estado.prestamos = await api("GET", "/api/prestamos");
  renderLista();
  if (seleccionar) seleccionar = Number(seleccionar);
  if (seleccionar && estado.prestamos.some((p) => p.id === seleccionar)) {
    abrirPrestamo(seleccionar);
  } else if (estado.actual && estado.prestamos.some((p) => p.id === estado.actual.id)) {
    renderLista();
  }
}

function renderLista() {
  const cont = $("#lista");
  const f = estado.filtro.toLowerCase();
  const lista = estado.prestamos.filter(
    (p) => p.cliente.toLowerCase().includes(f)
      && (!estado.filtroFuente || p.fuente === estado.filtroFuente)
  );
  if (!lista.length) {
    cont.innerHTML = `<p style="color:var(--texto-suave);padding:10px;text-align:center;font-size:.9rem">Sin préstamos para mostrar.</p>`;
    return;
  }
  cont.innerHTML = lista
    .map((p) => {
      const clase = { "Al día": "aldia", Atrasado: "atrasado", Pagado: "pagado" }[p.estado] || "aldia";
      const activa = estado.actual && estado.actual.id === p.id ? " activa" : "";
      return `<div class="tarjeta${activa}" data-id="${p.id}">
        <div class="tarjeta-top">
          <span class="tarjeta-nombre">${escapar(p.cliente)}</span>
          <span class="insignia ${clase}">${escapar(p.estado)}</span>
        </div>
        <div class="tarjeta-monto">Préstamo ${p.id} · ${fmtMoneda(p.monto)} · ${escapar(p.tasa_mensual_pct)}% mensual</div>
        <div class="chip-fuente ${slugFuente(p.fuente)}">${escapar(p.fuente)}</div>
      </div>`;
    })
    .join("");
  cont.querySelectorAll(".tarjeta").forEach((t) =>
    t.addEventListener("click", () => abrirPrestamo(Number(t.dataset.id)))
  );
}

function poblarFiltroFuente() {
  const sel = $("#filtro-fuente");
  const opciones = ['<option value="">Todas las fuentes</option>']
    .concat(estado.fuentes.map((f) => `<option value="${escapar(f)}">${escapar(f)}</option>`));
  sel.innerHTML = opciones.join("");
}

/* ===== Detalle ===== */
async function abrirPrestamo(id) {
  estado.actual = await api("GET", `/api/prestamos/${id}`);
  renderLista();
  renderDetalle();
}

function renderDetalle() {
  const p = estado.actual;
  if (!p) return;
  const r = p.resumen;
  const claseEstado = { "Al día": "aldia", Atrasado: "atrasado", Pagado: "pagado" }[p.estado] || "aldia";
  const formulaTxt = nombreFormula(p.formula);

  $("#detalle").innerHTML = `
    <div class="detalle-cabecera">
      <div class="detalle-titulo">
        <h2>Préstamo ${p.id} — ${escapar(p.cliente.nombre)}</h2>
        <span class="insignia ${claseEstado}">${escapar(p.estado)}</span>
        <span class="chip-fuente ${slugFuente(p.fuente)}">${escapar(p.fuente)}</span>
      </div>
      <div class="detalle-sub">${fmtMoneda(p.monto)} · ${escapar(p.tasa_mensual_pct)}% mensual · Fórmula ${formulaTxt} · ${p.num_cuotas} cuotas</div>
      <div class="detalle-botones">
        <button class="btn btn-sm" id="d-editar">✏️ Editar</button>
        <button class="btn btn-sm" id="d-simular">📈 Simular ampliación</button>
        <button class="btn btn-sm" id="d-excel">📊 Exportar Excel</button>
        <button class="btn btn-sm" id="d-pdf">📄 Exportar PDF</button>
        <button class="btn btn-sm btn-peligro" id="d-eliminar">🗑️ Eliminar</button>
      </div>
      <div class="resumen-cards">
        <div class="resumen-card"><div class="etq">Total a pagar</div><div class="val">${fmtMoneda(r.total)}</div></div>
        <div class="resumen-card"><div class="etq">Intereses</div><div class="val">${fmtMoneda(r.total_interes)}</div></div>
        <div class="resumen-card"><div class="etq">Pagado</div><div class="val">${fmtMoneda(r.pagado)}</div></div>
        <div class="resumen-card"><div class="etq">Por cobrar</div><div class="val">${fmtMoneda(r.por_cobrar)}</div></div>
        <div class="resumen-card"><div class="etq">Cuotas pagadas</div><div class="val">${r.cuotas_pagadas}/${r.num_cuotas}</div></div>
      </div>
      <div class="tabs">
        <button class="tab" data-tab="crono">Cronograma y pagos</button>
        <button class="tab" data-tab="datos">Datos del cliente</button>
        <button class="tab" data-tab="amp">Ampliaciones</button>
      </div>
    </div>
    <div class="tab-cuerpo" id="tab-cuerpo"></div>`;

  $("#d-editar").onclick = () => abrirFormulario(p);
  $("#d-simular").onclick = () => abrirSimulacion(p);
  $("#d-excel").onclick = () => exportarArchivo(`/api/prestamos/${p.id}/excel`, "Excel");
  $("#d-pdf").onclick = () => exportarArchivo(`/api/prestamos/${p.id}/pdf`, "PDF");
  $("#d-eliminar").onclick = () => eliminar(p);
  $("#detalle").querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => { estado.tab = t.dataset.tab; pintarTab(); })
  );
  pintarTab();
}

function pintarTab() {
  const p = estado.actual;
  $("#detalle").querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("activa", t.dataset.tab === estado.tab)
  );
  const cuerpo = $("#tab-cuerpo");
  if (estado.tab === "crono") cuerpo.innerHTML = tablaCronograma(p.cuotas, true);
  else if (estado.tab === "datos") cuerpo.innerHTML = vistaDatos(p);
  else cuerpo.innerHTML = vistaAmpliaciones(p);

  if (estado.tab === "crono") {
    cuerpo.querySelectorAll(".chk").forEach((chk) =>
      chk.addEventListener("change", () => marcarPago(Number(chk.dataset.id), chk.checked))
    );
  }
}

function sumarCampo(cuotas, campo) {
  return cuotas.reduce((a, c) => a + Number(c[campo]), 0);
}

function tablaCronograma(cuotas, conPagos, indiceCorte = -1) {
  const conCarrillo = cuotas.some((c) => c.interes_carrillo !== undefined);
  const regulares = cuotas.filter((c) => !c.es_balon);
  const balon = cuotas.find((c) => c.es_balon);

  const celdaChk = (c) =>
    conPagos
      ? `<td class="centro"><input type="checkbox" class="chk" data-id="${c.id}" ${c.pagada ? "checked" : ""}></td>`
      : "";
  const celdaCarr = (c) =>
    conCarrillo
      ? `<td class="carrillo">${fmtMoneda(c.interes_carrillo || 0)}</td><td class="mio">${fmtMoneda(c.interes_mio || 0)}</td>`
      : "";

  const filas = regulares
    .map((c, i) => {
      const pagada = c.pagada ? " pagada" : "";
      const corte = i === indiceCorte ? " corte" : "";
      return `<tr class="${pagada}${corte}">
        <td class="centro">${c.numero}</td>
        <td class="centro">${fmtFecha(c.fecha)}</td>
        <td class="centro">${c.dias}</td>
        <td>${fmtMoneda(c.interes)}</td>
        ${celdaCarr(c)}
        <td>${fmtMoneda(c.amortizacion)}</td>
        <td>${fmtMoneda(c.cuota)}</td>
        <td>${fmtMoneda(c.saldo)}</td>
        ${celdaChk(c)}
      </tr>`;
    })
    .join("");

  // Totales: solo de las cuotas regulares (el balón va en su propia línea).
  const totInteres = sumarCampo(regulares, "interes");
  const totAmort = sumarCampo(regulares, "amortizacion");
  const totCuota = sumarCampo(regulares, "cuota");
  const totCarrillo = conCarrillo ? sumarCampo(regulares, "interes_carrillo") : 0;
  const totMio = conCarrillo ? sumarCampo(regulares, "interes_mio") : 0;
  const pieCarr = conCarrillo ? `<td>${fmtMoneda(totCarrillo)}</td><td>${fmtMoneda(totMio)}</td>` : "";
  const pie = `<tr class="fila-total">
      <td class="izq" colspan="3">Totales</td>
      <td>${fmtMoneda(totInteres)}</td>
      ${pieCarr}
      <td>${fmtMoneda(totAmort)}</td>
      <td>${fmtMoneda(totCuota)}</td>
      <td></td>
      ${conPagos ? "<td></td>" : ""}
    </tr>`;

  // Línea de pago del saldo de capital (cuota balón), si existe.
  const filaBalon = balon
    ? `<tr class="fila-balon">
        <td class="izq" colspan="3">🏦 Pago del saldo del capital</td>
        <td>${fmtMoneda(balon.interes)}</td>
        ${celdaCarr(balon)}
        <td>${fmtMoneda(balon.amortizacion)}</td>
        <td>${fmtMoneda(balon.cuota)}</td>
        <td>${fmtMoneda(balon.saldo)}</td>
        ${celdaChk(balon)}
      </tr>`
    : "";

  const thCarr = conCarrillo ? '<th>Int. Carrillo</th><th>Mi interés</th>' : "";
  const resumenCarr = conCarrillo
    ? `<div class="ti carrillo-box"><span class="ti-etq">🏦 Interés de Carrillo</span><span class="ti-val">${fmtMoneda(totCarrillo)}</span></div>
       <div class="ti ganancia"><span class="ti-etq">💰 Mi interés</span><span class="ti-val">${fmtMoneda(totMio)}</span></div>`
    : `<div class="ti ganancia"><span class="ti-etq">💰 Ganancia por intereses</span><span class="ti-val">${fmtMoneda(totInteres)}</span></div>`;
  const cardBalon = balon
    ? `<div class="ti capital"><span class="ti-etq">🏦 Pago del saldo del capital</span><span class="ti-val">${fmtMoneda(balon.cuota)}</span></div>`
    : "";

  // Capital recuperado y total a cobrar SÍ incluyen el balón.
  const capitalRecuperado = sumarCampo(cuotas, "amortizacion");
  const totalCobrar = sumarCampo(cuotas, "cuota");

  return `<div class="tabla-wrap"><table class="crono">
    <thead><tr>
      <th class="centro">N°</th><th class="centro">Vencimiento</th><th class="centro">N° Días</th>
      <th>Intereses</th>${thCarr}<th>Amortización</th><th>Cuota</th><th>Saldo Pendiente</th>
      ${conPagos ? '<th class="centro">Pagada</th>' : ""}
    </tr></thead>
    <tbody>${filas}</tbody>
    <tfoot>${pie}${filaBalon}</tfoot>
  </table></div>
  <div class="totales-resumen">
    ${resumenCarr}
    <div class="ti capital"><span class="ti-etq">🔁 Capital recuperado</span><span class="ti-val">${fmtMoneda(capitalRecuperado)}</span></div>
    ${cardBalon}
    <div class="ti"><span class="ti-etq">Total a cobrar</span><span class="ti-val">${fmtMoneda(totalCobrar)}</span></div>
  </div>`;
}

function vistaDatos(p) {
  return `<div class="datos-grid">
    <div class="dato"><div class="etq">Cliente</div><div class="val">${escapar(p.cliente.nombre)}</div></div>
    <div class="dato"><div class="etq">Teléfono</div><div class="val">${escapar(p.cliente.telefono || "—")}</div></div>
    <div class="dato"><div class="etq">Email</div><div class="val">${escapar(p.cliente.email || "—")}</div></div>
    <div class="dato"><div class="etq">Monto</div><div class="val">${fmtMoneda(p.monto)}</div></div>
    <div class="dato"><div class="etq">Tasa mensual</div><div class="val">${escapar(p.tasa_mensual_pct)}%</div></div>
    <div class="dato"><div class="etq">Fórmula de interés</div><div class="val">${nombreFormula(p.formula)}</div></div>
    <div class="dato"><div class="etq">Fuente / Entidad</div><div class="val">${escapar(p.fuente)}</div></div>
    ${Number(p.tasa_carrillo_pct) > 0 ? `<div class="dato"><div class="etq">Tasa mensual de Carrillo</div><div class="val">${escapar(p.tasa_carrillo_pct)}%</div></div>` : ""}
    <div class="dato"><div class="etq">Fecha de desembolso</div><div class="val">${fmtFecha(p.fecha_desembolso)}</div></div>
    <div class="dato"><div class="etq">Primer vencimiento</div><div class="val">${fmtFecha(p.fecha_primer_vencimiento)}</div></div>
    <div class="dato"><div class="etq">N° de cuotas</div><div class="val">${p.num_cuotas}</div></div>
    ${Number(p.capital_final) > 0 ? `<div class="dato"><div class="etq">Devolución de capital al final</div><div class="val">${fmtMoneda(p.capital_final)}</div></div>` : ""}
    <div class="dato"><div class="etq">Estado</div><div class="val">${escapar(p.estado)}</div></div>
  </div>
  <div class="notas-box">${escapar(p.notas) || "<i>Sin notas.</i>"}</div>`;
}

function vistaAmpliaciones(p) {
  if (!p.ampliaciones.length)
    return `<p style="color:var(--texto-suave)">Este préstamo no tiene ampliaciones registradas.</p>`;
  const filas = p.ampliaciones
    .map(
      (a) => `<tr>
      <td class="centro">${fmtFecha(a.fecha)}</td>
      <td>${fmtMoneda(a.monto_extra)}</td>
      <td class="centro">${a.cuotas_agregadas}</td>
      <td class="centro">${fmtFecha(a.creada_en)}</td>
    </tr>`
    )
    .join("");
  return `<div class="tabla-wrap"><table class="crono">
    <thead><tr><th class="centro">Aplicada desde</th><th>Monto extra</th><th class="centro">Cuotas +</th><th class="centro">Registrada</th></tr></thead>
    <tbody>${filas}</tbody></table></div>`;
}

/* ===== Modal genérico ===== */
function abrirModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-fondo").classList.remove("oculto");
}
function cerrarModal() {
  $("#modal-fondo").classList.add("oculto");
  $("#modal").innerHTML = "";
}

/* ===== Formulario crear / editar ===== */
function abrirFormulario(p) {
  const e = p || {};
  const cli = e.cliente || {};
  const hoy = new Date().toISOString().slice(0, 10);
  abrirModal(`
    <div class="modal-cabecera">
      <h3>${p ? "Editar préstamo" : "Nuevo préstamo"}</h3>
      <button class="cerrar" id="m-cerrar">×</button>
    </div>
    <div class="modal-cuerpo">
      <div class="campos">
        <div class="campo"><label>Cliente *</label><input id="f-nombre" value="${escapar(cli.nombre || "")}"></div>
        <div class="campo"><label>Teléfono</label><input id="f-tel" value="${escapar(cli.telefono || "")}"></div>
        <div class="campo"><label>Email</label><input id="f-email" value="${escapar(cli.email || "")}"></div>
        <div class="campo"><label>Monto (S/)</label><input id="f-monto" type="number" step="0.01" min="0" value="${e.monto || ""}"></div>
        <div class="campo"><label>Tasa mensual (%)</label><input id="f-tasa" type="number" step="0.0001" min="0" value="${e.tasa_mensual_pct || ""}"><span class="ayuda">Ej.: 1.4602</span></div>
        <div class="campo"><label>Fórmula de interés</label>
          <select id="f-formula">
            <option value="A"${e.formula === "A" || !e.formula ? " selected" : ""}>A — efectiva (por días)</option>
            <option value="B"${e.formula === "B" ? " selected" : ""}>B — simple (tasa/30 × días)</option>
            <option value="C"${e.formula === "C" ? " selected" : ""}>C — mensual fija (sin días)</option>
          </select>
        </div>
        <div class="campo"><label>Fuente / Entidad</label>
          <select id="f-fuente">
            ${estado.fuentes.map((fu) => `<option value="${escapar(fu)}"${(e.fuente || "Propios") === fu ? " selected" : ""}>${escapar(fu)}</option>`).join("")}
          </select>
        </div>
        <div class="campo" id="campo-carrillo"><label>Tasa mensual de Carrillo (%)</label><input id="f-carrillo" type="number" step="0.0001" min="0" value="${e.tasa_carrillo_pct && Number(e.tasa_carrillo_pct) > 0 ? e.tasa_carrillo_pct : 0}"><span class="ayuda">Parte del interés mensual que le corresponde a Carrillo.</span></div>
        <div class="campo"><label>Fecha de desembolso</label><input id="f-desemb" type="date" value="${e.fecha_desembolso || hoy}"></div>
        <div class="campo"><label>Primer vencimiento</label><input id="f-venc" type="date" value="${e.fecha_primer_vencimiento || ""}"><span class="ayuda">Tú la eliges; puede ser menos de un mes.</span></div>
        <div class="campo"><label>N° de cuotas</label><input id="f-cuotas" type="number" min="1" step="1" value="${e.num_cuotas || 12}"></div>
        <div class="campo ancho"><label>Devolución de capital al final (S/)</label><input id="f-capital" type="number" step="0.01" min="0" value="${e.capital_final ? Number(e.capital_final) : 0}"><span class="ayuda">Saldo de capital que el cliente devuelve al término (cuota balón). Déjalo en 0 si se amortiza todo en las cuotas.</span></div>
        <div class="campo ancho"><label>Notas</label><textarea id="f-notas" rows="2">${escapar(e.notas || "")}</textarea></div>
      </div>
      <div class="previa" id="f-previa">
        <div class="item"><div class="etq">Cuota fija</div><div class="val" id="pv-cuota">—</div></div>
        <div class="item"><div class="etq">Total a pagar</div><div class="val" id="pv-total">—</div></div>
        <div class="item"><div class="etq">Intereses</div><div class="val" id="pv-int">—</div></div>
        <div class="item"><div class="etq">1er interés (días)</div><div class="val" id="pv-c1">—</div></div>
      </div>
    </div>
    <div class="modal-pie">
      <button class="btn" id="m-cancelar">Cancelar</button>
      <button class="btn btn-primario" id="m-guardar">${p ? "Guardar cambios" : "Crear préstamo"}</button>
    </div>`);

  $("#m-cerrar").onclick = cerrarModal;
  $("#m-cancelar").onclick = cerrarModal;
  ["f-nombre", "f-tel", "f-email", "f-monto", "f-tasa", "f-formula", "f-fuente", "f-carrillo", "f-capital", "f-desemb", "f-venc", "f-cuotas", "f-notas"].forEach((id) => {
    const el = document.getElementById(id);
    el.addEventListener("input", previaDebounced);
  });
  $("#f-fuente").addEventListener("change", toggleCampoCarrillo);
  toggleCampoCarrillo();
  $("#m-guardar").onclick = () => guardarPrestamo(p);
  actualizarPrevia();
}

function toggleCampoCarrillo() {
  const esCarrillo = $("#f-fuente").value === "Carrillo Royalti";
  $("#campo-carrillo").style.display = esCarrillo ? "" : "none";
}

function leerFormulario() {
  return {
    cliente: {
      nombre: $("#f-nombre").value, telefono: $("#f-tel").value, email: $("#f-email").value,
    },
    monto: $("#f-monto").value,
    tasa_mensual_pct: $("#f-tasa").value,
    formula: $("#f-formula").value,
    fuente: $("#f-fuente").value,
    tasa_carrillo_pct: $("#f-carrillo").value || "0",
    capital_final: $("#f-capital").value || "0",
    fecha_desembolso: $("#f-desemb").value,
    fecha_primer_vencimiento: $("#f-venc").value,
    num_cuotas: $("#f-cuotas").value,
    notas: $("#f-notas").value,
  };
}

let previaTimer;
function previaDebounced() {
  clearTimeout(previaTimer);
  previaTimer = setTimeout(actualizarPrevia, 350);
}
async function actualizarPrevia() {
  const d = leerFormulario();
  if (!d.monto || !d.tasa_mensual_pct || !d.fecha_desembolso || !d.fecha_primer_vencimiento || !d.num_cuotas) return;
  try {
    const r = await api("POST", "/api/calcular", d);
    $("#pv-cuota").textContent = fmtMoneda(r.cuota_fija);
    $("#pv-total").textContent = fmtMoneda(r.resumen.total);
    $("#pv-int").textContent = fmtMoneda(r.resumen.total_interes);
    const c1 = r.cuotas[0];
    $("#pv-c1").textContent = `${fmtMoneda(c1.interes)} (${c1.dias}d)`;
  } catch (_) {
    $("#pv-cuota").textContent = "—";
  }
}

async function guardarPrestamo(p) {
  try {
    const d = leerFormulario();
    if (p) {
      await api("PUT", `/api/prestamos/${p.id}`, d);
      avisar("Préstamo actualizado.");
      cerrarModal();
      await cargarLista(p.id);
    } else {
      const nuevo = await api("POST", "/api/prestamos", d);
      avisar(`Préstamo ${nuevo.id} creado.`);
      cerrarModal();
      await cargarLista(nuevo.id);
    }
  } catch (err) {
    avisar(err.message, true);
  }
}

/* ===== Simulación de ampliación ===== */
function abrirSimulacion(p) {
  const primeraNoPagada = p.cuotas.find((c) => !c.pagada) || p.cuotas[p.cuotas.length - 1];
  const fechaDef = primeraNoPagada ? primeraNoPagada.fecha : p.fecha_primer_vencimiento;
  abrirModal(`
    <div class="modal-cabecera">
      <h3>Simular ampliación — ${escapar(p.cliente.nombre)}</h3>
      <button class="cerrar" id="m-cerrar">×</button>
    </div>
    <div class="modal-cuerpo">
      <div class="campos">
        <div class="campo"><label>Aplicar desde la fecha</label><input id="s-fecha" type="date" value="${fechaDef}"></div>
        <div class="campo"><label>Monto extra (S/)</label><input id="s-monto" type="number" step="0.01" min="0" value="0"></div>
        <div class="campo"><label>Cuotas a agregar</label><input id="s-cuotas" type="number" step="1" min="0" value="0"></div>
        <div class="campo" style="justify-content:flex-end"><button class="btn btn-primario" id="s-recalcular">Recalcular</button></div>
      </div>
      <div class="previa" id="s-previa"><div class="item"><div class="etq">Ajusta los valores y pulsa «Recalcular».</div></div></div>
      <div id="s-tabla" style="margin-top:14px"></div>
    </div>
    <div class="modal-pie">
      <button class="btn" id="m-cancelar">Cerrar</button>
      <button class="btn btn-primario" id="s-guardar" disabled>Guardar como nueva versión</button>
    </div>`);

  $("#m-cerrar").onclick = cerrarModal;
  $("#m-cancelar").onclick = cerrarModal;
  $("#s-recalcular").onclick = () => recalcularSim(p);
  $("#s-guardar").onclick = () => aplicarSim(p);
  recalcularSim(p);
}

async function recalcularSim(p) {
  const cuerpo = {
    fecha: $("#s-fecha").value,
    monto_extra: $("#s-monto").value || "0",
    cuotas_agregadas: $("#s-cuotas").value || "0",
  };
  try {
    const r = await api("POST", `/api/prestamos/${p.id}/simular`, cuerpo);
    $("#s-previa").innerHTML = `
      <div class="item"><div class="etq">Saldo a la fecha</div><div class="val">${fmtMoneda(r.saldo_base)}</div></div>
      <div class="item"><div class="etq">+ Monto extra</div><div class="val">${fmtMoneda(cuerpo.monto_extra)}</div></div>
      <div class="item"><div class="etq">Nuevo capital</div><div class="val">${fmtMoneda(r.capital_nuevo)}</div></div>
      <div class="item"><div class="etq">Nueva cuota fija</div><div class="val">${fmtMoneda(r.cuota_fija)}</div></div>
      <div class="item"><div class="etq">Cuotas restantes</div><div class="val">${r.cuotas_restantes}</div></div>
      <div class="item"><div class="etq">Total restante</div><div class="val">${fmtMoneda(r.total_restante)}</div></div>`;
    $("#s-tabla").innerHTML = tablaCronograma(r.cuotas, false, r.indice_corte);
    $("#s-guardar").disabled = false;
  } catch (err) {
    avisar(err.message, true);
  }
}

async function aplicarSim(p) {
  if (!confirm("¿Guardar esta simulación como la nueva versión del préstamo?\nEl cronograma se reemplazará desde la fecha de ampliación.")) return;
  const cuerpo = {
    fecha: $("#s-fecha").value,
    monto_extra: $("#s-monto").value || "0",
    cuotas_agregadas: $("#s-cuotas").value || "0",
  };
  try {
    await api("POST", `/api/prestamos/${p.id}/ampliar`, cuerpo);
    avisar("Ampliación aplicada.");
    cerrarModal();
    await cargarLista(p.id);
  } catch (err) {
    avisar(err.message, true);
  }
}

/* ===== Pagos / eliminar ===== */
async function marcarPago(cuotaId, pagada) {
  try {
    estado.actual = await api("POST", `/api/prestamos/${estado.actual.id}/pagos`, {
      cuota_id: cuotaId, pagada,
    });
    renderDetalle();
    cargarLista(estado.actual.id);
  } catch (err) {
    avisar(err.message, true);
  }
}

async function eliminar(p) {
  if (!confirm(`¿Eliminar el préstamo ${p.id} de ${p.cliente.nombre}?\nEsta acción no se puede deshacer.`)) return;
  try {
    await api("DELETE", `/api/prestamos/${p.id}`);
    estado.actual = null;
    avisar("Préstamo eliminado.");
    $("#detalle").innerHTML = `<div class="vacio"><div class="vacio-icono">📄</div><p>Selecciona un préstamo de la lista<br>o crea uno nuevo para empezar.</p></div>`;
    await cargarLista();
  } catch (err) {
    avisar(err.message, true);
  }
}

/* ===== Dashboard de patrimonio ===== */
const MESES_ABR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
function fmtMes(m) {
  const [a, mm] = m.split("-");
  return `${MESES_ABR[parseInt(mm, 10) - 1]} ${a}`;
}

async function mostrarDashboard() {
  let data;
  try {
    data = await api("GET", "/api/dashboard");
  } catch (err) {
    avisar(err.message, true);
    return;
  }
  renderDashboard(data);
  $(".contenedor").classList.add("oculto");
  $("#vista-dashboard").classList.remove("oculto");
}

function ocultarDashboard() {
  $("#vista-dashboard").classList.add("oculto");
  $(".contenedor").classList.remove("oculto");
}

function renderDashboard(data) {
  const meses = data.meses;
  const t = data.totales;
  const hoy = new Date().toISOString().slice(0, 7);
  let actual = meses.find((m) => m.mes === hoy);
  if (!actual) {
    const previas = meses.filter((m) => m.mes <= hoy);
    actual = previas.length ? previas[previas.length - 1] : (meses[0] || null);
  }
  const a = actual || { interes_mio: "0", amortizacion: "0", impuesto: "0", saldo_pendiente: "0", falta_cobrar: "0" };
  const mesActual = actual ? actual.mes : "";

  const maxInt = Math.max(1, ...meses.map((m) => Number(m.interes_mio)));
  const barras = meses
    .map((m) => {
      const h = Math.round((Number(m.interes_mio) / maxInt) * 100);
      return `<div class="barra-col${m.mes === mesActual ? " actual" : ""}" title="${fmtMes(m.mes)}: ${fmtMoneda(m.interes_mio)} (mío)">
        <div class="barra" style="height:${h}%"></div>
        <div class="barra-lbl">${m.mes.slice(2).replace("-", "/")}</div>
      </div>`;
    })
    .join("");

  const filas = meses
    .map((m) => `<tr class="${m.mes === mesActual ? "mes-actual" : ""}">
        <td class="izq">${fmtMes(m.mes)}</td>
        <td>${fmtMoneda(m.interes_mio)}</td>
        <td>${fmtMoneda(m.amortizacion)}</td>
        <td>${fmtMoneda(m.impuesto)}</td>
        <td>${fmtMoneda(m.saldo_pendiente)}</td>
        <td>${fmtMoneda(m.falta_cobrar)}</td>
      </tr>`)
    .join("");

  $("#vista-dashboard").innerHTML = `
    <div class="dash-cab">
      <button class="btn" id="dash-volver">← Préstamos</button>
      <h2>Dashboard de patrimonio</h2>
      <span class="dash-hint">Mes actual: <b>${fmtMes(hoy)}</b></span>
    </div>
    <div class="dash-cards">
      <div class="dcard patri"><div class="etq">🏦 Patrimonio (capital pendiente)</div><div class="val">${fmtMoneda(a.saldo_pendiente)}</div></div>
      <div class="dcard"><div class="etq">💵 Falta cobrar (capital + interés)</div><div class="val">${fmtMoneda(a.falta_cobrar)}</div></div>
      <div class="dcard"><div class="etq">📅 Mi interés (este mes)</div><div class="val">${fmtMoneda(a.interes_mio)}</div></div>
      <div class="dcard"><div class="etq">🔁 Amortización (este mes)</div><div class="val">${fmtMoneda(a.amortizacion)}</div></div>
      <div class="dcard imp"><div class="etq">🧾 Impuesto a pagar (este mes, 5%)</div><div class="val">${fmtMoneda(a.impuesto)}</div></div>
    </div>
    <div class="dash-cards">
      <div class="dcard"><div class="etq">Σ Mi interés (total)</div><div class="val">${fmtMoneda(t.interes_mio)}</div></div>
      <div class="dcard"><div class="etq">Σ Amortización (capital)</div><div class="val">${fmtMoneda(t.amortizacion)}</div></div>
      <div class="dcard imp"><div class="etq">Σ Impuesto total (5%)</div><div class="val">${fmtMoneda(t.impuesto)}</div></div>
      <div class="dcard excl"><div class="etq">⛔ Interés de Carrillo (no entra)</div><div class="val">${fmtMoneda(t.interes_carrillo)}</div></div>
    </div>
    <h3 class="dash-sub">Mi interés por mes</h3>
    <div class="dash-chart">${barras}</div>
    <h3 class="dash-sub">Historial mensual</h3>
    <div class="tabla-wrap dash-tabla">
      <table class="crono">
        <thead><tr>
          <th class="izq">Mes</th><th>Mi interés</th><th>Amortización</th>
          <th>Impuesto (5%)</th><th>Capital pendiente</th><th>Falta cobrar</th>
        </tr></thead>
        <tbody>${filas}</tbody>
      </table>
    </div>`;

  $("#dash-volver").onclick = ocultarDashboard;
}

/* ===== Arranque ===== */
async function init() {
  $("#btn-dashboard").addEventListener("click", mostrarDashboard);
  $("#btn-nuevo").addEventListener("click", () => abrirFormulario(null));
  $("#buscar").addEventListener("input", (e) => { estado.filtro = e.target.value; renderLista(); });
  $("#filtro-fuente").addEventListener("change", (e) => { estado.filtroFuente = e.target.value; renderLista(); });
  $("#modal-fondo").addEventListener("click", (e) => { if (e.target.id === "modal-fondo") cerrarModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarModal(); });
  initTema();
  try { estado.fuentes = (await api("GET", "/api/fuentes")).fuentes; } catch (_) {}
  poblarFiltroFuente();
  cargarLista();
}
document.addEventListener("DOMContentLoaded", init);
