/* Meeting Insights — single-page app */
const API = '';
let TOKEN = localStorage.getItem('mi_token') || '';
let ME = null;
const charts = {};

/* ---------------- helpers ---------------- */
function inr(x) {
  x = Number(x || 0);
  if (Math.abs(x) >= 1e7) return '₹' + (x / 1e7).toFixed(2) + ' Cr';
  if (Math.abs(x) >= 1e5) return '₹' + (x / 1e5).toFixed(2) + ' L';
  return '₹' + x.toLocaleString('en-IN');
}
function pct(x) { return Number(x || 0).toFixed(2) + '%'; }

async function api(path, opts = {}) {
  const headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
  const res = await fetch(API + path, Object.assign({}, opts, { headers }));
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function destroyChart(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

/* ---------------- auth ---------------- */
const $ = (id) => document.getElementById(id);

async function login(username, password) {
  const data = await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  TOKEN = data.access_token;
  localStorage.setItem('mi_token', TOKEN);
  await boot();
}

function logout() {
  TOKEN = ''; ME = null;
  localStorage.removeItem('mi_token');
  $('app-view').classList.add('hidden');
  $('login-view').classList.remove('hidden');
}

$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = $('login-error'); err.classList.add('hidden');
  try { await login($('login-username').value.trim(), $('login-password').value); }
  catch (ex) { err.textContent = ex.message; err.classList.remove('hidden'); }
});
$('logout').addEventListener('click', logout);

/* ---------------- routing ---------------- */
function setActiveNav(name) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.nav === name));
  const mob = $('mobile-nav'); if (mob) mob.value = name;
}
async function navigate(name) {
  setActiveNav(name);
  try {
    if (name === 'dashboard') await renderDashboard();
    else if (name === 'trends') await renderTrends();
    else if (name === 'entry') await renderEntry();
    else if (name === 'users') await renderUsers();
  } catch (ex) {
    $('page').innerHTML = `<div class="card p-6 text-red-600">Error: ${ex.message}</div>`;
  }
}
document.querySelectorAll('.nav-btn').forEach(b => b.addEventListener('click', () => navigate(b.dataset.nav)));
$('mobile-nav').addEventListener('change', (e) => navigate(e.target.value));

/* ---------------- boot ---------------- */
async function boot() {
  try {
    ME = await api('/api/auth/me');
  } catch (ex) { logout(); return; }
  $('login-view').classList.add('hidden');
  $('app-view').classList.remove('hidden');
  $('who').textContent = `${ME.username} · ${ME.role}`;
  // role-gated nav
  const isEditor = ME.role === 'editor' || ME.role === 'admin';
  const isAdmin = ME.role === 'admin';
  document.querySelectorAll('.editor-only').forEach(el => el.classList.toggle('hidden', !isEditor));
  document.querySelectorAll('.admin-only').forEach(el => el.classList.toggle('hidden', !isAdmin));
  Array.from($('mobile-nav').options).forEach(o => {
    if (o.value === 'entry') o.hidden = !isEditor;
    if (o.value === 'users') o.hidden = !isAdmin;
  });
  await navigate('dashboard');
}

/* ---------------- dashboard ---------------- */
function kpiCard(label, value, sub, accent) {
  return `<div class="card p-5">
    <div class="text-sm text-slate-500">${label}</div>
    <div class="kpi-value text-2xl font-bold mt-1 ${accent || 'text-slate-900'}">${value}</div>
    <div class="text-xs text-slate-400 mt-1">${sub || ''}</div>
  </div>`;
}

