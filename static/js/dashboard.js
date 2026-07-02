/* ═══════════════════════════════════════════════════════════════════════
   Claro Ventas — Dashboard de Asistencia
   ═══════════════════════════════════════════════════════════════════════ */

'use strict';

// ── Constantes de color ──────────────────────────────────────────────────
const COLORS = {
  red:    '#DA291C',
  green:  '#2E7D32',
  yellow: '#F57F17',
  blue:   '#1565C0',
  greenMid:  '#66BB6A',
  yellowMid: '#FFC107',
  blueMid:   '#42A5F5',
  redLight:  'rgba(218,41,28,0.15)',
  greenLight:'rgba(46,125,50,0.15)',
  yellowLight:'rgba(245,127,23,0.15)',
  blueLight: 'rgba(21,101,192,0.15)',
};

// ── Estado global ────────────────────────────────────────────────────────
const state = {
  rawData:   null,
  charts:    {},
  advisor: {
    data:        [],
    filtered:    [],
    page:        1,
    pageSize:    25,
    sortCol:     'Nombre',
    sortDir:     'asc',
    searchName:  '',
    searchSup:   '',
  },
  countdown:    60,
  refreshTimer: null,
  cdTimer:      null,
};

// ── Entrada ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadFilterOptions();
  refreshDashboard();
  startAutoRefresh();
});

// ════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════════════════════════════════════

function setupEventListeners() {
  // Filters → debounced refresh
  ['f-supervisor','f-campana','f-estado','f-hora-ini','f-hora-fin'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', debounce(refreshDashboard, 350));
  });

  document.getElementById('btn-clear-filters').addEventListener('click', clearFilters);
  document.getElementById('btn-refresh').addEventListener('click', () => refreshDashboard(true));

  // Advisor table search
  ['search-name','search-supervisor'].forEach(id => {
    document.getElementById(id).addEventListener('input', debounce(() => {
      state.advisor.searchName = document.getElementById('search-name').value.trim().toLowerCase();
      state.advisor.searchSup  = document.getElementById('search-supervisor').value.trim().toLowerCase();
      state.advisor.page = 1;
      applyAdvisorFilters();
      renderAdvisorTable();
    }, 250));
  });

  // Page size
  document.getElementById('page-size').addEventListener('change', e => {
    state.advisor.pageSize = parseInt(e.target.value, 10);
    state.advisor.page = 1;
    renderAdvisorTable();
  });

  // Pagination
  document.getElementById('btn-first').addEventListener('click', () => goToPage(1));
  document.getElementById('btn-prev').addEventListener('click',  () => goToPage(state.advisor.page - 1));
  document.getElementById('btn-next').addEventListener('click',  () => goToPage(state.advisor.page + 1));
  document.getElementById('btn-last').addEventListener('click',  () => {
    const pages = Math.ceil(state.advisor.filtered.length / state.advisor.pageSize);
    goToPage(pages);
  });

  // Sort headers
  document.querySelectorAll('#advisor-table .sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (state.advisor.sortCol === col) {
        state.advisor.sortDir = state.advisor.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.advisor.sortCol = col;
        state.advisor.sortDir = 'asc';
      }
      updateSortHeaders();
      applyAdvisorFilters();
      renderAdvisorTable();
    });
  });

  // Export
  document.getElementById('btn-export-excel').addEventListener('click', exportExcel);
  document.getElementById('btn-export-csv').addEventListener('click',   exportCSV);
}

// ════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ════════════════════════════════════════════════════════════════════════

