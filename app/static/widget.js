const number = new Intl.NumberFormat('ru-RU');
const weight = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 });
function render(data) {
  const summary = data.summary || {};
  document.getElementById('orders').textContent = number.format(summary.orders || 0);
  document.getElementById('weight').textContent = weight.format(summary.weight || 0);
  document.getElementById('boxes').textContent = number.format(summary.boxes || 0);
  document.getElementById('searches').textContent = number.format(summary.searches || 0);
  const health = data.health || {};
  document.getElementById('dot').className = `dot ${health.onza === 'online' && health.firebase === 'online' ? 'online' : ''}`;
  document.getElementById('updated').textContent = health.last_success ? new Date(health.last_success).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '—';
}
fetch('/api/dashboard').then((response) => response.json()).then(render).catch(() => {});
const events = new EventSource('/events');
events.onmessage = (event) => render(JSON.parse(event.data));
document.body.addEventListener('dblclick', () => window.open('/', '_blank'));
