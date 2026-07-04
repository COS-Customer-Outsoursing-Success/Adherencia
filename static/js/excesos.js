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
  setupEventListeners();
  loadFilterOptions();
  refreshReport();
  startAutoRefresh();
});

// ════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
  ['f-supervisor', 'f-campana', 'f-solo-exceso'].forEach(id => {
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
  const soloExceso = document.getElementById('f-solo-exceso')?.checked;
  if (supervisor) params.set('supervisor', supervisor);
  if (campana)    params.set('campana', campana);
  if (soloExceso) params.set('solo_con_exceso', '1');
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
    console.warn('[Excesos] No se pudieron cargar opciones de filtro:', e);
  }
}

function clearFilters() {
  document.getElementById('f-supervisor').value = '';
  document.getElementById('f-campana').value = '';
  document.getElementById('f-solo-exceso').checked = false;
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
  renderPolarChart(data.supervisors || []);
  renderPolarRanking(data.supervisors || []);
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
// POLAR CHART — gráfica de áreas polares apiladas (custom canvas)
// ════════════════════════════════════════════════════════════════════════

const POLAR_COLORS = {
  alm:   { base: '#1565C0', light: '#7FB2E8' },
  break: { base: '#F57C00', light: '#FFC078' },
  bano:  { base: '#DA291C', light: '#F0928A' },
};

const polarChart = {
  canvas: null,
  ctx: null,
  slices: [],      // geometría calculada para hit-testing en hover
  raf: null,
};

function renderPolarChart(supervisors) {
  const canvas = document.getElementById('chart-polar-exceso');
  if (!canvas) return;

  // Alta densidad de píxeles para nitidez en pantallas retina
  const dpr = window.devicePixelRatio || 1;
  if (!canvas._scaled) {
    canvas._logicalSize = parseFloat(canvas.getAttribute('width'));
    canvas.width = canvas._logicalSize * dpr;
    canvas.height = canvas._logicalSize * dpr;
    canvas._scaled = true;
    canvas.addEventListener('mousemove', onPolarHover);
    canvas.addEventListener('mouseleave', hidePolarTooltip);
  }

  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  polarChart.canvas = canvas;
  polarChart.ctx = ctx;
  const size = canvas._logicalSize;

  const sorted = [...supervisors]
    .filter(s => s.exceso_total_min > 0)
    .sort((a, b) => b.exceso_total_min - a.exceso_total_min);

  const totalGeneral = supervisors.reduce((sum, s) => sum + s.exceso_total_min, 0);
  setKPI('polar-total-value', Math.round(totalGeneral));

  if (!sorted.length) {
    ctx.clearRect(0, 0, size, size);
    polarChart.slices = [];
    return;
  }

  const maxTotal = Math.max(...sorted.map(s => s.exceso_total_min), 1);

  cancelAnimationFrame(polarChart.raf);
  const duration = 700;
  const start = performance.now();

  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
    drawPolar(sorted, maxTotal, size, eased);
    if (t < 1) {
      polarChart.raf = requestAnimationFrame(frame);
    }
  }
  polarChart.raf = requestAnimationFrame(frame);
}