async function refreshDashboard(manual = false) {
  if (manual) {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 800);
  }

  setLoading(true);
  resetCountdown();

  try {
    const params = buildQueryParams();
    const res = await fetch('/api/dashboard?' + params);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`);

    state.rawData = data;
    updateAll(data);
    setStatus(true);
  } catch (err) {
    console.error('[Dashboard] Error al cargar datos:', err);
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
    const res  = await fetch('/api/filters');
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
    console.warn('[Dashboard] No se pudieron cargar opciones de filtro:', e);
  }
}

function buildQueryParams() {
  const params = new URLSearchParams();
  const add = (id, key) => {
    const v = document.getElementById(id)?.value?.trim();
    if (v) params.set(key, v);
  };
  add('f-supervisor', 'supervisor');
  add('f-campana',    'campana');
  add('f-estado',     'estado');
  add('f-hora-ini',   'hora_inicio');
  add('f-hora-fin',   'hora_fin');
  return params.toString();
}

function clearFilters() {
  ['f-supervisor','f-campana','f-estado','f-hora-ini','f-hora-fin'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('search-name').value = '';
  document.getElementById('search-supervisor').value = '';
  state.advisor.searchName = '';
  state.advisor.searchSup  = '';
  refreshDashboard();
}

// ════════════════════════════════════════════════════════════════════════
// UPDATE ALL COMPONENTS
// ════════════════════════════════════════════════════════════════════════

function updateAll(data) {
  updateKPIs(data.kpis);
  updateCharts(data);
  renderSupervisorTable(data.supervisors);
  updateAusentismo(data.ausentismo);
  updateRetardos(data.retardos);

  state.advisor.data = data.attendance || [];
  applyAdvisorFilters();
  renderAdvisorTable();

  const el = document.getElementById('last-update');
  if (el) el.textContent = data.last_update || '—';
}

// ════════════════════════════════════════════════════════════════════════
// KPIs
// ════════════════════════════════════════════════════════════════════════

function updateKPIs(kpis) {
  if (!kpis) return;
  setKPI('kpi-programados',     kpis.total_programados);
  setKPI('kpi-asistieron',      kpis.total_asistieron);
  setKPI('kpi-ausentes',        kpis.total_ausentes);
  setKPI('kpi-retardos',        kpis.total_retardos);
  setKPI('kpi-pct-ausentismo',  kpis.pct_ausentismo  + '%');
  setKPI('kpi-pct-puntualidad', kpis.pct_puntualidad + '%');
  setKPI('kpi-pct-retardos',    kpis.pct_retardos    + '%');
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
// CHARTS
// ════════════════════════════════════════════════════════════════════════

function updateCharts(data) {
  updateBarChart(data.supervisors || []);
  updateDonutChart(data.kpis);
  updateHBarChart(data.supervisors || []);
  updateTimelineChart(data.timeline || { labels: [], values: [] });
}

// ── Barra: Supervisores ──────────────────────────────────────────────────
function updateBarChart(supervisors) {
  const ctx = document.getElementById('chart-bar-supervisors').getContext('2d');
  const labels    = supervisors.map(s => truncate(s.supervisor, 18));
  const prog      = supervisors.map(s => s.programados);
  const asist     = supervisors.map(s => s.asistieron);
  const ausentes  = supervisors.map(s => s.ausentes);

  const cfg = {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Programados', data: prog,     backgroundColor: COLORS.blueLight,   borderColor: COLORS.blue,   borderWidth: 2, borderRadius: 4 },
        { label: 'Asistieron',  data: asist,    backgroundColor: COLORS.greenLight,  borderColor: COLORS.green,  borderWidth: 2, borderRadius: 4 },
        { label: 'Ausentes',    data: ausentes, backgroundColor: COLORS.redLight,    borderColor: COLORS.red,    borderWidth: 2, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 12 } } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 }, maxRotation: 35 } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 11 } } },
      },
    },
  };

  if (state.charts.bar) {
    state.charts.bar.data = cfg.data;
    state.charts.bar.update('active');
  } else {
    state.charts.bar = new Chart(ctx, cfg);
  }
}

// ── Dona: Distribución global ────────────────────────────────────────────
function updateDonutChart(kpis) {
  if (!kpis) return;
  const ctx = document.getElementById('chart-donut').getContext('2d');
  const asistPuro = Math.max(0, (kpis.total_asistieron || 0) - (kpis.total_retardos || 0));
  const retardos  = kpis.total_retardos  || 0;
  const ausentes  = kpis.total_ausentes  || 0;
  const total     = kpis.total_programados || 1;

  const values = [asistPuro, retardos, ausentes];
  const labels = ['Puntuales', 'Retardos', 'Ausentes'];
  const colors = [COLORS.green, COLORS.yellow, COLORS.red];

  const cfg = {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: '#fff', hoverOffset: 8 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.raw} (${((ctx.raw/total)*100).toFixed(1)}%)`,
          },
        },
      },
    },
  };

  if (state.charts.donut) {
    state.charts.donut.data = cfg.data;
    state.charts.donut.update('active');
  } else {
    state.charts.donut = new Chart(ctx, cfg);
  }

  // Leyenda personalizada
  const leg = document.getElementById('donut-legend');
  if (leg) {
    leg.innerHTML = [
      { label: 'Puntuales', count: asistPuro, color: COLORS.green },
      { label: 'Retardos',  count: retardos,  color: COLORS.yellow },
      { label: 'Ausentes',  count: ausentes,  color: COLORS.red },
    ].map(item => `
      <div class="legend-item">
        <div class="legend-dot" style="background:${item.color}"></div>
        <span class="legend-label">${item.label}</span>
        <span class="legend-count">${item.count}</span>
        <span class="legend-pct">${pct(item.count, total)}%</span>
      </div>
    `).join('');
  }
}

