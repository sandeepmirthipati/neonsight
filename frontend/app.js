const API_URL = 'https://neonsight.onrender.com';
const chartInstances = {};
const colors = ['#00f2fe', '#7928ca', '#ff0080', '#00e676', '#ff9f03', '#4facfe', '#ff5e62', '#c6ff00'];
const $ = selector => document.querySelector(selector);

document.addEventListener('DOMContentLoaded', () => { lucide.createIcons(); checkEngine(); });
const zone = $('#drop-zone');
['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, event => { event.preventDefault(); zone.classList.add('dragging'); }));
['dragleave', 'drop'].forEach(name => zone.addEventListener(name, event => { event.preventDefault(); zone.classList.remove('dragging'); }));
zone.addEventListener('drop', event => analyze(event.dataTransfer.files[0]));
$('#file-input').addEventListener('change', event => analyze(event.target.files[0]));
$('#new-file').addEventListener('click', reset);
$('#preview-toggle').addEventListener('click', () => { const table = $('#table-container'), isHidden = table.classList.toggle('hidden'); $('#preview-toggle').setAttribute('aria-expanded', String(!isHidden)); });

async function checkEngine() {
  try { const response = await fetch(`${API}/`, { signal: AbortSignal.timeout(3500) }); if (!response.ok) throw Error(); $('#connection').classList.add('online'); $('#connection span').textContent = 'Engine online'; }
  catch { $('#connection span').textContent = 'Engine offline'; }
}

async function analyze(file) {
  if (!file) return;
  if (!/\.(csv|xlsx)$/i.test(file.name)) return showError('Choose a CSV or XLSX dataset.');
  if (file.size > 30 * 1024 * 1024) return showError('The maximum upload size is 30 MB.');
  $('#error').classList.add('hidden'); $('#loader').classList.remove('hidden');
  const body = new FormData(); body.append('file', file);
  try {
    const response = await fetch(`${API}/api/analyze`, { method: 'POST', body });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Analysis failed.');
    if (!data.summary || !data.charts || !Array.isArray(data.preview)) throw new Error('The analysis engine returned an invalid response. Restart the backend and retry.');
    render(data);
  } catch (error) { showError(error.message || 'Unable to reach the analysis engine.'); checkEngine(); }
  finally { $('#loader').classList.add('hidden'); $('#file-input').value = ''; }
}

function render(data) {
  const { summary, charts } = data;
  $('#file-name').textContent = data.file_name;
  $('#rows').textContent = number(summary.total_rows); $('#columns').textContent = number(summary.total_columns);
  $('#missing').textContent = `${summary.missing_percentage}%`; $('#missing-detail').textContent = `${number(summary.missing_cells)} cells`;
  $('#memory').textContent = bytes(summary.memory_bytes); $('#duplicates').textContent = number(summary.duplicate_rows); $('#primary-type').textContent = summary.primary_column_type;
  $('#category-subtitle').textContent = charts.categories.title; $('#trend-subtitle').textContent = charts.trend.title;
  healthChart(charts.health); categoryChart(charts.categories); trendChart(charts.trend); radarChart(charts.radar); rangeChart(charts.ranges); scatterChart(charts.scatter); renderTable(data.preview, data.columns);
  $('#upload-section').classList.add('hidden'); $('#dashboard').classList.remove('hidden'); $('#dashboard').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function commonOptions() { return { responsive: true, maintainAspectRatio: false, animation: { duration: 1500, easing: 'easeOutQuart' }, plugins: { legend: { display: false }, tooltip: { backgroundColor: '#111a2c', titleColor: '#eff7ff', bodyColor: '#b5c4df', padding: 10, cornerRadius: 8, displayColors: false } } }; }
function replace(key, id, config) { chartInstances[key]?.destroy(); chartInstances[key] = new Chart($(id), config); }
function gridScales() { return { x: { grid: { display: false }, ticks: { color: '#8d9ab4', font: { size: 10 } }, border: { display: false } }, y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,.06)' }, ticks: { color: '#8d9ab4', font: { size: 10 } }, border: { display: false } } }; }
function healthChart(data) {
  $('#health-legend').innerHTML = data.labels.map((label, index) => `<span><i style="background:${['#00e676','#ff0080'][index]}"></i>${label}: ${number(data.values[index])}</span>`).join('');
  replace('health', '#health-chart', { type: 'doughnut', data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: ['#00e676', '#ff0080'], borderWidth: 0, hoverOffset: 10 }] }, options: { ...commonOptions(), cutout: '72%' } });
}
function categoryChart(data) {
  $('#category-empty').classList.toggle('hidden', Boolean(data.values.length));
  replace('category', '#category-chart', { type: 'bar', data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: data.values.map((_, index) => colors[index % colors.length]), borderRadius: 7, borderSkipped: false }] }, options: { ...commonOptions(), indexAxis: 'y', scales: gridScales() } });
}
function trendChart(data) {
  $('#trend-empty').classList.toggle('hidden', Boolean(data.values.length));
  const context = $('#trend-chart').getContext('2d'), fill = context.createLinearGradient(0, 0, 0, 245); fill.addColorStop(0, 'rgba(0,242,254,.42)'); fill.addColorStop(1, 'rgba(0,242,254,0)');
  replace('trend', '#trend-chart', { type: 'line', data: { labels: data.labels, datasets: [{ data: data.values, borderColor: '#00f2fe', backgroundColor: fill, fill: true, tension: .4, borderWidth: 2.3, pointRadius: 0, pointHoverRadius: 5 }] }, options: { ...commonOptions(), interaction: { mode: 'index', intersect: false }, scales: { ...gridScales(), x: { ...gridScales().x, ticks: { color: '#8d9ab4', maxTicksLimit: 9, font: { size: 10 } } } } } });
}
function radarChart(data) { replace('radar', '#radar-chart', { type: 'radar', data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: 'rgba(121,40,202,.23)', borderColor: '#a56bff', pointBackgroundColor: '#ff0080', pointRadius: 3, borderWidth: 2 }] }, options: { ...commonOptions(), scales: { r: { min: 0, max: 100, ticks: { display: false }, grid: { color: 'rgba(255,255,255,.09)' }, angleLines: { color: 'rgba(255,255,255,.1)' }, pointLabels: { color: '#9ca9c2', font: { size: 10 } } } } } }); }
function rangeChart(data) {
  $('#range-empty').classList.toggle('hidden', Boolean(data.labels.length));
  replace('range', '#range-chart', { type: 'bar', data: { labels: data.labels, datasets: [{ label: 'Min', data: data.minimum, backgroundColor: '#7928ca', borderRadius: 4 }, { label: 'Average', data: data.average, backgroundColor: '#00f2fe', borderRadius: 4 }, { label: 'Max', data: data.maximum, backgroundColor: '#ff9f03', borderRadius: 4 }] }, options: { ...commonOptions(), plugins: { ...commonOptions().plugins, legend: { display: true, labels: { color: '#9ca9c2', boxWidth: 9, font: { size: 10 } } } }, scales: gridScales() } });
}
function scatterChart(data) {
  $('#scatter-empty').classList.toggle('hidden', Boolean(data.points.length));
  $('#scatter-subtitle').textContent = data.x_name && data.y_name ? `${data.x_name} × ${data.y_name}${data.correlation !== null ? ` · r ${data.correlation}` : ''}` : 'No measurable relationship';
  replace('scatter', '#scatter-chart', { type: 'scatter', data: { datasets: [{ data: data.points, backgroundColor: 'rgba(255,0,128,.65)', borderColor: '#ff0080', pointRadius: 4, pointHoverRadius: 6 }] }, options: { ...commonOptions(), scales: { x: { title: { display: Boolean(data.x_name), text: data.x_name, color: '#8d9ab4' }, grid: { color: 'rgba(255,255,255,.06)' }, ticks: { color: '#8d9ab4' }, border: { display: false } }, y: { title: { display: Boolean(data.y_name), text: data.y_name, color: '#8d9ab4' }, grid: { color: 'rgba(255,255,255,.06)' }, ticks: { color: '#8d9ab4' }, border: { display: false } } } } });
}
function renderTable(rows, columns) {
  const target = $('#table-container'); if (!rows.length) { target.innerHTML = '<p class="empty">No preview rows available.</p>'; return; }
  const keys = Object.keys(rows[0]), metadata = Object.fromEntries(columns.map(column => [column.name, column]));
  target.innerHTML = `<table><thead><tr>${keys.map(key => `<th>${escape(key)} <span class="type">${escape(metadata[key]?.kind || '')}</span></th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${keys.map(key => `<td>${escape(row[key] ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function reset() { Object.values(chartInstances).forEach(chart => chart?.destroy()); Object.keys(chartInstances).forEach(key => delete chartInstances[key]); $('#dashboard').classList.add('hidden'); $('#upload-section').classList.remove('hidden'); $('#table-container').classList.add('hidden'); $('#preview-toggle').setAttribute('aria-expanded', 'false'); window.scrollTo({ top: 0, behavior: 'smooth' }); }
function number(value) { return Number(value).toLocaleString(); } function bytes(value) { if (value < 1024) return `${value} B`; if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`; return `${(value / 1048576).toFixed(1)} MB`; }
function escape(value) { return String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character])); } function showError(message) { $('#error').textContent = message; $('#error').classList.remove('hidden'); }