function drawPolar(sorted, maxTotal, size, progress) {
  const ctx = polarChart.ctx;
  const cx = size / 2;
  const cy = size / 2;
  const innerR = size * 0.16;
  const outerR = size * 0.46;
  const gap = 0.035; // radianes de separación entre cuñas

  ctx.clearRect(0, 0, size, size);
  polarChart.slices = [];

  const n = sorted.length;
  const anglePer = (2 * Math.PI) / n;
  let angle = -Math.PI / 2;

  sorted.forEach(s => {
    const a0 = angle + gap / 2;
    const a1 = angle + anglePer - gap / 2;
    const range = (outerR - innerR) * progress;

    const rAlm   = innerR + (s.exceso_alm_min   / maxTotal) * range;
    const rBreak = rAlm   + (s.exceso_break_min / maxTotal) * range;
    const rBano  = rBreak + (s.exceso_bano_min  / maxTotal) * range;

    drawRing(ctx, cx, cy, innerR, rAlm,   a0, a1, POLAR_COLORS.alm);
    drawRing(ctx, cx, cy, rAlm,   rBreak, a0, a1, POLAR_COLORS.break);
    drawRing(ctx, cx, cy, rBreak, rBano,  a0, a1, POLAR_COLORS.bano);

    polarChart.slices.push({
      a0, a1, rInner: innerR, rOuter: Math.max(rBano, innerR + 1),
      supervisor: s.supervisor,
      layers: [
        { name: 'Almuerzo', min: s.exceso_alm_min,   rFrom: innerR, rTo: rAlm },
        { name: 'Break',    min: s.exceso_break_min, rFrom: rAlm,   rTo: rBreak },
        { name: 'Baño',     min: s.exceso_bano_min,  rFrom: rBreak, rTo: rBano },
      ],
      total: s.exceso_total_min,
    });

    angle += anglePer;
  });

  // Máscara circular blanca en el centro (hueco del donut)
  ctx.beginPath();
  ctx.arc(cx, cy, innerR - 1, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();
}

function drawRing(ctx, cx, cy, rFrom, rTo, a0, a1, color) {
  if (rTo <= rFrom) return;
  const gradient = ctx.createRadialGradient(cx, cy, rFrom, cx, cy, rTo);
  gradient.addColorStop(0, color.light);
  gradient.addColorStop(1, color.base);

  ctx.beginPath();
  ctx.arc(cx, cy, rTo, a0, a1);
  ctx.arc(cx, cy, rFrom, a1, a0, true);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = '#ffffff';
  ctx.stroke();
}

function onPolarHover(e) {
  const canvas = polarChart.canvas;
  const rect = canvas.getBoundingClientRect();
  const size = canvas._logicalSize;
  const scale = size / rect.width;
  const x = (e.clientX - rect.left) * scale;
  const y = (e.clientY - rect.top) * scale;
  const cx = size / 2, cy = size / 2;
  const dx = x - cx, dy = y - cy;
  const r = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx);

  const hit = polarChart.slices.find(s => {
    if (r < s.rInner || r > s.rOuter) return false;
    return angleInRange(angle, s.a0, s.a1);
  });

  if (!hit) { hidePolarTooltip(); return; }

  const layer = hit.layers.find(l => r >= l.rFrom && r <= l.rTo) || hit.layers[hit.layers.length - 1];
  showPolarTooltip(e, hit, layer);
}

function angleInRange(a, a0, a1) {
  // a0/a1 están en el sistema "-90° + sentido horario"; convertimos a atan2 estándar
  const norm = ang => {
    let v = ang - (-Math.PI / 2);
    while (v < 0) v += Math.PI * 2;
    while (v >= Math.PI * 2) v -= Math.PI * 2;
    return v;
  };
  const target = norm(a);
  const from = norm(a0);
  const to = norm(a1);
  return from <= to ? (target >= from && target <= to) : (target >= from || target <= to);
}

function showPolarTooltip(e, slice, layer) {
  const tip = document.getElementById('polar-tooltip');
  const wrapper = document.querySelector('.polar-card__chart');
  if (!tip || !wrapper) return;
  const rect = wrapper.getBoundingClientRect();
  tip.innerHTML = `<strong>${esc(slice.supervisor)}</strong><br>${layer.name}: <strong>${round1(layer.min)} min</strong><br>Total: ${round1(slice.total)} min`;
  tip.style.left = (e.clientX - rect.left) + 'px';
  tip.style.top  = (e.clientY - rect.top - 10) + 'px';
  tip.classList.add('show');
}

function hidePolarTooltip() {
  const tip = document.getElementById('polar-tooltip');
  if (tip) tip.classList.remove('show');
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

// ── Ranking lateral ───────────────────────────────────────────────────────

function renderPolarRanking(supervisors) {
  const el = document.getElementById('polar-ranking');
  if (!el) return;
  const sorted = [...supervisors].sort((a, b) => b.exceso_total_min - a.exceso_total_min);

  if (!sorted.length) {
    el.innerHTML = '<p class="empty-row">Sin datos para mostrar</p>';
    return;
  }

  el.innerHTML = sorted.map((s, i) => `
    <div class="polar-ranking__row">
      <span class="polar-ranking__rank">#${i + 1}</span>
      <span class="polar-ranking__name">${esc(s.supervisor)}</span>
      <span class="polar-ranking__value">${round1(s.exceso_total_min)} min</span>
    </div>`).join('');
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
    tbody.innerHTML = '<tr><td colspan="13" class="empty-row">Sin resultados para los filtros aplicados</td></tr>';
    renderPagination(0, page, pageSize);
    return;
  }

  const start = (page - 1) * pageSize;
  const slice = filtered.slice(start, start + pageSize);

  tbody.innerHTML = slice.map(r => {
    return `
      <tr>
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
    Asesor: r.Asesor || '', Supervisor: r.Supervisor || '', Campaña: r.Campana || '',
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
  const headers = ['Asesor','Supervisor','Campaña','T_Login','T_Pantalla_Verde','T_Dead','T_Preturno','T_Capacitacion','T_Whatsapp','Exceso_Almuerzo','Exceso_Break','Exceso_Bano','Exceso_Total'];
  const rows = state.agente.filtered.map(r => [
    csvCell(r.Asesor), csvCell(r.Supervisor), csvCell(r.Campana),
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