// ── Barra horizontal: Ranking ausentismo ─────────────────────────────────
function updateHBarChart(supervisors) {
  const ctx = document.getElementById('chart-hbar').getContext('2d');
  const sorted = [...supervisors].sort((a, b) => b.pct_ausentismo - a.pct_ausentismo);
  const labels  = sorted.map(s => truncate(s.supervisor, 22));
  const values  = sorted.map(s => s.pct_ausentismo);
  const colors  = values.map(v => v > 10 ? COLORS.red : v >= 5 ? COLORS.yellow : COLORS.green);

  const cfg = {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '% Ausentismo',
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw}% ausentismo` } },
      },
      scales: {
        x: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: v => v + '%', font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,0.05)' },
        },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
    },
  };

  if (state.charts.hbar) {
    state.charts.hbar.data = cfg.data;
    state.charts.hbar.update('active');
  } else {
    state.charts.hbar = new Chart(ctx, cfg);
  }
}

// ── Línea: Timeline de llegadas ──────────────────────────────────────────
function updateTimelineChart(timeline) {
  const ctx = document.getElementById('chart-timeline').getContext('2d');

  const cfg = {
    type: 'line',
    data: {
      labels: timeline.labels,
      datasets: [{
        label: 'Ingresos',
        data: timeline.values,
        borderColor: COLORS.red,
        backgroundColor: 'rgba(218,41,28,0.10)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: COLORS.red,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw} asesores ingresaron` } },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 }, maxRotation: 40 },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0,0,0,0.05)' },
          ticks: { precision: 0, font: { size: 11 } },
        },
      },
    },
  };

  if (state.charts.timeline) {
    state.charts.timeline.data = cfg.data;
    state.charts.timeline.update('active');
  } else {
    state.charts.timeline = new Chart(ctx, cfg);
  }
}

// ════════════════════════════════════════════════════════════════════════
// SUPERVISOR TABLE
// ════════════════════════════════════════════════════════════════════════