async function renderDashboard() {
  const d = await api('/api/dashboard');
  if (d.empty) { $('page').innerHTML = `<div class="card p-6">No meetings yet. Use <b>Data Entry</b> to add one.</div>`; return; }
  const t = d.totals, ag = d.ageing, q = d.quotation, s = d.sales.totals;

  $('page').innerHTML = `
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p class="text-sm text-slate-500">Meeting ${d.meeting.meeting_date} · period ${d.meeting.period_start || '?'} → ${d.meeting.period_end || '?'}</p>
      </div>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      ${kpiCard('Total Outstanding', inr(t.outstanding), `MBS ${inr(t.outstanding_mbs)} · MCORP ${inr(t.outstanding_mcorp)}`, 'text-brand-700')}
      ${kpiCard('Collected (week)', inr(t.collected), `Efficiency ${pct(t.collection_efficiency_pct)}`, 'text-green-600')}
      ${kpiCard('60+ Days Overdue', inr(ag.overdue_total), `${pct(ag.overdue_pct)} of book — at risk`, 'text-red-600')}
      ${kpiCard('Quotation Conversion', pct(q.conversion_pct), `${q.confirmed} of ${q.prepared} confirmed`, 'text-amber-600')}
    </div>

    <div class="grid lg:grid-cols-2 gap-4 mb-6">
      <div class="card p-5">
        <h3 class="font-semibold mb-1">Ageing of Receivables</h3>
        <p class="text-xs text-slate-400 mb-3">Outstanding by bucket, split MBS vs MCORP</p>
        <div class="chart-box"><canvas id="ageingChart"></canvas></div>
      </div>
      <div class="card p-5">
        <h3 class="font-semibold mb-1">Collection % by Agent</h3>
        <p class="text-xs text-slate-400 mb-3">Higher is better — who is recovering vs lagging</p>
        <div class="chart-box"><canvas id="leaderChart"></canvas></div>
      </div>
    </div>

    <div class="grid lg:grid-cols-2 gap-4 mb-6">
      <div class="card p-5">
        <h3 class="font-semibold mb-1">Quotation Funnel</h3>
        <p class="text-xs text-slate-400 mb-3">Prepared → Confirmed pipeline</p>
        <div class="chart-box-sm"><canvas id="quoteChart"></canvas></div>
      </div>
      <div class="card p-5">
        <h3 class="font-semibold mb-1">Sales vs Purchase by Branch (tons)</h3>
        <p class="text-xs text-slate-400 mb-3">Tonnage movement per branch</p>
        <div class="chart-box-sm"><canvas id="branchChart"></canvas></div>
      </div>
    </div>

    <div class="card p-5 mb-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-semibold">AI Insights</h3>
        <div class="flex items-center gap-2">
          <span id="insight-source" class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"></span>
          <button id="refresh-insight" class="text-xs text-brand-600 hover:underline">Regenerate</button>
        </div>
      </div>
      <div id="insight-body" class="insight text-sm text-slate-700">Loading…</div>
    </div>

    <div class="card p-5">
      <h3 class="font-semibold mb-3">Agent Collection Detail</h3>
      <div class="overflow-x-auto">
      <table class="data w-full text-sm text-right">
        <thead class="text-slate-500 border-b">
          <tr><th class="text-left">Agent</th><th>90d</th><th>60d</th><th>30d</th><th>Other</th><th>Outstanding</th><th>Collected</th><th>Coll %</th><th>New Target</th></tr>
        </thead>
        <tbody>
          ${d.agents.map(a => `<tr class="border-b last:border-0">
            <td class="text-left font-medium">${a.agent}</td>
            <td>${inr(a.bucket_totals.d90)}</td>
            <td>${inr(a.bucket_totals.d60)}</td>
            <td>${inr(a.bucket_totals.d30)}</td>
            <td>${inr(a.bucket_totals.other)}</td>
            <td class="font-semibold">${inr(a.outstanding)}</td>
            <td class="text-green-600">${inr(a.collected)}</td>
            <td class="${a.coll_pct < 15 ? 'text-red-600 font-semibold' : ''}">${pct(a.coll_pct)}</td>
            <td>${inr(a.new_target)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </div>
    </div>
  `;

  drawAgeing(d.ageing);
  drawLeaderboard(d.leaderboard);
  drawQuote(d.quotation);
  drawBranches(d.sales.branches);
  loadInsights(d.meeting.id);
}

function drawAgeing(ag) {
  destroyChart('ageingChart');
  const labels = ['90 days', '60 days', '30 days', 'Other'];
  const keys = ['d90', 'd60', 'd30', 'other'];
  charts.ageingChart = new Chart($('ageingChart'), {
    type: 'bar',
    data: { labels, datasets: [
      { label: 'MBS', data: keys.map(k => ag.mbs[k]), backgroundColor: '#3b5bdb' },
      { label: 'MCORP', data: keys.map(k => ag.mcorp[k]), backgroundColor: '#f08c00' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => inr(v) } } },
      plugins: { tooltip: { callbacks: { label: c => c.dataset.label + ': ' + inr(c.raw) } } } }
  });
}

function drawLeaderboard(lb) {
  destroyChart('leaderChart');
  charts.leaderChart = new Chart($('leaderChart'), {
    type: 'bar',
    data: { labels: lb.map(a => a.agent), datasets: [{
      label: 'Coll %', data: lb.map(a => a.coll_pct),
      backgroundColor: lb.map(a => a.coll_pct < 15 ? '#e03131' : a.coll_pct < 25 ? '#f08c00' : '#2f9e44'),
    }]},
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { callback: v => v + '%' } } } }
  });
}

function drawQuote(q) {
  destroyChart('quoteChart');
  charts.quoteChart = new Chart($('quoteChart'), {
    type: 'bar',
    data: { labels: q.stages.map(s => s.stage), datasets: [{
      label: 'Count', data: q.stages.map(s => s.total),
      backgroundColor: '#27408b' }]},
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
  });
}

function drawBranches(branches) {
  destroyChart('branchChart');
  charts.branchChart = new Chart($('branchChart'), {
    type: 'bar',
    data: { labels: branches.map(b => b.branch), datasets: [
      { label: 'Sales', data: branches.map(b => b.sales), backgroundColor: '#2f9e44' },
      { label: 'Purchase', data: branches.map(b => b.purchase), backgroundColor: '#868e96' },
    ]},
    options: { responsive: true, maintainAspectRatio: false }
  });
}

function mdToHtml(md) {
  return md.split(/\n\n+/).map(p =>
    '<p>' + p.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>') + '</p>'
  ).join('');
}
async function loadInsights(meetingId, refresh = false) {
  const body = $('insight-body'); body.textContent = 'Generating…';
  try {
    const d = await api(`/api/meetings/${meetingId}/insights${refresh ? '?refresh=true' : ''}`);
    body.innerHTML = mdToHtml(d.body);
    const tag = $('insight-source');
    tag.textContent = d.source === 'ai' ? 'AI-generated' : 'computed';
    tag.className = 'text-xs px-2 py-0.5 rounded-full ' + (d.source === 'ai' ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500');
    $('refresh-insight').onclick = () => loadInsights(meetingId, true);
  } catch (ex) { body.innerHTML = `<span class="text-red-600">${ex.message}</span>`; }
}

/* ---------------- trends ---------------- */
async function renderTrends() {
  const data = await api('/api/trends');
  if (data.length < 2) {
    $('page').innerHTML = `<h1 class="text-2xl font-bold mb-3">Trends</h1>
      <div class="card p-6 text-slate-500">Add at least 2 meetings to see week-over-week trends. Currently ${data.length}.</div>`;
    return;
  }
  $('page').innerHTML = `<h1 class="text-2xl font-bold mb-4">Week-over-Week Trends</h1>
    <div class="grid lg:grid-cols-2 gap-4">
      <div class="card p-5"><h3 class="font-semibold mb-3">Outstanding vs Collected</h3><div class="chart-box"><canvas id="tAmt"></canvas></div></div>
      <div class="card p-5"><h3 class="font-semibold mb-3">Collection Efficiency & Overdue %</h3><div class="chart-box"><canvas id="tPct"></canvas></div></div>
      <div class="card p-5"><h3 class="font-semibold mb-3">Sales vs Purchase (tons)</h3><div class="chart-box"><canvas id="tSales"></canvas></div></div>
      <div class="card p-5"><h3 class="font-semibold mb-3">Quotation Conversion %</h3><div class="chart-box"><canvas id="tConv"></canvas></div></div>
    </div>`;
  const labels = data.map(d => d.date);
  destroyChart('tAmt'); charts.tAmt = new Chart($('tAmt'), { type: 'line', data: { labels, datasets: [
    { label: 'Outstanding', data: data.map(d => d.outstanding), borderColor: '#3b5bdb', tension: .3 },
    { label: 'Collected', data: data.map(d => d.collected), borderColor: '#2f9e44', tension: .3 } ]},
    options: { responsive: true, maintainAspectRatio: false, scales: { y: { ticks: { callback: v => inr(v) } } } } });
  destroyChart('tPct'); charts.tPct = new Chart($('tPct'), { type: 'line', data: { labels, datasets: [
    { label: 'Collection Eff %', data: data.map(d => d.collection_efficiency_pct), borderColor: '#2f9e44', tension: .3 },
    { label: 'Overdue %', data: data.map(d => d.overdue_pct), borderColor: '#e03131', tension: .3 } ]},
    options: { responsive: true, maintainAspectRatio: false } });
  destroyChart('tSales'); charts.tSales = new Chart($('tSales'), { type: 'line', data: { labels, datasets: [
    { label: 'Sales', data: data.map(d => d.sales_total), borderColor: '#2f9e44', tension: .3 },
    { label: 'Purchase', data: data.map(d => d.purchase_total), borderColor: '#868e96', tension: .3 } ]},
    options: { responsive: true, maintainAspectRatio: false } });
  destroyChart('tConv'); charts.tConv = new Chart($('tConv'), { type: 'line', data: { labels, datasets: [
    { label: 'Conversion %', data: data.map(d => d.quotation_conversion_pct), borderColor: '#f08c00', tension: .3 } ]},
    options: { responsive: true, maintainAspectRatio: false } });
}

/* ---------------- data entry ---------------- */
function collRow() {
  return `<tr class="coll-row border-b">
    <td><input class="cell c-agent rounded border px-2 py-1" placeholder="Agent"/></td>
    ${['d90_mbs','d90_mcorp','d60_mbs','d60_mcorp','d30_mbs','d30_mcorp','other_mbs','other_mcorp','collected_mbs','collected_mcorp','coll_pct','new_target'].map(k =>
      `<td><input type="number" step="any" class="cell c-${k} rounded border px-1 py-1 text-right" value="0"/></td>`).join('')}
    <td><button class="rm text-red-500">✕</button></td>
  </tr>`;
}
function quoteRow(stage = '') {
  return `<tr class="q-row border-b">
    <td><input class="cell q-stage rounded border px-2 py-1" value="${stage}" placeholder="STAGE"/></td>
    <td><input type="number" step="any" class="cell q-mbs rounded border px-1 py-1 text-right" value="0"/></td>
    <td><input type="number" step="any" class="cell q-mcorp rounded border px-1 py-1 text-right" value="0"/></td>
    <td><button class="rm text-red-500">✕</button></td>
  </tr>`;
}
function salesRow() {
  return `<tr class="s-row border-b">
    <td><input class="cell s-person rounded border px-2 py-1" placeholder="Salesperson"/></td>
    <td><input class="cell s-branch rounded border px-2 py-1" placeholder="Branch" value="ALL"/></td>
    <td><input type="number" step="any" class="cell s-pmbs rounded border px-1 py-1 text-right" value="0"/></td>
    <td><input type="number" step="any" class="cell s-pmcorp rounded border px-1 py-1 text-right" value="0"/></td>
    <td><input type="number" step="any" class="cell s-smbs rounded border px-1 py-1 text-right" value="0"/></td>
    <td><input type="number" step="any" class="cell s-smcorp rounded border px-1 py-1 text-right" value="0"/></td>
    <td><button class="rm text-red-500">✕</button></td>
  </tr>`;
}

async function renderEntry() {
  $('page').innerHTML = `
    <h1 class="text-2xl font-bold mb-1">Data Entry</h1>
    <p class="text-sm text-slate-500 mb-4">Add a new weekly meeting. Outstanding totals are computed automatically from the buckets.</p>

    <div class="card p-5 mb-4 grid sm:grid-cols-3 gap-3">
      <div><label class="text-sm text-slate-600">Meeting date</label><input id="m-date" type="date" class="w-full rounded border px-2 py-1"/></div>
      <div><label class="text-sm text-slate-600">Period start</label><input id="m-start" type="date" class="w-full rounded border px-2 py-1"/></div>
      <div><label class="text-sm text-slate-600">Period end</label><input id="m-end" type="date" class="w-full rounded border px-2 py-1"/></div>
    </div>

    <div class="card p-5 mb-4">
      <div class="flex items-center justify-between mb-2"><h3 class="font-semibold">Collections by Agent</h3>
        <button id="add-coll" class="text-sm text-brand-600">+ Add agent</button></div>
      <div class="overflow-x-auto"><table class="w-full text-xs">
        <thead class="text-slate-500"><tr><th>Agent</th><th>90 MBS</th><th>90 MC</th><th>60 MBS</th><th>60 MC</th><th>30 MBS</th><th>30 MC</th><th>Oth MBS</th><th>Oth MC</th><th>Coll MBS</th><th>Coll MC</th><th>Coll%</th><th>New Tgt</th><th></th></tr></thead>
        <tbody id="coll-body"></tbody></table></div>
    </div>

    <div class="card p-5 mb-4">
      <div class="flex items-center justify-between mb-2"><h3 class="font-semibold">Sales / Purchase (tons)</h3>
        <button id="add-sales" class="text-sm text-brand-600">+ Add row</button></div>
      <div class="overflow-x-auto"><table class="w-full text-xs">
        <thead class="text-slate-500"><tr><th>Salesperson</th><th>Branch</th><th>Pur MBS</th><th>Pur MC</th><th>Sale MBS</th><th>Sale MC</th><th></th></tr></thead>
        <tbody id="sales-body"></tbody></table></div>
    </div>

    <div class="card p-5 mb-4">
      <div class="flex items-center justify-between mb-2"><h3 class="font-semibold">Quotations</h3>
        <button id="add-quote" class="text-sm text-brand-600">+ Add stage</button></div>
      <div class="overflow-x-auto"><table class="w-full text-xs">
        <thead class="text-slate-500"><tr><th>Stage</th><th>MBS</th><th>MCORP</th><th></th></tr></thead>
        <tbody id="quote-body"></tbody></table></div>
    </div>

    <div class="flex items-center gap-3">
      <button id="save-meeting" class="bg-brand-600 hover:bg-brand-700 text-white font-medium rounded-lg px-5 py-2">Save meeting</button>
      <span id="save-msg" class="text-sm"></span>
    </div>
  `;

  const collBody = $('coll-body'), salesBody = $('sales-body'), quoteBody = $('quote-body');
  collBody.insertAdjacentHTML('beforeend', collRow());
  salesBody.insertAdjacentHTML('beforeend', salesRow());
  ['PREPARED','CONFIRMED','PENDING','UNDER_PROCESS','NOT_CONFIRMED'].forEach(s => quoteBody.insertAdjacentHTML('beforeend', quoteRow(s)));

  $('add-coll').onclick = () => collBody.insertAdjacentHTML('beforeend', collRow());
  $('add-sales').onclick = () => salesBody.insertAdjacentHTML('beforeend', salesRow());
  $('add-quote').onclick = () => quoteBody.insertAdjacentHTML('beforeend', quoteRow());
  $('page').addEventListener('click', (e) => { if (e.target.classList.contains('rm')) e.target.closest('tr').remove(); });

  $('save-meeting').onclick = saveMeeting;
}

function num(el, sel) { const i = el.querySelector(sel); return i ? parseFloat(i.value || '0') : 0; }
function str(el, sel) { const i = el.querySelector(sel); return i ? i.value.trim() : ''; }

async function saveMeeting() {
  const msg = $('save-msg'); msg.textContent = ''; msg.className = 'text-sm';
  if (!$('m-date').value) { msg.textContent = 'Meeting date is required.'; msg.classList.add('text-red-600'); return; }

  const collections = Array.from(document.querySelectorAll('.coll-row'))
    .filter(r => str(r, '.c-agent'))
    .map(r => ({
      agent: str(r, '.c-agent'),
      d90_mbs: num(r, '.c-d90_mbs'), d90_mcorp: num(r, '.c-d90_mcorp'),
      d60_mbs: num(r, '.c-d60_mbs'), d60_mcorp: num(r, '.c-d60_mcorp'),
      d30_mbs: num(r, '.c-d30_mbs'), d30_mcorp: num(r, '.c-d30_mcorp'),
      other_mbs: num(r, '.c-other_mbs'), other_mcorp: num(r, '.c-other_mcorp'),
      collected_mbs: num(r, '.c-collected_mbs'), collected_mcorp: num(r, '.c-collected_mcorp'),
      coll_pct: num(r, '.c-coll_pct'), new_target: num(r, '.c-new_target'),
    }));

  const sales = Array.from(document.querySelectorAll('.s-row'))
    .filter(r => str(r, '.s-person'))
    .map(r => ({
      salesperson: str(r, '.s-person'), branch: str(r, '.s-branch') || 'ALL',
      purchase_mbs: num(r, '.s-pmbs'), purchase_mcorp: num(r, '.s-pmcorp'),
      sales_mbs: num(r, '.s-smbs'), sales_mcorp: num(r, '.s-smcorp'),
    }));

  const quotations = Array.from(document.querySelectorAll('.q-row'))
    .filter(r => str(r, '.q-stage'))
    .map(r => ({ stage: str(r, '.q-stage'), mbs: num(r, '.q-mbs'), mcorp: num(r, '.q-mcorp') }));

  const body = {
    meeting_date: $('m-date').value,
    period_start: $('m-start').value || null,
    period_end: $('m-end').value || null,
    collections, sales, quotations,
  };
  try {
    const res = await api('/api/meetings', { method: 'POST', body: JSON.stringify(body) });
    msg.textContent = `Saved (meeting #${res.id}). Opening dashboard…`;
    msg.classList.add('text-green-600');
    setTimeout(() => navigate('dashboard'), 800);
  } catch (ex) { msg.textContent = ex.message; msg.classList.add('text-red-600'); }
}

/* ---------------- users ---------------- */
async function renderUsers() {
  const users = await api('/api/users');
  $('page').innerHTML = `
    <h1 class="text-2xl font-bold mb-4">Users & Roles</h1>
    <div class="grid lg:grid-cols-3 gap-4">
      <div class="card p-5 lg:col-span-2">
        <h3 class="font-semibold mb-3">Existing users</h3>
        <table class="data w-full text-sm">
          <thead class="text-slate-500 border-b"><tr><th class="text-left">User</th><th class="text-left">Role</th><th></th></tr></thead>
          <tbody>${users.map(u => `<tr class="border-b last:border-0">
            <td class="text-left font-medium">${u.username}</td>
            <td class="text-left"><span class="px-2 py-0.5 rounded-full text-xs ${u.role==='admin'?'bg-brand-100 text-brand-700':u.role==='editor'?'bg-amber-100 text-amber-700':'bg-slate-100 text-slate-600'}">${u.role}</span></td>
            <td class="text-right">${u.id===ME.id?'<span class="text-xs text-slate-400">you</span>':`<button data-del="${u.id}" class="del-user text-red-500 text-sm">Delete</button>`}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>
      <div class="card p-5">
        <h3 class="font-semibold mb-3">Add user</h3>
        <div class="space-y-3">
          <input id="u-name" class="w-full rounded border px-3 py-2" placeholder="Username"/>
          <input id="u-pass" type="password" class="w-full rounded border px-3 py-2" placeholder="Password (min 4)"/>
          <select id="u-role" class="w-full rounded border px-3 py-2">
            <option value="viewer">viewer — read only</option>
            <option value="editor">editor — can add data</option>
            <option value="admin">admin — full control</option>
          </select>
          <button id="u-create" class="w-full bg-brand-600 hover:bg-brand-700 text-white rounded-lg py-2">Create</button>
          <p id="u-msg" class="text-sm"></p>
        </div>
      </div>
    </div>`;

  document.querySelectorAll('.del-user').forEach(b => b.onclick = async () => {
    if (!confirm('Delete this user?')) return;
    await api('/api/users/' + b.dataset.del, { method: 'DELETE' });
    renderUsers();
  });
  $('u-create').onclick = async () => {
    const m = $('u-msg'); m.textContent = ''; m.className = 'text-sm';
    try {
      await api('/api/users', { method: 'POST', body: JSON.stringify({
        username: $('u-name').value.trim(), password: $('u-pass').value, role: $('u-role').value }) });
      renderUsers();
    } catch (ex) { m.textContent = ex.message; m.classList.add('text-red-600'); }
  };
}

/* ---------------- start ---------------- */
if (TOKEN) boot(); else { $('login-view').classList.remove('hidden'); }
