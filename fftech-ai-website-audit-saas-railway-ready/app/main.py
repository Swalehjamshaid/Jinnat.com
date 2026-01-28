<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FF Tech Audit – World-Class Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {
  --primary: #fbbf24; --bg: #0a0f1a; --card: rgba(15,23,42,0.85);
  --border: #1f2937; --muted: #94a3b8; --text: #e2e8f0; --success: #22c55e;
  --warning: #eab308; --danger: #ef4444;
  --gradient-gold: linear-gradient(135deg,#fbbf24,#f59e0b);
}
body { background: var(--bg); color: var(--text); font-family: "Inter",sans-serif; min-height:100vh; }
.card { background: var(--card); border:1px solid var(--border); border-radius:1.25rem; backdrop-filter:blur(12px); box-shadow:0 10px 35px rgba(0,0,0,0.55); transition: all 0.4s cubic-bezier(0.34,1.56,0.64,1); }
.card:hover{ transform:translateY(-8px); box-shadow:0 20px 50px rgba(251,191,36,0.18);}
.metric-card { cursor:pointer; outline:none; transition: transform 0.3s; }
.metric-card:hover, .metric-card:focus { transform: translateY(-6px) scale(1.02); box-shadow: 0 15px 45px rgba(251,191,36,0.18); }
.kpi { font-weight:900; font-size:3rem; background: var(--gradient-gold); -webkit-background-clip:text; -webkit-text-fill-color:transparent; line-height:1; }
.kpi-label { font-size:0.9rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }
.progress { height:14px; background: rgba(30,41,59,0.6); border-radius:7px; overflow:hidden; }
.progress-bar { background: var(--gradient-gold); transition: width 0.9s ease; position: relative; }
.progress-bar::after { content:""; position:absolute; inset:0; background:linear-gradient(90deg,transparent,rgba(255,255,255,.25),transparent); animation: shimmer 2s linear infinite; }
@keyframes shimmer { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
.score-ring { width:260px; height:260px; margin:0 auto; position:relative; }
.score-ring svg { transform:rotate(-90deg); }
.circle-bg { fill:none; stroke: rgba(255,255,255,0.08); stroke-width:22; }
.circle { fill:none; stroke-linecap:round; stroke-width:22; transition: stroke-dashoffset 1.4s cubic-bezier(0.34,1.56,0.64,1), stroke 1.4s ease; }
.section-header { color: var(--primary); margin: 3rem 0 1.5rem; font-weight:700; letter-spacing:0.02em; position:relative; display:inline-block;}
.section-header:after { content:''; position:absolute; bottom:-6px; left:0; width:60px; height:3px; background: var(--gradient-gold); border-radius:3px; }
:focus-visible { outline: 3px solid var(--primary); outline-offset: 4px; }
.tooltip-inner { background-color: var(--card); color: var(--text); border:1px solid var(--border); font-size:.85rem; }
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg border-bottom border-secondary">
<div class="container"><a class="navbar-brand fw-bold fs-4" href="/" style="color: var(--primary);">FF Tech Audit</a></div>
</nav>
<div class="container py-5">
<header class="text-center mb-5">
<h1 class="display-4 fw-black" style="background: var(--gradient-gold); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">FF Tech Audit Dashboard</h1>
<p class="lead muted fw-light">World-class visualization of your website audit</p>
</header>

<section class="card p-4 mb-5" aria-label="Website URL Input" role="region">
<div class="row g-3 align-items-end">
<div class="col-md-8">
<label class="form-label fw-semibold" for="urlInput">Website URL</label>
<input id="urlInput" type="url" class="form-control bg-dark text-white border-secondary" placeholder="e.g., www.example.com" autofocus>
</div>
<div class="col-md-4 d-flex gap-2">
<button id="runBtn" class="btn btn-primary w-100" tabindex="0"><i class="bi bi-rocket-takeoff-fill me-2"></i>Run Audit</button>
<button id="resetBtn" class="btn btn-outline-danger w-100" tabindex="0"><i class="bi bi-arrow-counterclockwise me-2"></i>Reset</button>
</div>
</div>
<div id="statusLine" class="mt-3 small fw-semibold text-info" role="status" aria-live="polite">Status: Idle</div>
<div class="progress mt-2" role="progressbar" aria-label="Audit Progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
<div id="progressBar" class="progress-bar" style="width:0%"></div>
</div>
</section>

<div id="errorBox" class="alert alert-danger d-none" role="alert"></div>

<div id="resultsArea" class="d-none" role="region" aria-label="Audit Results">
<section class="text-center mb-5">
<h5 class="text-muted mb-2">Audited URL</h5>
<h4 id="auditUrl" class="text-info fw-medium">—</h4>
<div class="score-ring my-5">
<svg viewBox="0 0 240 240">
<circle class="circle-bg" cx="120" cy="120" r="110"/>
<circle id="scoreCircle" class="circle" cx="120" cy="120" r="110" stroke-dasharray="691" stroke-dashoffset="691"/>
</svg>
<div class="position-absolute top-50 start-50 translate-middle text-center">
<div id="ovScore" class="display-2 fw-black text-white">—</div>
<small class="text-muted">/100</small>
</div>
</div>
<div id="grade" class="badge bg-primary text-white badge-pill">—</div>
</section>

<section class="row g-4 mb-5" id="kpiSection" role="region" aria-label="Key Performance Indicators" tabindex="0"></section>

<section>
<h5 class="section-header">Visual Analytics</h5>
<div class="row g-4" id="chartsSection" role="region" aria-label="Charts and Visual Analytics" tabindex="0"></div>
</section>

<section>
<h5 class="section-header">Detailed Audit Insights</h5>
<div id="structuredInsights" role="region" aria-label="Detailed Audit Panels" tabindex="0"></div>
</section>

<section class="mt-5">
<h5 class="section-header toggle-btn" tabindex="0" onclick="$('auditJson').classList.toggle('d-none')">
<i class="bi bi-code-slash me-2"></i>Toggle Raw JSON View
</h5>
<pre id="auditJson" class="code-block d-none"></pre>
</section>
</div>
</div>

<footer class="text-center small text-secondary py-4">
© FF Tech Audit Engine – Beautiful, Accessible & Adaptive Dashboard
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
const $ = id=>document.getElementById(id);
function resetUI(){ setText("statusLine","Status: Idle"); $("progressBar").style.width="0%"; $("progressBar").setAttribute("aria-valuenow",0); $("kpiSection").innerHTML=""; $("chartsSection").innerHTML=""; $("structuredInsights").innerHTML=""; $("auditJson").textContent=""; $("resultsArea").classList.add("d-none"); $("errorBox").classList.add("d-none"); const c=$("scoreCircle"); if(c){c.style.strokeDashoffset="691"; c.style.stroke="#3b82f6";} }
function setText(id,val){ $(id) && ($(id).textContent=val??"—"); }
$("urlInput").addEventListener("keydown",e=>{if(e.key==="Enter")$("runBtn").click();});
function updateStatus(msg){
  if(msg.status){ const s=$("statusLine"); s.textContent=`Status: ${msg.status}`; s.setAttribute('aria-live','polite'); }
  if(typeof msg.crawl_progress==="number"){ const p=$("progressBar"); const val=Math.min(100,Math.max(0,msg.crawl_progress)); p.style.width=val+"%"; p.setAttribute('aria-valuenow',val);}
}
$("runBtn").addEventListener("click",()=>{
  const url=$("urlInput").value.trim();
  if(!url){ $("errorBox").textContent="Please enter a valid URL"; $("errorBox").classList.remove("d-none"); return; }
  $("resultsArea").classList.remove("d-none");
  $("auditUrl").textContent=url;

  const ws = new WebSocket(`ws://${window.location.host}/ws`);
  ws.addEventListener('open',()=>{ ws.send(JSON.stringify({url})); });
  ws.addEventListener('message', e=>{
    let msg=JSON.parse(e.data);
    updateStatus(msg);
    $("auditJson").textContent=JSON.stringify(msg,null,2);

    // Example KPI update
    if(msg.kpis){
      $("kpiSection").innerHTML = "";
      msg.kpis.forEach(k=>{
        const div=document.createElement("div");
        div.className="col-md-3 metric-card";
        div.tabIndex=0;
        div.setAttribute("role","group");
        div.setAttribute("aria-label",k.name);
        div.innerHTML=`<div class="card p-3 text-center">
          <div class="kpi">${k.value}</div>
          <div class="kpi-label">${k.name}</div>
        </div>`;
        $("kpiSection").appendChild(div);
      });
    }

    // Example Overall score update
    if(typeof msg.score==="number"){
      const s=msg.score; setText("ovScore",s); $("scoreCircle").style.strokeDashoffset = 691 - (691*s/100);
      $("scoreCircle").style.stroke = s>80?"#22c55e":s>60?"#eab308":"#ef4444";
      if(msg.grade)setText("grade",msg.grade);
    }
  });
  ws.addEventListener('close',()=>console.log("WS closed"));
});

$("resetBtn").addEventListener("click",()=>{ resetUI(); });
</script>
</body>
</html>