function renderSupervisorTable(supervisors) {
  const tbody = document.getElementById('supervisor-tbody');
  if (!supervisors || supervisors.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-row">Sin datos para mostrar</td></tr>';
    return;
  }

  tbody.innerHTML = supervisors.map(s => {
    const ausClass = s.pct_ausentismo > 10 ? 'aus-danger'
                   : s.pct_ausentismo >= 5  ? 'aus-warn'
                   :                          'aus-ok';
    return `
      <tr class="${ausClass}">
        <td><strong>${esc(s.supervisor)}</strong></td>
        <td class="text-center">${s.programados}</td>
        <td class="text-center">${s.asistieron}</td>
        <td class="text-center">${s.ausentes}</td>
        <td class="text-center">${s.retardos}</td>
        <td class="text-center">${s.pct_ausentismo}%</td>
        <td class="text-center">${s.pct_retardo}%</td>
        <td class="text-center">${s.pct_asistencia}%</td>
      </tr>`;
  }).join('');
}

// ════════════════════════════════════════════════════════════════════════
// AUSENTISMO
// ════════════════════════════════════════════════════════════════════════

function updateAusentismo(ausentismo) {
  if (!ausentismo) return;

  setKPI('ausentismo-total', ausentismo.total);

  const countEl = document.getElementById('ausentismo-count');
  if (countEl) {
    const n = ausentismo.total;
    countEl.textContent = `${n} asesor${n !== 1 ? 'es' : ''} ausente${n !== 1 ? 's' : ''}`;
  }

  renderAusentismoTable(ausentismo.list || []);
  updateAusentismoBarChart(ausentismo.by_supervisor || []);
}

function renderAusentismoTable(list) {
  const tbody = document.getElementById('ausentismo-tbody');
  if (!tbody) return;
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="empty-row">Sin ausencias registradas</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(r => `
    <tr>
      <td>${esc(r.Nombre || '—')}</td>
      <td>${esc(r.Supervisor || '—')}</td>
      <td class="text-center mono">${r.Hora_Programada || '—'}</td>
    </tr>`).join('');
}

function updateAusentismoBarChart(bySupervisor) {
  const ctx = document.getElementById('chart-ausentismo-bar').getContext('2d');
  const labels = bySupervisor.map(s => truncate(s.supervisor, 20));
  const values = bySupervisor.map(s => s.ausentes);

  const cfg = {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Ausentes',
        data: values,
        backgroundColor: COLORS.redLight,
        borderColor: COLORS.red,
        borderWidth: 2,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw} ausente${ctx.raw !== 1 ? 's' : ''}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 }, maxRotation: 35 } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { precision: 0, font: { size: 11 } } },
      },
    },
  };

  if (state.charts.ausentismoBar) {
    state.charts.ausentismoBar.data = cfg.data;
    state.charts.ausentismoBar.update('active');
  } else {
    state.charts.ausentismoBar = new Chart(ctx, cfg);
  }
}

// ════════════════════════════════════════════════════════════════════════
// RETARDOS
// ════════════════════════════════════════════════════════════════════════

function updateRetardos(retardos) {
  if (!retardos) return;

  setKPI('retardos-total', retardos.total);

  const countEl = document.getElementById('retardos-count');
  if (countEl) {
    const n = retardos.total;
    countEl.textContent = `${n} asesor${n !== 1 ? 'es' : ''} con retardo`;
  }

  renderRetardosTable(retardos.list || []);
  updateRetardoBarChart(retardos.list || []);
  renderAvgRetardoChips(retardos.avg_by_supervisor || []);
}

function renderRetardosTable(list) {
  const tbody = document.getElementById('retardos-tbody');
  if (!tbody) return;
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">Sin retardos registrados</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(r => `
    <tr>
      <td>${esc(r.Nombre || '—')}</td>
      <td>${esc(r.Supervisor || '—')}</td>
      <td class="text-center mono">${r.Hora_Programada || '—'}</td>
      <td class="text-center mono">${r.Hora_Inicio || '—'}</td>
      <td class="text-center mono">${r.Tiempo_Retardo || '—'}</td>
    </tr>`).join('');
}

function updateRetardoBarChart(list) {
  const ctx = document.getElementById('chart-retardo-bar').getContext('2d');
  const top = list.slice(0, 15); // top 15 mayores retardos para legibilidad
  const labels = top.map(r => truncate(r.Nombre, 20));
  const values = top.map(r => r.Tiempo_Retardo_Min);

  const cfg = {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Minutos de retardo',
        data: values,
        backgroundColor: COLORS.yellowMid,
        borderColor: COLORS.yellow,
        borderWidth: 2,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw} min de retardo` } },
      },
      scales: {
        x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
    },
  };

  if (state.charts.retardoBar) {
    state.charts.retardoBar.data = cfg.data;
    state.charts.retardoBar.update('active');
  } else {
    state.charts.retardoBar = new Chart(ctx, cfg);
  }
}

