/* ═══════════════════════════════════════════════════════════════════════
   Claro Ventas — Detalle de Productividad por Agente
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

const GAUGE_FIELD = {
  ocupacion:      'pct_ocupacion',
  disponibilidad: 'pct_disponibilidad',
  pausa:          'pct_pausa',
  eficiencia:     'pct_eficiencia',
  utilizacion:    'pct_utilizacion',
  shrinkage:      'pct_shrinkage',
};

const state = {
  agente: {
    data:        [],
    filtered:    [],
    page:        1,
    pageSize:    25,
    sortCol:     'Asesor',
    sortDir:     'asc',
    searchName:  '',
    searchSup:   '',
  },
  refreshTimer: null,
};

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadFilterOptions();
  refreshReport();
  startAutoRefresh();
});

// ════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
  ['f-supervisor', 'f-campana'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', debounce(refreshReport, 250));
  });

  document.getElementById('btn-clear-filters').addEventListener('click', clearFilters);
  document.getElementById('btn-refresh').addEventListener('click', () => refreshReport(true));

  ['search-name', 'search-supervisor'].forEach(id => {
    document.getElementById(id).addEventListener('input', debounce(() => {
      state.agente.searchName = document.getElementById('search-name').value.trim().toLowerCase();
      state.agente.searchSup  = document.getElementById('search-supervisor').value.trim().toLowerCase();
      state.agente.page = 1;
      applyAgenteFilters();
      renderAgenteTable();
    }, 250));
  });

  document.getElementById('page-size').addEventListener('change', e => {
    state.agente.pageSize = parseInt(e.target.value, 10);
    state.agente.page = 1;
    renderAgenteTable();
  });

  document.querySelectorAll('#view-toggle .view-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#view-toggle .view-toggle__btn').forEach(b => b.classList.remove('view-toggle__btn--active'));
      btn.classList.add('view-toggle__btn--active');
      document.getElementById('agente-table').classList.toggle('mode-summary', btn.dataset.mode === 'summary');
    });
  });

  document.getElementById('btn-first').addEventListener('click', () => goToPage(1));
  document.getElementById('btn-prev').addEventListener('click',  () => goToPage(state.agente.page - 1));
  document.getElementById('btn-next').addEventListener('click',  () => goToPage(state.agente.page + 1));
  document.getElementById('btn-last').addEventListener('click',  () => {
    const pages = Math.ceil(state.agente.filtered.length / state.agente.pageSize);
    goToPage(pages);
  });

  document.querySelectorAll('#agente-table .sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (state.agente.sortCol === col) {
        state.agente.sortDir = state.agente.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.agente.sortCol = col;
        state.agente.sortDir = 'asc';
      }
      updateSortHeaders();
      applyAgenteFilters();
      renderAgenteTable();
    });
  });

  document.getElementById('btn-export-excel').addEventListener('click', exportExcel);
  document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
}

// ════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ════════════════════════════════════════════════════════════════════════

function buildQueryParams() {
  const params = new URLSearchParams();
  const supervisor = document.getElementById('f-supervisor')?.value?.trim();
  const campana    = document.getElementById('f-campana')?.value?.trim();
  if (supervisor) params.set('supervisor', supervisor);
  if (campana)    params.set('campana', campana);
  return params.toString();
}

async function refreshReport(manual = false) {
  if (manual) {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 800);
  }

  setLoading(true);

  try {
    const params = buildQueryParams();
    const res = await fetch('/api/detalle-agente?' + params);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`);

    updateAll(data);
    setStatus(true);
  } catch (err) {
    console.error('[DetalleAgente] Error al cargar datos:', err);
    setStatus(false);
    const isDbError = /mysql|conexi[oó]n|econnrefused/i.test(err.message);
    const msg = isDbError
      ? 'No se pudo conectar a la base de datos. Se mantienen los últimos datos disponibles.'
      : 'Error al cargar datos: ' + err.message;
    showToast(msg, 'error');
  } finally {
    setLoading(false);
  }
}

async function loadFilterOptions() {
  try {
    const res  = await fetch('/api/detalle-agente/filters');
    const opts = await res.json();

    const supSel = document.getElementById('f-supervisor');
    opts.supervisors.forEach(s => {
      const o = document.createElement('option');
      o.value = s; o.textContent = s;
      supSel.appendChild(o);
    });

    const camSel = document.getElementById('f-campana');
    opts.campanas.forEach(c => {
      const o = document.createElement('option');
      o.value = c; o.textContent = c;
      camSel.appendChild(o);
    });
  } catch (e) {
    console.warn('[DetalleAgente] No se pudieron cargar opciones de filtro:', e);
  }
}

function clearFilters() {
  document.getElementById('f-supervisor').value = '';
  document.getElementById('f-campana').value = '';
  document.getElementById('search-name').value = '';
  document.getElementById('search-supervisor').value = '';
  state.agente.searchName = '';
  state.agente.searchSup  = '';
  refreshReport();
}

// ════════════════════════════════════════════════════════════════════════
// UPDATE ALL
// ════════════════════════════════════════════════════════════════════════

function updateAll(data) {
  updateKPIs(data.kpis);
  updateGauges(data.kpis);
  renderRankings(data.agentes || []);

  state.agente.data = data.agentes || [];
  applyAgenteFilters();
  renderAgenteTable();

  const el = document.getElementById('last-update');
  if (el) el.textContent = data.last_update || '—';
}

// ════════════════════════════════════════════════════════════════════════
// RANKINGS — quiénes necesitan más atención, de un vistazo
// ════════════════════════════════════════════════════════════════════════

function renderRankings(agentes) {
  renderRankPanel('rank-eficiencia', agentes, 'Pct_Eficiencia', 'asc',  v => `${v}%`);
  renderRankPanel('rank-shrinkage',  agentes, 'Pct_Shrinkage',  'desc', v => `${v}%`);
  renderRankPanel('rank-aht',        agentes, 'T_AHT_seg',      'desc', (v, r) => r.T_AHT);
}

function renderRankPanel(elId, agentes, field, dir, formatValue, topN = 5) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (!agentes.length) {
    el.innerHTML = '<p class="empty-row">Sin datos</p>';
    return;
  }

  const sorted = [...agentes].sort((a, b) => dir === 'asc' ? a[field] - b[field] : b[field] - a[field]);
  const top = sorted.slice(0, topN);
  const maxVal = Math.max(...top.map(r => r[field]), 1);

  el.innerHTML = top.map(r => {
    const value = r[field];
    const widthPct = Math.max(4, Math.round((value / maxVal) * 100));
    return `
      <div class="rank-row">
        <span class="rank-name" title="${esc(r.Asesor)}">${esc(r.Asesor)}</span>
        <div class="rank-bar"><div class="rank-bar__fill" style="width:${widthPct}%"></div></div>
        <span class="rank-value">${formatValue(value, r)}</span>
      </div>`;
  }).join('');
}

// ════════════════════════════════════════════════════════════════════════
// KPIs
// ════════════════════════════════════════════════════════════════════════

function updateKPIs(kpis) {
  if (!kpis) return;
  setKPI('kpi-total-agentes',  kpis.total_agentes);
  setKPI('kpi-total-llamadas', kpis.total_llamadas);
  setKPI('kpi-total-ventas',   kpis.total_ventas);
  setKPI('kpi-aht-prom',       kpis.aht_prom);
  setKPI('kpi-total-desconex', kpis.total_desconexiones);
  setKPI('kpi-desconex-prom',  kpis.desconex_prom);
}

function setKPI(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = value ?? '—';
    el.classList.add('kpi-updated');
    setTimeout(() => el.classList.remove('kpi-updated'), 600);
  }
}

// ════════════════════════════════════════════════════════════════════════
// GAUGES SEGMENTADOS (custom canvas)
// ════════════════════════════════════════════════════════════════════════

function updateGauges(kpis) {
  if (!kpis) return;
  document.querySelectorAll('.gauge-canvas').forEach(canvas => {
    const key = canvas.dataset.gauge;
    const field = GAUGE_FIELD[key];
    const pct = kpis[field] ?? 0;
    drawSegmentedGauge(canvas, pct);
  });
}

function drawSegmentedGauge(canvas, pct) {
  const dpr = window.devicePixelRatio || 1;
  if (!canvas._scaled) {
    canvas._logicalSize = parseFloat(canvas.getAttribute('width'));
    canvas.width = canvas._logicalSize * dpr;
    canvas.height = canvas._logicalSize * dpr;
    canvas._scaled = true;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const size = canvas._logicalSize;
  const cx = size / 2, cy = size / 2;
  const radius = size * 0.36;
  const numTicks = 40;
  const gapFraction = 0.35;
  const anglePerTick = (2 * Math.PI) / numTicks;
  const tickAngle = anglePerTick * (1 - gapFraction);

  cancelAnimationFrame(canvas._raf);
  const duration = 800;
  const start = performance.now();

  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    draw((pct / 100) * eased);
    if (t < 1) canvas._raf = requestAnimationFrame(frame);
  }

  function draw(filledRatio) {
    ctx.clearRect(0, 0, size, size);
    const filledTicks = Math.round(filledRatio * numTicks);
    let angle = -Math.PI / 2;
    for (let i = 0; i < numTicks; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, radius, angle, angle + tickAngle);
      ctx.lineWidth = size * 0.09;
      ctx.lineCap = 'round';
      ctx.strokeStyle = i < filledTicks ? '#DA291C' : '#F3D6D3';
      ctx.stroke();
      angle += anglePerTick;
    }
    ctx.fillStyle = '#212121';
    ctx.font = `700 ${size * 0.15}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(round1(pct) + '%', cx, cy);
  }

  canvas._raf = requestAnimationFrame(frame);
}

// ════════════════════════════════════════════════════════════════════════
// DETAIL TABLE
// ════════════════════════════════════════════════════════════════════════

function applyAgenteFilters() {
  let data = [...state.agente.data];

  if (state.agente.searchName) {
    data = data.filter(r => (r.Asesor || '').toLowerCase().includes(state.agente.searchName));
  }
  if (state.agente.searchSup) {
    data = data.filter(r => (r.Supervisor || '').toLowerCase().includes(state.agente.searchSup));
  }

  const col = state.agente.sortCol;
  const dir = state.agente.sortDir === 'asc' ? 1 : -1;
  data.sort((a, b) => {
    const va = a[col] ?? '';
    const vb = b[col] ?? '';
    return va < vb ? -dir : va > vb ? dir : 0;
  });

  state.agente.filtered = data;
  document.getElementById('agente-count').textContent =
    `${data.length} agente${data.length !== 1 ? 's' : ''} encontrado${data.length !== 1 ? 's' : ''}`;
}

function renderAgenteTable() {
  const tbody = document.getElementById('agente-tbody');
  const { filtered, page, pageSize } = state.agente;

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="21" class="empty-row">Sin resultados para los filtros aplicados</td></tr>';
    renderPagination(0, page, pageSize);
    return;
  }

  const start = (page - 1) * pageSize;
  const slice = filtered.slice(start, start + pageSize);

  tbody.innerHTML = slice.map(r => `
    <tr>
      <td><strong>${esc(r.Asesor || '—')}</strong></td>
      <td>${esc(r.Supervisor || '—')}</td>
      <td><span style="font-size:0.78rem;color:#757575">${esc(r.Campana || '—')}</span></td>
      <td class="text-center">${neutralBadge(r.T_logueado)}</td>
      <td class="text-center">${r.Llamadas}</td>
      <td class="text-center">${r.Llamadas_Inb}</td>
      <td class="text-center">${r.Llamadas_Out}</td>
      <td class="text-center">${r.Ventas_Inb}</td>
      <td class="text-center">${r.Ventas_Out}</td>
      <td class="text-center">${neutralBadge(r.T_AHT)}</td>
      <td class="text-center">${neutralBadge(r.T_ACW)}</td>
      <td class="text-center">${neutralBadge(r.T_Espera)}</td>
      <td class="text-center">${neutralBadge(r.T_Pausa_Produ)}</td>
      <td class="text-center">${countBadge(r.Cant_Desconex, 0, 3)}</td>
      <td class="text-center">${neutralBadge(r.T_Desconex)}</td>
      <td class="text-center">${pctBadge(r.Pct_Pausa, 20, 35)}</td>
      <td class="text-center">${pctBadge(r.Pct_Ocupacion, 70, 50, true)}</td>
      <td class="text-center">${pctBadge(r.Pct_Disponibilidad, 20, 40)}</td>
      <td class="text-center">${pctBadge(r.Pct_Utilizacion, 70, 50, true)}</td>
      <td class="text-center">${pctBadge(r.Pct_Shrinkage, 20, 35)}</td>
      <td class="text-center">${pctBadge(r.Pct_Eficiencia, 60, 40, true)}</td>
    </tr>`).join('');

  renderPagination(filtered.length, page, pageSize);
}

function renderPagination(total, page, pageSize) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  document.getElementById('page-info').textContent = `Página ${page} de ${pages}`;
  document.getElementById('btn-first').disabled = page <= 1;
  document.getElementById('btn-prev').disabled  = page <= 1;
  document.getElementById('btn-next').disabled  = page >= pages;
  document.getElementById('btn-last').disabled  = page >= pages;
}

function goToPage(n) {
  const pages = Math.max(1, Math.ceil(state.agente.filtered.length / state.agente.pageSize));
  state.agente.page = Math.min(Math.max(1, n), pages);
  renderAgenteTable();
}

function updateSortHeaders() {
  document.querySelectorAll('#agente-table .sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === state.agente.sortCol) {
      th.classList.add('sort-' + state.agente.sortDir);
    }
  });
}

// ════════════════════════════════════════════════════════════════════════
// EXPORT
// ════════════════════════════════════════════════════════════════════════

function exportExcel() {
  if (!state.agente.filtered.length) {
    showToast('No hay datos para exportar', 'error');
    return;
  }
  const rows = state.agente.filtered.map(r => ({
    Asesor: r.Asesor || '', Supervisor: r.Supervisor || '', Campaña: r.Campana || '',
    T_Logueado: r.T_logueado, Llamadas: r.Llamadas, Llamadas_Inb: r.Llamadas_Inb, Llamadas_Out: r.Llamadas_Out,
    Ventas_Inb: r.Ventas_Inb, Ventas_Out: r.Ventas_Out, T_AHT: r.T_AHT, T_ACW: r.T_ACW, T_Espera: r.T_Espera,
    T_Pausa_Produ: r.T_Pausa_Produ, Cant_Desconex: r.Cant_Desconex, T_Desconex: r.T_Desconex,
    Pct_Pausa: r.Pct_Pausa, Pct_Ocupacion: r.Pct_Ocupacion, Pct_Disponibilidad: r.Pct_Disponibilidad,
    Pct_Utilizacion: r.Pct_Utilizacion, Pct_Shrinkage: r.Pct_Shrinkage, Pct_Eficiencia: r.Pct_Eficiencia,
  }));
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'DetalleAgente');
  XLSX.writeFile(wb, `detalle_agente_claro_${dateStamp()}.xlsx`);
  showToast('Exportado a Excel correctamente', 'ok');
}

function exportCSV() {
  if (!state.agente.filtered.length) {
    showToast('No hay datos para exportar', 'error');
    return;
  }
  const headers = ['Asesor','Supervisor','Campaña','T_Logueado','Llamadas','Llamadas_Inb','Llamadas_Out','Ventas_Inb','Ventas_Out','T_AHT','T_ACW','T_Espera','T_Pausa_Produ','Cant_Desconex','T_Desconex','Pct_Pausa','Pct_Ocupacion','Pct_Disponibilidad','Pct_Utilizacion','Pct_Shrinkage','Pct_Eficiencia'];
  const rows = state.agente.filtered.map(r => [
    csvCell(r.Asesor), csvCell(r.Supervisor), csvCell(r.Campana),
    csvCell(r.T_logueado), csvCell(r.Llamadas), csvCell(r.Llamadas_Inb), csvCell(r.Llamadas_Out),
    csvCell(r.Ventas_Inb), csvCell(r.Ventas_Out), csvCell(r.T_AHT), csvCell(r.T_ACW), csvCell(r.T_Espera),
    csvCell(r.T_Pausa_Produ), csvCell(r.Cant_Desconex), csvCell(r.T_Desconex),
    csvCell(r.Pct_Pausa), csvCell(r.Pct_Ocupacion), csvCell(r.Pct_Disponibilidad),
    csvCell(r.Pct_Utilizacion), csvCell(r.Pct_Shrinkage), csvCell(r.Pct_Eficiencia),
  ].join(','));
  const content = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `detalle_agente_claro_${dateStamp()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Exportado a CSV correctamente', 'ok');
}

// ════════════════════════════════════════════════════════════════════════
// AUTO-REFRESH
// ════════════════════════════════════════════════════════════════════════

const REFRESH_INTERVAL_MS = 30 * 60 * 1000;

function startAutoRefresh() {
  clearInterval(state.refreshTimer);
  state.refreshTimer = setInterval(() => refreshReport(), REFRESH_INTERVAL_MS);
}

// ════════════════════════════════════════════════════════════════════════
// UI HELPERS
// ════════════════════════════════════════════════════════════════════════

function setLoading(on) {
  document.getElementById('loading-overlay').classList.toggle('active', on);
}

function setStatus(ok) {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  if (dot)  dot.className  = 'status-dot ' + (ok ? 'status-dot--ok' : 'status-dot--error');
  if (text) text.textContent = ok ? 'Conectado' : 'Error de conexión';
}

function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (type ? ' toast--' + type : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3500);
}

function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function csvCell(val) {
  const s = String(val ?? '');
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

// ── Formato condicional (badges de color + icono) ────────────────────────

function neutralBadge(str) {
  return `<span class="badge-time badge-time--neutral">${str}</span>`;
}

function pctBadge(value, warnAt, dangerAt, inverse) {
  let level;
  if (inverse) {
    level = value < dangerAt ? 'danger' : value < warnAt ? 'warn' : 'ok';
  } else {
    level = value > dangerAt ? 'danger' : value >= warnAt ? 'warn' : 'ok';
  }
  const icon = level === 'danger' ? '🔴' : level === 'warn' ? '🟡' : '✅';
  return `<span class="badge-time badge-time--${level}">${icon} ${value}%</span>`;
}

function countBadge(n, warnAt, dangerAt) {
  const level = n > dangerAt ? 'danger' : n > warnAt ? 'warn' : 'ok';
  const icon = level === 'danger' ? '🔴' : level === 'warn' ? '🟡' : '✅';
  return `<span class="badge-time badge-time--${level}"><strong>${icon} ${n}</strong></span>`;
}

function dateStamp() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
}
