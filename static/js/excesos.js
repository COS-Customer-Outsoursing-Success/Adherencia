/* ═══════════════════════════════════════════════════════════════════════
   Claro Ventas — Reporte de Excesos
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

const COLORS = {
  red:    '#DA291C',
  green:  '#2E7D32',
  yellow: '#F57F17',
  blue:   '#1565C0',
};

const state = {
  agente: {
    data:        [],
    filtered:    [],
    page:        1,
    pageSize:    25,
    sortCol:     'T_Exceso_Total_seg',
    sortDir:     'desc',
    searchName:  '',
    searchSup:   '',
  },
  refreshTimer: null,
};

document.addEventListener('DOMContentLoaded', () => {
  setDefaultDateRange();
  setupEventListeners();
  loadFilterOptions();
  refreshReport();
  startAutoRefresh();
});

// ════════════════════════════════════════════════════════════════════════
// RANGO DE FECHAS POR DEFECTO
// ════════════════════════════════════════════════════════════════════════
// Siempre hoy. Debe reflejar utils/daterange.py:default_range().

function getDefaultDateRange() {
  const iso = new Date().toISOString().slice(0, 10);
  return { inicio: iso, fin: iso };
}

function setDefaultDateRange() {
  const { inicio, fin } = getDefaultDateRange();
  const ini = document.getElementById('f-fecha-ini');
  const end = document.getElementById('f-fecha-fin');
  if (ini) ini.value = inicio;
  if (end) end.value = fin;
}

// El atributo min="2026-08-01" del input solo restringe el calendario visual;
// no impide teclear una fecha manualmente. Se recorta también aquí para que
// la consulta y lo que se ve en el input nunca queden por debajo del histórico
// disponible (debe reflejar utils/daterange.py:MIN_AVAILABLE_DATE).
const MIN_AVAILABLE_DATE = '2026-08-01';

function clampDateFilters() {
  const ini = document.getElementById('f-fecha-ini');
  const fin = document.getElementById('f-fecha-fin');
  if (ini && ini.value && ini.value < MIN_AVAILABLE_DATE) ini.value = MIN_AVAILABLE_DATE;
  if (fin && fin.value && fin.value < MIN_AVAILABLE_DATE) fin.value = MIN_AVAILABLE_DATE;
}

// ════════════════════════════════════════════════════════════════════════
// SUPERVISOR (multiselect por checkboxes)
// ════════════════════════════════════════════════════════════════════════

function populateSupervisorOptions(names) {
  const list = document.getElementById('f-supervisor-list');
  if (!list) return;
  list.innerHTML = names.map(name => `
    <label class="ms-dropdown__option">
      <input type="checkbox" value="${esc(name)}" /> ${esc(name)}
    </label>`).join('');
}

function getSelectedSupervisors() {
  return [...document.querySelectorAll('#f-supervisor-list input[type="checkbox"]:checked')].map(cb => cb.value);
}

function updateSupervisorTrigger() {
  const textEl = document.getElementById('f-supervisor-trigger-text');
  if (!textEl) return;
  const selected = getSelectedSupervisors();
  textEl.textContent = selected.length === 0 ? 'Todos'
    : selected.length === 1 ? selected[0]
    : `${selected.length} seleccionados`;
}

function resetSupervisorFilter() {
  const all = document.getElementById('f-supervisor-all');
  if (all) all.checked = true;
  document.querySelectorAll('#f-supervisor-list input[type="checkbox"]').forEach(cb => { cb.checked = false; });
  updateSupervisorTrigger();
}

function setupSupervisorMultiselect(onChange) {
  const wrapper = document.getElementById('f-supervisor');
  const trigger = document.getElementById('f-supervisor-trigger');
  const panel   = document.getElementById('f-supervisor-panel');
  const all     = document.getElementById('f-supervisor-all');
  const list    = document.getElementById('f-supervisor-list');
  if (!wrapper || !trigger || !panel || !all || !list) return;

  trigger.addEventListener('click', () => {
    const willOpen = panel.hidden;
    panel.hidden = !willOpen;
    trigger.setAttribute('aria-expanded', String(willOpen));
  });

  document.addEventListener('click', e => {
    if (!wrapper.contains(e.target) && !panel.hidden) {
      panel.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    }
  });

  all.addEventListener('change', () => {
    if (all.checked) {
      list.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
    }
    updateSupervisorTrigger();
    onChange();
  });

  list.addEventListener('change', e => {
    if (!e.target.matches('input[type="checkbox"]')) return;
    const anyChecked = list.querySelectorAll('input[type="checkbox"]:checked').length > 0;
    all.checked = !anyChecked;
    updateSupervisorTrigger();
    onChange();
  });
}

// ════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
  ['f-campana', 'f-solo-exceso', 'f-fecha-ini', 'f-fecha-fin'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', debounce(refreshReport, 250));
  });
  setupSupervisorMultiselect(debounce(refreshReport, 250));

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
  clampDateFilters();
  const params = new URLSearchParams();
  const campana    = document.getElementById('f-campana')?.value?.trim();
  const soloExceso = document.getElementById('f-solo-exceso')?.checked;
  const fechaIni   = document.getElementById('f-fecha-ini')?.value?.trim();
  const fechaFin   = document.getElementById('f-fecha-fin')?.value?.trim();
  getSelectedSupervisors().forEach(s => params.append('supervisor', s));
  if (campana)    params.set('campana', campana);
  if (soloExceso) params.set('solo_con_exceso', '1');
  if (fechaIni)   params.set('fecha_inicio', fechaIni);
  if (fechaFin)   params.set('fecha_fin', fechaFin);
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
    const res = await fetch('/api/excesos?' + params);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`);

    updateAll(data);
    setStatus(true);
  } catch (err) {
    console.error('[Excesos] Error al cargar datos:', err);
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
    const res  = await fetch('/api/excesos/filters');
    const opts = await res.json();

    populateSupervisorOptions(opts.supervisors);

    const camSel = document.getElementById('f-campana');
    opts.campanas.forEach(c => {
      const o = document.createElement('option');
      o.value = c; o.textContent = c;
      camSel.appendChild(o);
    });
  } catch (e) {
    console.warn('[Excesos] No se pudieron cargar opciones de filtro:', e);
  }
}

function clearFilters() {
  resetSupervisorFilter();
  document.getElementById('f-campana').value = '';
  document.getElementById('f-solo-exceso').checked = false;
  document.getElementById('search-name').value = '';
  document.getElementById('search-supervisor').value = '';
  state.agente.searchName = '';
  state.agente.searchSup  = '';
  setDefaultDateRange();
  refreshReport();
}

// ════════════════════════════════════════════════════════════════════════
// UPDATE ALL
// ════════════════════════════════════════════════════════════════════════

function updateAll(data) {
  updateKPIs(data.kpis);
  renderExcesoDonut(data.supervisors || []);
  renderExcesoBars(data.supervisors || []);
  renderSupervisorTable(data.supervisors || []);

  state.agente.data = data.agentes || [];
  applyAgenteFilters();
  renderAgenteTable();

  const el = document.getElementById('last-update');
  if (el) el.textContent = data.last_update || '—';
}

// ════════════════════════════════════════════════════════════════════════
// KPIs
// ════════════════════════════════════════════════════════════════════════

function updateKPIs(kpis) {
  if (!kpis) return;
  setKPI('kpi-total-agentes', kpis.total_agentes);
  setKPI('kpi-con-exceso',    kpis.agentes_con_exceso);
  setKPI('kpi-pct-exceso',    kpis.pct_con_exceso + '%');
  setKPI('kpi-exceso-alm',    kpis.total_exceso_alm_min);
  setKPI('kpi-exceso-break',  kpis.total_exceso_break_min);
  setKPI('kpi-exceso-bano',   kpis.total_exceso_bano_min);
  setKPI('kpi-exceso-total',  kpis.total_exceso_min);
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
// EXCESO POR SUPERVISOR — dona (composición total) + barras apiladas (por supervisor)
// ════════════════════════════════════════════════════════════════════════

const EXCESO_TIPOS = [
  { key: 'exceso_alm_min',   name: 'Almuerzo', cls: 'alm',   color: '#1565C0' },
  { key: 'exceso_break_min', name: 'Break',    cls: 'break', color: '#F57C00' },
  { key: 'exceso_bano_min',  name: 'Baño',     cls: 'bano',  color: '#DA291C' },
  { key: 'exceso_dead_min',  name: 'Desconexión',    cls: 'dead',  color: '#6A1B9A' },
  { key: 'exceso_pantalla_min', name: 'Pantalla Verde', cls: 'pv', color: '#2E9E5B' },
];

function round1(n) {
  return Math.round(n * 10) / 10;
}

function renderExcesoDonut(supervisors) {
  const svg = document.getElementById('exceso-donut');
  if (!svg) return;

  const totales = EXCESO_TIPOS.map(t => ({
    ...t, min: supervisors.reduce((sum, s) => sum + (s[t.key] || 0), 0),
  }));
  const total = totales.reduce((sum, t) => sum + t.min, 0);
  setKPI('polar-total-value', Math.round(total));

  const R = 80, C = 2 * Math.PI * R;
  let offset = 0;
  const arcs = total > 0 ? totales.map(t => {
    const len = (t.min / total) * C;
    const arc = `<circle cx="100" cy="100" r="${R}" fill="none" stroke="${t.color}" stroke-width="26"
      stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}" transform="rotate(-90 100 100)">
      <title>${t.name}: ${round1(t.min)} min (${Math.round(t.min / total * 100)}%)</title></circle>`;
    offset += len;
    return arc;
  }).join('') : '';
  svg.innerHTML = `<circle cx="100" cy="100" r="${R}" fill="none" stroke="#eee" stroke-width="26"/>${arcs}`;

  const legend = document.getElementById('exceso-donut-legend');
  if (legend) {
    legend.innerHTML = totales.map(t => `
      <div class="polar-legend__item">
        <span class="polar-dot polar-dot--${t.cls}"></span> ${t.name}
        <strong>${round1(t.min)} min</strong>
        <span class="exceso-pct">${total > 0 ? Math.round(t.min / total * 100) : 0}%</span>
      </div>`).join('');
  }
}

function renderExcesoBars(supervisors) {
  const el = document.getElementById('polar-ranking');
  if (!el) return;
  const sorted = [...supervisors].sort((a, b) => b.exceso_total_min - a.exceso_total_min);

  if (!sorted.length) {
    el.innerHTML = '<p class="empty-row">Sin datos para mostrar</p>';
    return;
  }

  const max = Math.max(...sorted.map(s => s.exceso_total_min), 1);
  el.innerHTML = sorted.map((s, i) => {
    const segs = EXCESO_TIPOS.map(t => {
      const v = s[t.key] || 0;
      return v > 0
        ? `<span class="exceso-bar__seg exceso-bar__seg--${t.cls}" style="width:${v / max * 100}%"
             title="${t.name}: ${round1(v)} min"></span>`
        : '';
    }).join('');
    return `
    <div class="exceso-bar">
      <span class="polar-ranking__rank">#${i + 1}</span>
      <span class="exceso-bar__name" title="${esc(s.supervisor)}">${esc(s.supervisor)}</span>
      <div class="exceso-bar__track">${segs}</div>
      <span class="polar-ranking__value">${round1(s.exceso_total_min)} min</span>
    </div>`;
  }).join('');
}

// ════════════════════════════════════════════════════════════════════════
// SUPERVISOR TABLE
// ════════════════════════════════════════════════════════════════════════

function renderSupervisorTable(supervisors) {
  const tbody = document.getElementById('supervisor-tbody');
  if (!supervisors.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-row">Sin datos para mostrar</td></tr>';
    return;
  }
  tbody.innerHTML = supervisors.map(s => `
    <tr>
      <td><strong>${esc(s.supervisor)}</strong></td>
      <td class="text-center">${countBadge(s.agentes, '👥')}</td>
      <td class="text-center">${conExcesoBadge(s.con_exceso)}</td>
      <td class="text-center">${minBadge(s.exceso_alm_min, 5, 15)}</td>
      <td class="text-center">${minBadge(s.exceso_break_min, 5, 15)}</td>
      <td class="text-center">${minBadge(s.exceso_bano_min, 5, 15)}</td>
      <td class="text-center">${minBadge(s.exceso_total_min, 10, 30)}</td>
    </tr>`).join('');
}

function countBadge(n, icon) {
  return `<span class="badge-time badge-time--neutral"><strong>${icon} ${n}</strong></span>`;
}

function conExcesoBadge(n) {
  const level = n > 0 ? 'danger' : 'ok';
  const icon = n > 0 ? '⚠️' : '✅';
  return `<span class="badge-time badge-time--${level}"><strong>${icon} ${n}</strong></span>`;
}

// ── Formato condicional (badges de color + icono) ────────────────────────

function timeBadge(seconds, str, warnAt, dangerAt) {
  let level = 'ok', icon = '✅';
  if (seconds > dangerAt) { level = 'danger'; icon = '🔴'; }
  else if (seconds > warnAt) { level = 'warn'; icon = '🟡'; }
  return `<span class="badge-time badge-time--${level}">${icon} ${str}</span>`;
}

function neutralBadge(str) {
  return `<span class="badge-time badge-time--neutral">${str}</span>`;
}

function minBadge(minutes, warnAt, dangerAt) {
  let level = 'ok', icon = '✅';
  if (minutes > dangerAt) { level = 'danger'; icon = '🔴'; }
  else if (minutes > warnAt) { level = 'warn'; icon = '🟡'; }
  return `<span class="badge-time badge-time--${level}"><strong>${icon} ${minutes} min</strong></span>`;
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
  const tbody   = document.getElementById('agente-tbody');
  const { filtered, page, pageSize } = state.agente;

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="14" class="empty-row">Sin resultados para los filtros aplicados</td></tr>';
    renderPagination(0, page, pageSize);
    return;
  }

  const start = (page - 1) * pageSize;
  const slice = filtered.slice(start, start + pageSize);

  tbody.innerHTML = slice.map(r => {
    return `
      <tr>
        <td class="text-center">${neutralBadge(r.Fecha || '—')}</td>
        <td><strong>${esc(r.Asesor || '—')}</strong></td>
        <td>${esc(r.Supervisor || '—')}</td>
        <td><span style="font-size:0.78rem;color:#757575">${esc(r.Campana || '—')}</span></td>
        <td class="text-center">${neutralBadge(r.T_login)}</td>
        <td class="text-center">${neutralBadge(r.T_Pantalla_Verde)}</td>
        <td class="text-center">${timeBadge(r.T_dead_seg, r.T_dead, 120, 300)}</td>
        <td class="text-center">${neutralBadge(r.T_preturno)}</td>
        <td class="text-center">${neutralBadge(r.T_capacitacion)}</td>
        <td class="text-center">${neutralBadge(r.T_whatsapp)}</td>
        <td class="text-center">${timeBadge(r.T_Exceso_Alm_seg, r.T_Exceso_Alm, 0, 300)}</td>
        <td class="text-center">${timeBadge(r.T_Exceso_Break_seg, r.T_Exceso_Break, 0, 300)}</td>
        <td class="text-center">${timeBadge(r.T_Exceso_Bano_seg, r.T_Exceso_Bano, 0, 300)}</td>
        <td class="text-center">${timeBadge(r.T_Exceso_Total_seg, r.T_Exceso_Total, 0, 600)}</td>
      </tr>`;
  }).join('');

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
    Fecha: r.Fecha || '', Asesor: r.Asesor || '', Supervisor: r.Supervisor || '', Campaña: r.Campana || '',
    T_Login: r.T_login, T_Pantalla_Verde: r.T_Pantalla_Verde, T_Dead: r.T_dead,
    T_Preturno: r.T_preturno, T_Capacitacion: r.T_capacitacion, T_Whatsapp: r.T_whatsapp,
    Exceso_Almuerzo: r.T_Exceso_Alm, Exceso_Break: r.T_Exceso_Break, Exceso_Bano: r.T_Exceso_Bano,
    Exceso_Total: r.T_Exceso_Total,
  }));
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Excesos');
  XLSX.writeFile(wb, `excesos_claro_${dateStamp()}.xlsx`);
  showToast('Exportado a Excel correctamente', 'ok');
}

function exportCSV() {
  if (!state.agente.filtered.length) {
    showToast('No hay datos para exportar', 'error');
    return;
  }
  const headers = ['Fecha','Asesor','Supervisor','Campaña','T_Login','T_Pantalla_Verde','T_Dead','T_Preturno','T_Capacitacion','T_Whatsapp','Exceso_Almuerzo','Exceso_Break','Exceso_Bano','Exceso_Total'];
  const rows = state.agente.filtered.map(r => [
    csvCell(r.Fecha), csvCell(r.Asesor), csvCell(r.Supervisor), csvCell(r.Campana),
    csvCell(r.T_login), csvCell(r.T_Pantalla_Verde), csvCell(r.T_dead),
    csvCell(r.T_preturno), csvCell(r.T_capacitacion), csvCell(r.T_whatsapp),
    csvCell(r.T_Exceso_Alm), csvCell(r.T_Exceso_Break), csvCell(r.T_Exceso_Bano),
    csvCell(r.T_Exceso_Total),
  ].join(','));
  const content = [headers.join(','), ...rows].join('\n');
  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `excesos_claro_${dateStamp()}.csv`;
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

function truncate(str, len) {
  return str && str.length > len ? str.slice(0, len) + '…' : str;
}

function dateStamp() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
}