function renderAvgRetardoChips(avgBySupervisor) {
  const el = document.getElementById('avg-retardo-list');
  if (!el) return;
  if (!avgBySupervisor.length) {
    el.innerHTML = '';
    return;
  }
  el.innerHTML = avgBySupervisor.map(s => `
    <div class="avg-retardo-chip">
      <span class="avg-retardo-chip__name">${esc(s.supervisor)}</span>
      <span class="avg-retardo-chip__value">${s.avg_min} min prom.</span>
    </div>`).join('');
}

// ════════════════════════════════════════════════════════════════════════
// ADVISOR TABLE
// ════════════════════════════════════════════════════════════════════════

function applyAdvisorFilters() {
  let data = [...state.advisor.data];

  if (state.advisor.searchName) {
    data = data.filter(r => (r.Nombre || '').toLowerCase().includes(state.advisor.searchName));
  }
  if (state.advisor.searchSup) {
    data = data.filter(r => (r.Supervisor || '').toLowerCase().includes(state.advisor.searchSup));
  }

  // Sort
  const col = state.advisor.sortCol;
  const dir = state.advisor.sortDir === 'asc' ? 1 : -1;
  data.sort((a, b) => {
    const va = a[col] ?? '';
    const vb = b[col] ?? '';
    return va < vb ? -dir : va > vb ? dir : 0;
  });

  state.advisor.filtered = data;
  document.getElementById('advisor-count').textContent =
    `${data.length} asesor${data.length !== 1 ? 'es' : ''} encontrado${data.length !== 1 ? 's' : ''}`;
}

function renderAdvisorTable() {
  const tbody    = document.getElementById('advisor-tbody');
  const { filtered, page, pageSize } = state.advisor;

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-row">Sin resultados para los filtros aplicados</td></tr>';
    renderPagination(0, page, pageSize);
    return;
  }

  const start  = (page - 1) * pageSize;
  const slice  = filtered.slice(start, start + pageSize);

  tbody.innerHTML = slice.map(r => {
    const badge = getStatusBadge(r);
    return `
      <tr>
        <td>${esc(r.Nombre  || '—')}</td>
        <td>${esc(r.Supervisor || '—')}</td>
        <td><span style="font-size:0.78rem;color:#757575">${esc(r.Campana || '—')}</span></td>
        <td class="text-center mono">${r.Hora_Programada || '—'}</td>
        <td class="text-center mono">${r.Hora_Inicio && r.Hora_Inicio !== '00:00:00' ? r.Hora_Inicio : '—'}</td>
        <td class="text-center mono">${r.Tiempo_Retardo && r.Tiempo_Retardo !== '00:00:00' ? r.Tiempo_Retardo : '—'}</td>
        <td class="text-center">${badge}</td>
      </tr>`;
  }).join('');

  renderPagination(filtered.length, page, pageSize);
}

function getStatusBadge(r) {
  if (r.Ausente === 1) {
    return '<span class="badge badge--red">❌ Ausente</span>';
  }
  if (r.Retardo === 1) {
    return '<span class="badge badge--yellow">🟡 Retardo</span>';
  }
  if (r.Asiste === 1) {
    return '<span class="badge badge--green">✅ Asistió</span>';
  }
  return '<span class="badge">— Pendiente</span>';
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
  const pages = Math.max(1, Math.ceil(state.advisor.filtered.length / state.advisor.pageSize));
  state.advisor.page = Math.min(Math.max(1, n), pages);
  renderAdvisorTable();
}

