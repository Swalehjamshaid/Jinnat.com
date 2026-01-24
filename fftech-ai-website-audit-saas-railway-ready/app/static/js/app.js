
// app/static/js/app.js

// Keep a persistent chart instance if you draw it here (index.html draws it already)
let breakdownChartInstance = null;

function updateProgress(percent) {
  const bar = document.getElementById('crawlProgressBar');
  if (!bar) return;
  bar.style.width = percent + '%';
  bar.textContent = percent + '%';
  bar.setAttribute('aria-valuenow', percent);
}

function setLoading(loading) {
  const btn = document.getElementById('btnOpenAudit');
  const btnText = document.getElementById('btnText');
  const btnSpinner = document.getElementById('btnSpinner');
  const progressContainer = document.getElementById('crawlProgressContainer');
  const overlay = document.getElementById('loadingOverlay');

  if (loading) {
    btn.disabled = true;
    btnText.textContent = 'Auditing...';
    btnSpinner.classList.remove('d-none');
    progressContainer?.classList.remove('d-none');
    overlay?.classList.add('active');
    updateProgress(0);
  } else {
    btn.disabled = false;
    btnText.textContent = 'Audit';
    btnSpinner.classList.add('d-none');
    progressContainer?.classList.add('d-none');
    overlay?.classList.remove('active');
  }
}

function resetResults() {
  const resultsDiv = document.getElementById('openResults');
  const ovScore = document.getElementById('ovScore');
  const gradeEl = document.getElementById('grade');
  const onpageEl = document.getElementById('onpageScore');
  const perfEl = document.getElementById('perfScore');
  const coverageEl = document.getElementById('coverageScore');
  const confEl = document.getElementById('confidence');
  const jsonPre = document.getElementById('openJson');

  resultsDiv?.classList.add('d-none');
  if (ovScore) ovScore.textContent = '-';
  if (gradeEl) gradeEl.textContent = '-';
  if (onpageEl) onpageEl.textContent = '-';
  if (perfEl) perfEl.textContent = '-';
  if (coverageEl) coverageEl.textContent = '-';
  if (confEl) confEl.textContent = '-';
  jsonPre?.classList.add('d-none');
  if (jsonPre) jsonPre.textContent = '';
}

function renderResults(data) {
  const resultsDiv = document.getElementById('openResults');
  const ovScore = document.getElementById('ovScore');
  const gradeEl = document.getElementById('grade');
  const onpageEl = document.getElementById('onpageScore');
  const perfEl = document.getElementById('perfScore');
  const coverageEl = document.getElementById('coverageScore');
  const confEl = document.getElementById('confidence');
  const jsonPre = document.getElementById('openJson');

  if (ovScore) ovScore.textContent = data.overall_score ?? '-';
  if (gradeEl) gradeEl.textContent = data.grade ?? '-';
  if (onpageEl) onpageEl.textContent = data.breakdown?.onpage ?? '-';
  if (perfEl) perfEl.textContent = data.breakdown?.performance ?? '-';
  if (coverageEl) coverageEl.textContent = data.breakdown?.coverage ?? '-';
  if (confEl) confEl.textContent = (data.breakdown?.confidence ?? '-') + '%';

  if (jsonPre) {
    jsonPre.textContent = JSON.stringify(data, null, 2);
    jsonPre.classList.remove('d-none');
  }
  resultsDiv?.classList.remove('d-none');
}

function runAudit(url) {
  setLoading(true);
  resetResults();

  const evtSource = new EventSource(`/api/open-audit-progress?url=${encodeURIComponent(url)}`);

  evtSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);

      if (typeof data.crawl_progress === 'number') {
        const pct = Math.round(data.crawl_progress * 100);
        updateProgress(pct);
      }
      if (data.status) {
        // Optional: show status in the button for better UX
        const btnText = document.getElementById('btnText');
        if (btnText && document.getElementById('btnOpenAudit').disabled) {
          btnText.textContent = data.status;
        }
      }
      if (data.finished) {
        evtSource.close();
        setLoading(false);
        renderResults(data);
      }
      if (data.error) {
        console.error('Audit error:', data.error);
      }
    } catch (err) {
      console.error('SSE parse error', err);
    }
  };

  evtSource.onerror = (err) => {
    console.error('SSE connection error', err);
    evtSource.close();
    setLoading(false);
    alert('Error during live audit.');
  };
}

(function init() {
  const btn = document.getElementById('btnOpenAudit');
  if (!btn) return;
  // Avoid duplicate listeners if index.html already binds one:
  btn.replaceWith(btn.cloneNode(true));
  const newBtn = document.getElementById('btnOpenAudit');

  newBtn.addEventListener('click', () => {
    const urlInput = document.getElementById('openUrl');
    const url = urlInput?.value?.trim();
    if (!url || !/^https?:\/\//i.test(url)) {
      return alert('Please enter a valid URL (http/https)');
    }
    runAudit(url);
  });
})();
