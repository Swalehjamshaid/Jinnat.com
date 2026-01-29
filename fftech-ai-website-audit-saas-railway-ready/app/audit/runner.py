<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FF Tech Audit – World-Class Dashboard</title>

  <!-- Bootstrap 5 & Icons -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet" />

  <!-- Font (Inter) -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />

  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

  <style>
    :root{
      --primary:#fbbf24;
      --bg:#0a0f1a;
      --card:rgba(15, 23, 42, 0.72);
      --border:#1f2937;
      --muted:#94a3b8;
      --text:#e2e8f0;
      --success:#22c55e;
      --warning:#eab308;
      --danger:#ef4444;
      --info:#38bdf8;

      --gradient-gold: linear-gradient(135deg, #fbbf24, #f59e0b);
      --gradient-success: linear-gradient(135deg, #22c55e, #16a34a);
      --gradient-warning: linear-gradient(135deg, #eab308, #ca8a04);
      --gradient-danger: linear-gradient(135deg, #ef4444, #dc2626);

      --shadow: 0 10px 35px rgba(0,0,0,0.55);
      --shadow-hover: 0 20px 50px rgba(251,191,36,0.18);
      --focus: 0 0 0 0.25rem rgba(251,191,36,0.30);
    }

    [data-bs-theme="light"]{
      --bg:#f8fafc;
      --card: rgba(255,255,255,0.9);
      --border:#e5e7eb;
      --muted:#64748b;
      --text:#0f172a;
      --shadow: 0 10px 25px rgba(15,23,42,0.08);
      --shadow-hover: 0 18px 45px rgba(15,23,42,0.14);
      --focus: 0 0 0 0.25rem rgba(59,130,246,0.30);
    }

    html,body{ height:100%; }
    body{
      background: var(--bg);
      color: var(--text);
      font-family: "Inter", system-ui, sans-serif;
      min-height: 100vh;
      background-image:
        radial-gradient(circle at 10% 20%, rgba(251,191,36,0.10) 0%, transparent 45%),
        radial-gradient(circle at 95% 10%, rgba(56,189,248,0.08) 0%, transparent 45%);
      background-attachment: fixed;
    }

    .container-narrow{ max-width:1120px; }

    .navbar{
      background: transparent;
      backdrop-filter: blur(8px);
    }
    .brand-badge{
      color: var(--primary) !important;
      font-weight: 800;
      letter-spacing: .3px;
    }

    .theme-toggle{
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      border-radius: .8rem;
      box-shadow: var(--shadow);
    }
    .theme-toggle:focus{ box-shadow: var(--focus); }

    .card{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
      transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .card:hover{
      transform: translateY(-7px);
      box-shadow: var(--shadow-hover);
      border-color: rgba(251,191,36,0.35);
    }

    .title-gradient{
      background: var(--gradient-gold);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .muted{ color: var(--muted); }

    .section-header{
      color: var(--primary);
      margin: 2.2rem 0 1.2rem;
      font-weight: 800;
      letter-spacing: 0.02em;
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: .6rem;
    }
    .section-header:after{
      content:'';
      position:absolute;
      bottom:-8px;
      left:0;
      width:72px;
      height:3px;
      background: var(--gradient-gold);
      border-radius: 3px;
    }

    .form-control.bg-dark{
      background: linear-gradient(180deg, rgba(2,6,23,0.55), rgba(2,6,23,0.78)) !important;
      border: 1px solid var(--border);
      color: var(--text);
      height: 48px;
    }
    .form-control:focus{
      border-color: rgba(251,191,36,0.55);
      box-shadow: var(--focus);
    }

    .btn-run{
      background: var(--gradient-gold);
      border: none;
      font-weight: 900;
      letter-spacing: .3px;
      color: #111827;
      border-radius: 0.9rem;
      box-shadow: 0 10px 26px rgba(251,191,36,0.18);
    }
    .btn-run:hover{ opacity: .95; }

    .btn-outline-danger{
      border-radius: 0.9rem;
    }

    .progress{
      height: 14px;
      background: rgba(30,41,59,0.6);
      border-radius: 9px;
      overflow: hidden;
    }
    .progress-bar{
      background: var(--gradient-gold);
      transition: width 0.9s ease;
      position: relative;
    }
    .progress-bar::after{
      content:"";
      position:absolute; inset:0;
      background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.28) 50%, rgba(255,255,255,0) 100%);
      animation: shimmer 1.9s linear infinite;
    }
    @keyframes shimmer{
      0%{ transform: translateX(-100%); }
      100%{ transform: translateX(100%); }
    }

    .error-box{
      background: rgba(239,68,68,0.12);
      border: 1px solid var(--danger);
      color: #fecaca;
      padding: 1rem 1.25rem;
      border-radius: 1rem;
      margin: 1.25rem 0;
    }

    /* Score ring */
    .score-ring{
      width: 260px; height: 260px;
      margin: 0 auto;
      position: relative;
      filter: drop-shadow(0 12px 35px rgba(251,191,36,0.12));
    }
    .score-ring svg{ transform: rotate(-90deg); }
    .circle-bg{
      fill: none;
      stroke: rgba(255,255,255,0.08);
      stroke-width: 22;
    }
    .circle{
      fill: none;
      stroke-linecap: round;
      stroke-width: 22;
      transition: stroke-dashoffset 1.35s cubic-bezier(0.34, 1.56, 0.64, 1), stroke 1.1s ease;
    }
    #ovScore{
      font-weight: 900;
      letter-spacing: .8px;
    }
    .badge-grade{
      font-size: 1.25rem;
      padding: .65rem 1.1rem;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.10);
      box-shadow: 0 10px 30px rgba(34,197,94,0.18);
    }

    /* KPI cards */
    .metric-card{
      background: linear-gradient(135deg, rgba(30,41,59,0.78), rgba(17,24,39,0.78));
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      padding: 1.55rem 1.35rem;
      text-align: center;
      transition: all 0.35s ease;
      height: 100%;
      position: relative;
      overflow: hidden;
      isolation: isolate;
    }
    .metric-card::before{
      content:"";
      position:absolute;
      inset:-2px;
      background: conic-gradient(from 180deg, rgba(251,191,36,0.10), transparent 40%, rgba(56,189,248,0.08), transparent 80%);
      filter: blur(14px);
      z-index:-1;
      opacity: .85;
    }
    .metric-card:hover{
      transform: translateY(-10px) scale(1.01);
      box-shadow: 0 18px 45px rgba(251,191,36,0.18);
      border-color: rgba(251,191,36,0.35);
    }
    .metric-icon{
      width: 48px; height: 48px;
      display: grid; place-items: center;
      border-radius: 14px;
      margin: 0 auto .75rem;
      background: radial-gradient(circle at 30% 30%, rgba(251,191,36,0.22), rgba(251,191,36,0.06));
      border: 1px solid rgba(251,191,36,0.35);
      color: var(--primary);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
    }
    .metric-label{
      font-size: .82rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .08em;
      font-weight: 800;
    }
    .metric-value{
      font-size: 2.4rem;
      font-weight: 900;
      background: var(--gradient-gold);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      line-height: 1.05;
    }

    /* Insights UI */
    .nav-tabs .nav-link{
      border: 1px solid transparent;
      color: var(--muted);
      font-weight: 800;
      letter-spacing: .2px;
    }
    .nav-tabs .nav-link.active{
      color: var(--text);
      border-color: rgba(251,191,36,0.35);
      background: rgba(251,191,36,0.06);
    }

    details{
      border: 1px solid rgba(148,163,184,0.18);
      border-radius: .9rem;
      padding: .75rem 1rem;
      background: rgba(2,6,23,0.25);
    }
    details + details{ margin-top: .75rem; }
    summary{
      cursor: pointer;
      font-weight: 900;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: .6rem;
      list-style: none;
    }
    summary::-webkit-details-marker{ display: none; }

    .kv-table{
      border-radius: .85rem;
      overflow: hidden;
      border: 1px solid rgba(148,163,184,0.18);
    }
    .kv-table table{
      margin: 0;
    }
    .kv-table th{
      width: 48%;
      color: var(--muted);
      font-weight: 800;
    }

    .code-block{
      background: #0a0f1d;
      color: #93c5fd;
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1rem 1.25rem;
      max-height: 520px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
    }

    .skeleton{
      position: relative;
      overflow: hidden;
      background: linear-gradient(90deg, rgba(148,163,184,0.10), rgba(148,163,184,0.18), rgba(148,163,184,0.10));
      background-size: 200% 100%;
      animation: shimmer 1.6s linear infinite;
      border-radius: .8rem;
      min-height: 18px;
    }

    canvas{ max-height: 360px; margin: 0 auto; display: block; }

    footer{
      border-top: 1px solid var(--border);
      padding-top: 2.5rem;
      margin-top: 4rem;
      color: var(--muted);
    }

    @media (prefers-reduced-motion: reduce){
      * { transition: none !important; animation: none !important; }
    }
  </style>
</head>

<body>
  <!-- Navbar -->
  <nav class="navbar navbar-expand-lg border-bottom border-secondary">
    <div class="container container-narrow py-2 d-flex align-items-center justify-content-between">
      <a class="navbar-brand brand-badge fs-4" href="/">
        <i class="bi bi-cpu-fill me-2"></i>FF Tech Audit
      </a>

      <button id="themeToggle" class="btn btn-sm theme-toggle" type="button" aria-label="Toggle theme" title="Toggle light/dark">
        <i class="bi bi-sun-fill d-none" id="sunIcon"></i>
        <i class="bi bi-moon-stars-fill" id="moonIcon"></i>
      </button>
    </div>
  </nav>

  <div class="container container-narrow py-5">
    <header class="text-center mb-5">
      <h1 class="display-4 fw-black title-gradient">FF Tech Audit Dashboard</h1>
      <p class="lead muted fw-light">World-class graphical visualization of your website audit</p>
    </header>

    <!-- Input -->
    <section class="card p-4 mb-5">
      <div class="row g-3 align-items-end">
        <div class="col-md-8">
          <label class="form-label fw-semibold" for="urlInput">Website URL</label>
          <input id="urlInput" type="text" class="form-control bg-dark text-white" placeholder="e.g., www.example.com" autofocus />
          <div class="form-text muted">Enter domain or full URL. Press <b>Enter</b> to run.</div>
        </div>
        <div class="col-md-4 d-flex gap-2">
          <button id="runBtn" class="btn btn-run w-100">
            <i class="bi bi-rocket-takeoff-fill me-2"></i>RUN AUDIT
          </button>
          <button id="resetBtn" class="btn btn-outline-danger w-100">
            <i class="bi bi-arrow-counterclockwise me-2"></i>RESET
          </button>
        </div>
      </div>

      <div id="statusLine" class="mt-3 small fw-semibold text-info" role="status" aria-live="polite">Status: Idle</div>
      <div class="progress mt-2" aria-label="Crawl progress">
        <div id="progressBar" class="progress-bar" role="progressbar" style="width:0%"></div>
      </div>
    </section>

    <!-- Error Display -->
    <div id="errorBox" class="error-box d-none" role="alert"></div>

    <!-- Results -->
    <div id="resultsArea" class="d-none">
      <!-- Overall Score -->
      <section class="text-center mb-5">
        <h6 class="muted mb-2">Audited URL</h6>
        <h4 id="auditUrl" class="text-info fw-medium text-break">—</h4>

        <div class="score-ring my-5 position-relative">
          <svg viewBox="0 0 240 240" aria-hidden="true">
            <circle class="circle-bg" cx="120" cy="120" r="110"></circle>
            <circle id="scoreCircle" class="circle" cx="120" cy="120" r="110" stroke-dasharray="691" stroke-dashoffset="691"></circle>
          </svg>
          <div class="position-absolute top-50 start-50 translate-middle text-center">
            <div id="ovScore" class="display-2 fw-black title-gradient">—</div>
            <small class="muted">/100</small>
          </div>
        </div>

        <div id="grade" class="badge-grade bg-primary text-white">—</div>
      </section>

      <!-- KPI Cards -->
      <h5 class="section-header"><i class="bi bi-grid-1x2"></i> Key Metrics</h5>
      <section class="row g-4 mb-5" id="kpiSection">
        <!-- Skeletons -->
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
      </section>

      <!-- Dynamic Cards -->
      <h5 class="section-header"><i class="bi bi-collection"></i> Detailed Metrics</h5>
      <section class="row g-4 mb-5" id="dynamicCards"></section>

      <!-- Charts -->
      <h5 class="section-header"><i class="bi bi-bar-chart-steps"></i> Visual Analytics</h5>
      <section class="row g-4 mb-5" id="chartsSection">
        <div class="col-12"><div class="card p-4"><div class="skeleton" style="height:260px"></div></div></div>
      </section>

      <!-- Structured Insights -->
      <h5 class="section-header"><i class="bi bi-diagram-3"></i> Presentable Insights</h5>

      <section class="card p-4">
        <ul class="nav nav-tabs mb-3" id="insightTabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="structured-tab" data-bs-toggle="tab" data-bs-target="#structuredView" type="button" role="tab">
              Structured Insights
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="raw-tab" data-bs-toggle="tab" data-bs-target="#rawView" type="button" role="tab">
              Raw JSON (Advanced)
            </button>
          </li>
        </ul>

        <div class="tab-content">
          <!-- Structured -->
          <div class="tab-pane fade show active" id="structuredView" role="tabpanel">
            <div class="d-flex flex-wrap gap-2 mb-3">
              <button id="expandAllBtn" class="btn btn-sm btn-outline-light">
                <i class="bi bi-arrows-expand me-1"></i>Expand All
              </button>
              <button id="collapseAllBtn" class="btn btn-sm btn-outline-light">
                <i class="bi bi-arrows-collapse me-1"></i>Collapse All
              </button>

              <div class="ms-auto d-flex gap-2">
                <button id="copyJsonBtn" class="btn btn-sm btn-outline-light" type="button">
                  <i class="bi bi-clipboard me-1"></i>Copy JSON
                </button>
                <button id="downloadJsonBtn" class="btn btn-sm btn-outline-light" type="button">
                  <i class="bi bi-download me-1"></i>Download JSON
                </button>
              </div>
            </div>

            <div id="structuredInsights"></div>
          </div>

          <!-- Raw -->
          <div class="tab-pane fade" id="rawView" role="tabpanel">
            <pre id="auditJson" class="code-block"></pre>
          </div>
        </div>
      </section>
    </div>

    <footer class="text-center small mt-5">
      © FF Tech Audit Engine – Beautiful &amp; Adaptive Dashboard
    </footer>
  </div>

  <!-- Bootstrap JS -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

  <script>
    /* ============================================================
       Utilities (safe, flexible, schema-tolerant)
    ============================================================ */
    const $ = (id) => document.getElementById(id);

    if (!Element.prototype.empty) {
      Element.prototype.empty = function () { this.innerHTML = ""; return this; };
    }

    const create = (tag, className = "", html = "") => {
      const el = document.createElement(tag);
      if (className) el.className = className;
      if (html) el.innerHTML = html;
      return el;
    };

    const setText = (id, val) => { if ($(id)) $(id).textContent = (val ?? "—"); };
    const pretty = (obj) => JSON.stringify(obj, null, 2);

    const isObject = (v) => v && typeof v === "object" && !Array.isArray(v);

    // safe getter: get(msg, "a.b.c", fallback)
    function get(obj, path, fallback = undefined) {
      if (!obj) return fallback;
      const parts = String(path).split(".");
      let cur = obj;
      for (const p of parts) {
        if (cur && typeof cur === "object" && p in cur) cur = cur[p];
        else return fallback;
      }
      return cur;
    }

    // human readable labels
    function humanize(key) {
      return String(key || "")
        .replace(/\[(\d+)\]/g, " $1 ")
        .replace(/[._-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/\b\w/g, (c) => c.toUpperCase());
    }

    // format values (bytes, booleans, long strings, nulls)
    function formatValue(key, value, unit = null) {
      if (value === null || value === undefined) return `<span class="muted">—</span>`;

      if (typeof value === "boolean") {
        return value
          ? `<span class="badge bg-success">Yes</span>`
          : `<span class="badge bg-secondary">No</span>`;
      }

      if (typeof value === "number") {
        const k = String(key || "").toLowerCase();
        if (k.includes("bytes")) {
          const n = value;
          const units = ["B", "KB", "MB", "GB"];
          let i = 0; let v = n;
          while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
          const best = `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
          return unit ? `${n} ${unit} <span class="muted">(${best})</span>` : best;
        }
        return unit ? `${value} ${unit}` : value.toLocaleString();
      }

      if (typeof value === "string") {
        if (value.length > 140) {
          return `<span title="${value.replace(/"/g, "&quot;")}">${value.slice(0, 137)}…</span>`;
        }
        return value === "" ? `<span class="muted">—</span>` : value;
      }

      // objects/arrays rendered elsewhere
      return String(value);
    }

    // Make a clean table for a plain object
    function renderKVTable(obj) {
      const rows = Object.entries(obj || {}).map(([k, v]) => {
        return `<tr>
          <th class="text-break">${humanize(k)}</th>
          <td class="text-break">${formatValue(k, v)}</td>
        </tr>`;
      }).join("");

      return `
        <div class="kv-table table-responsive">
          <table class="table table-dark table-bordered table-sm align-middle">
            <tbody>${rows || `<tr><td class="muted">No data</td></tr>`}</tbody>
          </table>
        </div>`;
    }

    // Render a KV array like [{key,value}]
    function renderKVArray(items) {
      const rows = (items || []).map((it) => {
        return `<tr>
          <th class="text-break">${humanize(it.key)}</th>
          <td class="text-break">${formatValue(it.key, it.value)}</td>
        </tr>`;
      }).join("");

      return `
        <div class="kv-table table-responsive">
          <table class="table table-dark table-bordered table-sm align-middle">
            <tbody>${rows || `<tr><td class="muted">No data</td></tr>`}</tbody>
          </table>
        </div>`;
    }

    // Recursive tree renderer for unknown schemas (auto-adapts to changes)
    function renderTree(key, value, openLevel = 0, level = 0) {
      const title = humanize(key);

      // primitive
      if (!isObject(value) && !Array.isArray(value)) {
        return `
          <div class="d-flex justify-content-between gap-3 border-bottom border-secondary-subtle py-2">
            <span class="muted text-break">${title}</span>
            <span class="text-break">${formatValue(key, value)}</span>
          </div>`;
      }

      // details group
      const opened = level < openLevel ? "open" : "";
      let inner = "";

      if (Array.isArray(value)) {
        if (value.length === 0) inner = `<div class="muted">[]</div>`;
        else {
          inner = value.map((v, i) => {
            const childKey = `${key}[${i}]`;
            return `<div class="mt-2">${renderTree(childKey, v, openLevel, level + 1)}</div>`;
          }).join("");
        }
      } else {
        const entries = Object.entries(value);
        if (!entries.length) inner = `<div class="muted">{}</div>`;
        else {
          inner = entries.map(([k, v]) => {
            return `<div class="mt-2">${renderTree(k, v, openLevel, level + 1)}</div>`;
          }).join("");
        }
      }

      return `
        <details ${opened}>
          <summary><i class="bi bi-folder2-open text-warning"></i>${title}</summary>
          <div class="pt-2 ps-2">${inner}</div>
        </details>`;
    }

    function metricTile(label, valueHtml, icon = "bi-graph-up") {
      return `
        <div class="col-md-3 col-sm-6">
          <div class="metric-card">
            <div class="metric-icon"><div class="metric-icon"><i class="bi ${icon}"></i></div></div>
            <div class="metric-label mb-1">${label}</div>
            <div class="metric-value">${valueHtml}</div>
          </div>
        </div>`;
    }

    /* ============================================================
       UI Reset
    ============================================================ */
    function resetUI() {
      setText("statusLine", "Status: Idle");
      $("progressBar").style.width = "0%";

      $("kpiSection")?.empty();
      $("dynamicCards")?.empty();
      $("chartsSection")?.empty();
      $("structuredInsights")?.empty();

      $("auditJson").textContent = "";
      $("resultsArea").classList.add("d-none");
      $("errorBox").classList.add("d-none");

      // Reset gauge
      const circle = $("scoreCircle");
      if (circle) {
        circle.style.strokeDashoffset = "691";
        circle.style.stroke = "#3b82f6";
      }

      // Skeletons back
      $("kpiSection").innerHTML = `
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
        <div class="col-md-3 col-sm-6"><div class="card p-3"><div class="skeleton mb-3" style="height:48px"></div><div class="skeleton mb-2" style="height:18px"></div><div class="skeleton" style="height:44px"></div></div></div>
      `;
      $("chartsSection").innerHTML = `<div class="col-12"><div class="card p-4"><div class="skeleton" style="height:260px"></div></div></div>`;
    }

    /* ============================================================
       Theme Toggle (persisted)
    ============================================================ */
    (function initTheme() {
      const root = document.documentElement;
      const key = "ff_theme";
      const saved = localStorage.getItem(key);
      const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
      const active = saved || (prefersLight ? "light" : "dark");

      root.setAttribute("data-bs-theme", active);

      function updateIcons() {
        const isLight = root.getAttribute("data-bs-theme") === "light";
        $("sunIcon").classList.toggle("d-none", !isLight);
        $("moonIcon").classList.toggle("d-none", isLight);
      }
      updateIcons();

      $("themeToggle").addEventListener("click", () => {
        const now = root.getAttribute("data-bs-theme") === "light" ? "dark" : "light";
        root.setAttribute("data-bs-theme", now);
        localStorage.setItem(key, now);
        updateIcons();
      });
    })();

    /* ============================================================
       Charts
    ============================================================ */
    function renderChart(container, title, data, type = "bar") {
      const col = create("div", "col-12");
      const card = create("div", "card p-4");
      card.innerHTML = `<div class="d-flex align-items-center justify-content-between mb-3">
        <h6 class="muted fw-semibold mb-0">${title}</h6>
        <span class="badge text-bg-dark border" style="border-color: rgba(251,191,36,0.25)">${type.toUpperCase()}</span>
      </div>`;
      const canvas = create("canvas");
      card.appendChild(canvas);
      col.appendChild(card);
      container.appendChild(col);

      const ctx = canvas.getContext("2d");
      new Chart(ctx, {
        type,
        data,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: getComputedStyle(document.documentElement).getPropertyValue("--text") } },
            tooltip: { backgroundColor: "rgba(15,23,42,0.92)" }
          },
          scales: type === "bar" ? {
            x: { ticks: { color: "#93c5fd" }, grid: { color: "rgba(31,41,55,0.35)" } },
            y: { ticks: { color: "#93c5fd" }, grid: { color: "rgba(31,41,55,0.35)" }, beginAtZero: true }
          } : {}
        }
      });
    }

    /* ============================================================
       Structured Insights (Presentable + Flexible)
    ============================================================ */
    function buildStructuredInsights(msg) {
      const root = $("structuredInsights");
      root.empty();

      // 1) Summary Tiles (best for executives)
      const summaryCard = create("div", "card p-4 mb-3");
      summaryCard.innerHTML = `<h6 class="fw-black mb-3"><i class="bi bi-clipboard-data me-2 text-warning"></i>Summary</h6>`;
      const summaryRow = create("div", "row g-4");

      const overall = Number(msg.overall_score ?? 0);
      const grade = msg.grade ?? "—";
      const seo = (isObject(get(msg, "breakdown.seo")) ? get(msg, "breakdown.seo.score") : get(msg, "breakdown.seo")) ?? "—";
      const speed = get(msg, "breakdown.performance.score", "—");
      const comp = get(msg, "breakdown.competitors.top_competitor_score", "—");
      const inLinks = get(msg, "breakdown.links.internal_links_count", "—");

      summaryRow.innerHTML =
        metricTile("Overall", overall, "bi-bullseye") +
        metricTile("Grade", `<span class="badge bg-info text-dark">${grade}</span>`, "bi-award-fill") +
        metricTile("SEO", seo, "bi-search") +
        metricTile("Speed", speed, "bi-speedometer2") +
        metricTile("Competitor", comp, "bi-trophy") +
        metricTile("Internal Links", inLinks, "bi-link-45deg");

      summaryCard.appendChild(summaryRow);
      root.appendChild(summaryCard);

      // 2) Breakdown Panel (auto)
      if (msg.breakdown) {
        const bCard = create("div", "card p-4 mb-3");
        bCard.innerHTML = `<h6 class="fw-black mb-3"><i class="bi bi-speedometer me-2 text-warning"></i>Scoring Breakdown</h6>`;
        const row = create("div", "row g-4");

        const iconMap = {
          seo: "bi-search",
          performance: "bi-speedometer2",
          links: "bi-link-45deg",
          competitors: "bi-people-fill",
          security: "bi-shield-lock",
          ai: "bi-robot"
        };

        Object.entries(msg.breakdown).forEach(([k, v]) => {
          const score = (isObject(v) && "score" in v) ? v.score : v;
          row.innerHTML += metricTile(humanize(k), score ?? "—", iconMap[k.toLowerCase()] || "bi-graph-up");
        });

        bCard.appendChild(row);
        root.appendChild(bCard);
      }

      // 3) Performance → HTML Insights (if exists)
      const htmlIns = get(msg, "breakdown.performance.extras.html_insights");
      if (htmlIns) {
        const pCard = create("div", "card p-4 mb-3");
        pCard.innerHTML = `<h6 class="fw-black mb-3"><i class="bi bi-fileAbsolutely, Khan ✅  
Here is a **fully updated `index.html`** that includes **all the “world‑class” attributes** you asked for:

### ✅ What this `index.html` includes (all in one file)
- **Same WebSocket flow & path**: `/ws` ✅ (no backend change needed)
- **Same IDs preserved** ✅ so your existing backend/output works:
  - `urlInput`, `runBtn`, `resetBtn`, `statusLine`, `progressBar`, `errorBox`, `resultsArea`, `auditUrl`, `scoreCircle`, `ovScore`, `grade`, `kpiSection`, `chartsSection`, `auditJson`
- **Presentable Insights instead of raw debug**
  - **Structured Insights tab (default)**: beautiful, collapsible, sectioned panels
  - **Raw JSON tab**: still available for debugging
- **Extremely flexible schema handling**
  - Auto-renders **unknown/new fields** via a generic tree view (so if backend adds new keys, UI still shows them properly)
- **Dynamic cards** (from `msg.dynamic.cards`)
- **Key–Value Inspector** (from `msg.dynamic.kv`)
- **Charts** using `msg.chart_data` (bar, doughnut, line, etc.)
- **Copy JSON** + **Download JSON**
- **Expand All / Collapse All** structured panels
- **Theme toggle (Dark/Light)** saved to local storage
- **Skeleton loaders + smooth animations**
- **Accessibility improvements**

---

# ✅ Updated `index.html` (Copy/Paste)

> Save this as: `templates/index.html`

```html
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FF Tech Audit – World-Class Dashboard</title>

  <!-- Bootstrap 5 & Icons -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet" />

  <!-- Inter font -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />

  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

  <style>
    :root {
      --primary: #fbbf24;
      --bg: #0a0f1a;
      --card: rgba(15, 23, 42, 0.75);
      --border: #1f2937;
      --muted: #94a3b8;
      --text: #e2e8f0;
      --success: #22c55e;
      --warning: #eab308;
      --danger: #ef4444;
      --info: #38bdf8;

      --gradient-gold: linear-gradient(135deg, #fbbf24, #f59e0b);
      --gradient-success: linear-gradient(135deg, #22c55e, #16a34a);
      --gradient-warning: linear-gradient(135deg, #eab308, #ca8a04);
      --gradient-danger: linear-gradient(135deg, #ef4444, #dc2626);

      --shadow: 0 10px 35px rgba(0,0,0,0.55);
      --shadow-hover: 0 20px 50px rgba(251,191,36,0.18);
      --focus: 0 0 0 .25rem rgba(251,191,36,.25);
    }

    [data-bs-theme="light"]{
      --bg: #f7fafc;
      --card: rgba(255,255,255,0.92);
      --border: #e5e7eb;
      --muted: #64748b;
      --text: #0f172a;
      --shadow: 0 10px 28px rgba(15,23,42,0.10);
      --shadow-hover: 0 18px 46px rgba(15,23,42,0.14);
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: "Inter", system-ui, sans-serif;
      min-height: 100vh;
      background-image:
        radial-gradient(circle at 10% 20%, rgba(251,191,36,0.10) 0%, transparent 40%),
        radial-gradient(circle at 85% 15%, rgba(56,189,248,0.10) 0%, transparent 40%);
      background-attachment: fixed;
    }

    .container-narrow{ max-width: 1120px; }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
      transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