function updateSortHeaders() {
  document.querySelectorAll('#advisor-table .sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === state.advisor.sortCol) {
      th.classList.add('sort-' + state.advisor.sortDir);
    }
  });
}

// ════════════════════════════════════════════════════════════════════════
// EXPORT
// ════════════════════════════════════════════════════════════════════════

function exportExcel() {
  if (!state.advisor.filtered.length) {
    showToast('No hay datos para exportar', 'error');
    return;
  }
  const rows = state.advisor.filtered.map(r => ({
    Nombre:           r.Nombre || '',
    Supervisor:       r.Supervisor || '',
    Campaña:          r.Campana || '',
    Hora_Programada:  r.Hora_Programada || '',
    Hora_Inicio:      r.Hora_Inicio || '',
    Tiempo_Retardo:   r.Tiempo_Retardo || '',
    Estado:           getEstadoTexto(r),
  }));

  const ws  = XLSX.utils.json_to_sheet(rows);
  const wb  = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Asistencia');
  XLSX.writeFile(wb, `asistencia_claro_${dateStamp()}.xlsx`);
  showToast('Exportado a Excel correctamente', 'ok');
}

function exportCSV() {
  if (!state.advisor.filtered.length) {
    showToast('No hay datos para exportar', 'error');
    return;
  }
  const headers = ['Nombre','Supervisor','Campaña','Hora Programada','Hora Inicio','Tiempo Retardo','Estado'];
  const rows = state.advisor.filtered.map(r => [
    csvCell(r.Nombre),
    csvCell(r.Supervisor),
    csvCell(r.Campana),
    csvCell(r.Hora_Programada),
    csvCell(r.Hora_Inicio),
    csvCell(r.Tiempo_Retardo),
    csvCell(getEstadoTexto(r)),
  ].join(','));

  const content = [headers.join(','), ...rows].join('\n');
  const blob    = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' });
  const url     = URL.createObjectURL(blob);
  const a       = document.createElement('a');
  a.href = url; a.download = `asistencia_claro_${dateStamp()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Exportado a CSV correctamente', 'ok');
}

function getEstadoTexto(r) {
  if (r.Ausente === 1) return 'Ausente';
  if (r.Retardo === 1) return 'Retardo';
  if (r.Asiste  === 1) return 'Asistió';
  return 'Pendiente';
}

// ════════════════════════════════════════════════════════════════════════
// AUTO-REFRESH & COUNTDOWN
// ════════════════════════════════════════════════════════════════════════

const REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 minutos
const REFRESH_INTERVAL_S  = REFRESH_INTERVAL_MS / 1000;

function startAutoRefresh() {
  clearInterval(state.refreshTimer);
  clearInterval(state.cdTimer);

  state.refreshTimer = setInterval(() => {
    refreshDashboard();
  }, REFRESH_INTERVAL_MS);

  resetCountdown();
}

function resetCountdown() {
  state.countdown = REFRESH_INTERVAL_S;
  renderCountdown();
  clearInterval(state.cdTimer);
  state.cdTimer = setInterval(() => {
    state.countdown -= 1;
    if (state.countdown < 0) state.countdown = 0;
    renderCountdown();
  }, 1_000);
}

function renderCountdown() {
  const el = document.getElementById('countdown');
  if (!el) return;
  const m = Math.floor(state.countdown / 60);
  const s = state.countdown % 60;
  el.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
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

// ════════════════════════════════════════════════════════════════════════
// UTILITIES
// ════════════════════════════════════════════════════════════════════════

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

function pct(n, d) {
  return d === 0 ? '0.0' : ((n / d) * 100).toFixed(1);
}

function truncate(str, len) {
  return str && str.length > len ? str.slice(0, len) + '…' : str;
}

function dateStamp() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
}
