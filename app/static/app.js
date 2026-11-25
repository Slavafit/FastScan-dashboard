const formatNumber = new Intl.NumberFormat('ru-RU');
const formatWeight = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
let dashboard = { summary: {}, history: [], parties: [], health: {} };
let selectedDays = 7;
let selectedMetric = 'orders';

const $ = (id) => document.getElementById(id);
const safe = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

function render(data) {
  dashboard = data;
  const summary = data.summary || {};
  $('orders').textContent = formatNumber.format(summary.orders || 0);
  $('weight').textContent = formatWeight.format(summary.weight || 0);
  $('boxes').textContent = formatNumber.format(summary.boxes || 0);
  $('searches').textContent = formatNumber.format(summary.searches || 0);
  $('search-detail').textContent = `найдено ${summary.searches_found || 0} · не найдено ${summary.searches_not_found || 0}`;
  $('open-parties').textContent = formatNumber.format(summary.open_parties || 0);
  renderHealth(data.health || {});
  renderParties(data.parties || []);
  renderChart();
}

function renderHealth(health) {
  const connection = $('connection');
  const online = ['online', 'demo'].includes(health.onza) && ['online', 'demo'].includes(health.firebase);
  const partial = ['online', 'demo'].includes(health.onza) || ['online', 'demo'].includes(health.firebase);
  connection.className = `connection ${online ? 'online' : partial ? '' : 'error'}`;
  connection.querySelector('strong').textContent = online ? 'Все системы доступны' : partial ? 'Частичные данные' : 'Нет подключения';
  const sourceStatus = `Onza: ${health.onza || '—'} · Firebase: ${health.firebase || '—'}`;
  const detail = health.message && health.message !== 'All data sources are available' ? health.message : sourceStatus;
  connection.querySelector('small').textContent = detail;
  connection.title = `${sourceStatus}${health.message ? ` · ${health.message}` : ''}`;
  const date = health.last_success ? new Date(health.last_success) : null;
  $('last-update').textContent = `Последнее обновление: ${date ? date.toLocaleTimeString('ru-RU') : '—'}`;
}

function renderParties(parties) {
  const latestParties = [...parties]
    .sort((left, right) => {
      const leftDate = Date.parse(left.created_at || '') || 0;
      const rightDate = Date.parse(right.created_at || '') || 0;
      return rightDate - leftDate;
    })
    .slice(0, 15);
  const rows = latestParties.map((party) => {
    const open = Number(party.status) === 0;
    const created = party.created_at ? new Date(party.created_at).toLocaleDateString('ru-RU') : '—';
    return `<tr>
      <td>${safe(party.name || party.code || '—')}</td>
      <td><span class="badge ${open ? '' : 'closed'}">${open ? 'В работе' : 'Закрыта'}</span></td>
      <td>${formatNumber.format(party.box_count || 0)}</td>
      <td>${formatNumber.format(party.order_count || 0)}</td>
      <td>${formatWeight.format(party.gross_weight || 0)} кг</td>
      <td>${created}</td>
    </tr>`;
  });
  $('parties').innerHTML = rows.length ? rows.join('') : '<tr><td colspan="6" class="empty">Партии пока не получены</td></tr>';
}

function renderChart() {
  const rows = (dashboard.history || []).slice(-selectedDays);
  const svg = $('chart');
  if (!rows.length) { svg.innerHTML = ''; return; }
  const width = Math.max(700, svg.clientWidth || 700);
  const height = Math.max(250, svg.clientHeight || 250);
  const pad = { left: 50, right: 18, top: 18, bottom: 42 };
  const values = rows.map((row) => Number(row[selectedMetric] || 0));
  const max = Math.max(...values, 1);
  const x = (index) => pad.left + (index / Math.max(1, rows.length - 1)) * (width - pad.left - pad.right);
  const y = (value) => pad.top + (1 - value / max) * (height - pad.top - pad.bottom);
  const line = values.map((value, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
  const area = `${line} L${x(rows.length - 1)},${height - pad.bottom} L${x(0)},${height - pad.bottom} Z`;
  const grid = [0, .25, .5, .75, 1].map((ratio) => {
    const gy = y(max * ratio);
    return `<line class="chart-grid" x1="${pad.left}" y1="${gy}" x2="${width - pad.right}" y2="${gy}"/><text class="chart-label" x="4" y="${gy + 4}">${Math.round(max * ratio)}</text>`;
  }).join('');
  const step = Math.max(1, Math.ceil(rows.length / 7));
  const labels = rows.map((row, index) => index % step === 0 || index === rows.length - 1
    ? `<text class="chart-label" text-anchor="middle" x="${x(index)}" y="${height - 12}">${new Date(`${row.day}T12:00:00`).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}</text>` : '').join('');
  const points = values.map((value, index) => `<circle class="chart-point" cx="${x(index)}" cy="${y(value)}" r="3.5"><title>${rows[index].day}: ${value.toFixed(selectedMetric === 'weight' ? 1 : 0)}</title></circle>`).join('');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.innerHTML = `<defs><linearGradient id="areaGradient" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#2e8a55" stop-opacity=".28"/><stop offset="1" stop-color="#2e8a55" stop-opacity="0"/></linearGradient></defs>${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${line}"/>${points}${labels}`;
}

document.querySelectorAll('[data-days]').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('[data-days]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  selectedDays = Number(button.dataset.days);
  renderChart();
}));
$('metric-select').addEventListener('change', (event) => { selectedMetric = event.target.value; renderChart(); });
$('refresh').addEventListener('click', async () => {
  $('refresh').disabled = true;
  try { await fetch('/api/refresh', { method: 'POST' }); } finally { $('refresh').disabled = false; }
});
window.addEventListener('resize', renderChart);

fetch('/api/dashboard').then((response) => response.json()).then(render).catch(() => {});
const events = new EventSource('/events');
events.onmessage = (event) => render(JSON.parse(event.data));
events.onerror = () => $('connection').className = 'connection error';
