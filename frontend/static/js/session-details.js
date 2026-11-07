/**
 * FACEGUARD AI - Forensic Session Details & Audit Controller
 * Displays complete fraud assessment, confirmed event breakdown, Matplotlib chart, and JSON export.
 */
import { api } from './api.js';
import { renderNavigation, renderHeader, showToast } from './components.js';

let activeSessionId = null;
let currentReportData = null;
let allConfirmedEvents = [];
let eventsCurrentPage = 1;
const EVENTS_PAGE_SIZE = 10;

async function initSessionDetails() {
  renderNavigation('details');
  renderHeader('Session Forensic Analysis', 'Auditor investigation view, algorithmic decision breakdown, and compliance export.');

  // Attach Events Pagination Listeners
  const eventsPrev = document.getElementById('eventsPrevBtn');
  const eventsNext = document.getElementById('eventsNextBtn');

  if (eventsPrev) {
    eventsPrev.addEventListener('click', () => {
      if (eventsCurrentPage > 1) {
        eventsCurrentPage--;
        renderConfirmedEventsPage(eventsCurrentPage);
      }
    });
  }

  if (eventsNext) {
    eventsNext.addEventListener('click', () => {
      const maxPages = Math.ceil(allConfirmedEvents.length / EVENTS_PAGE_SIZE) || 1;
      if (eventsCurrentPage < maxPages) {
        eventsCurrentPage++;
        renderConfirmedEventsPage(eventsCurrentPage);
      }
    });
  }

  const urlParams = new URLSearchParams(window.location.search);
  activeSessionId = urlParams.get('session_id');

  if (!activeSessionId) {
    // If no session passed, load latest session ID from backend
    await findLatestSession();
  }

  if (activeSessionId) {
    await loadSessionAnalysis(activeSessionId);
  } else {
    showEmptyInvestigationNotice();
  }

  // Refresh Button
  const refreshBtn = document.getElementById('refreshDetailsBtn');
  const refreshIcon = document.getElementById('refreshIcon');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      try {
        if (refreshIcon) refreshIcon.classList.add('animate-spin');
        if (!activeSessionId) {
          await findLatestSession();
        }
        if (activeSessionId) {
          await loadSessionAnalysis(activeSessionId);
          showToast('Investigation telemetry refreshed successfully.', 'success');
        } else {
          showToast('No session selected to refresh.', 'info');
        }
      } catch (err) {
        showToast(`Refresh error: ${err.message}`, 'error');
      } finally {
        if (refreshIcon) {
          setTimeout(() => refreshIcon.classList.remove('animate-spin'), 600);
        }
      }
    });
  }

  // Export JSON Report Button
  const exportBtn = document.getElementById('exportJsonReportBtn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      exportReportAsJson();
    });
  }
}

async function findLatestSession() {
  try {
    const sessions = await api.get('/fraud/sessions');
    if (Array.isArray(sessions) && sessions.length > 0) {
      activeSessionId = sessions[0].session_id;
    }
  } catch (err) {
    console.warn('Unable to query latest session:', err);
  }
}

async function loadSessionAnalysis(sessionId) {
  try {
    // 1. Fetch Session Detail
    const session = await api.get(`/fraud/sessions/${sessionId}`);
    // 2. Fetch Consolidated Fraud Report
    const report = await api.get(`/fraud/sessions/${sessionId}/report`);
    currentReportData = report;

    // Populate Candidate & Session Metadata
    document.getElementById('detailSessionId').textContent = session.session_id;
    document.getElementById('detailCandidateId').textContent = session.candidate_id;
    document.getElementById('detailInterviewId').textContent = session.interview_id;
    document.getElementById('detailTenantId').textContent = session.tenant_id;
    document.getElementById('detailConsent').textContent = session.consent_recorded ? 'RECORDED (GDPR Compliant)' : 'NOT RECORDED';
    document.getElementById('detailCreated').textContent = new Date(session.created_at).toLocaleString();

    // Populate Risk Assessment
    const risk = report.risk_assessment;
    const score = risk ? risk.risk_score : 0.0;
    const level = risk ? risk.risk_level : 'LOW';
    const recommendation = risk ? risk.recommendation : 'NO_ACTION';

    document.getElementById('detailRiskScore').textContent = score.toFixed(1);
    document.getElementById('detailRiskBar').style.width = `${Math.min(100, score)}%`;

    const levelBadge = document.getElementById('detailRiskLevelBadge');
    levelBadge.textContent = level;

    const recBadge = document.getElementById('detailRecommendationBadge');
    recBadge.textContent = recommendation;

    if (level === 'CRITICAL' || level === 'HIGH') {
      levelBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200';
      recBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200';
      document.getElementById('detailRiskBar').className = 'h-full bg-gradient-to-r from-amber-500 to-rose-600 rounded-full transition-all duration-300';
    } else if (level === 'MEDIUM') {
      levelBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200';
      recBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200';
      document.getElementById('detailRiskBar').className = 'h-full bg-gradient-to-r from-emerald-500 to-amber-500 rounded-full transition-all duration-300';
    } else {
      levelBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200';
      recBadge.className = 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200';
      document.getElementById('detailRiskBar').className = 'h-full bg-gradient-to-r from-emerald-500 to-sky-500 rounded-full transition-all duration-300';
    }

    // Populate Confirmed Events Table with Pagination
    allConfirmedEvents = report.confirmed_events || [];
    eventsCurrentPage = 1;
    renderConfirmedEventsPage(eventsCurrentPage);

    // Load Matplotlib Forensic Graphic
    loadForensicChart(sessionId);

  } catch (err) {
    showToast(`Failed to load investigation details: ${err.message}`, 'error');
  }
}

function renderConfirmedEventsPage(page) {
  const tableBody = document.getElementById('detailEventsTableBody');
  const emptyEl = document.getElementById('detailEventsEmpty');
  const countBadge = document.getElementById('detailEventCountBadge');
  const paginationEl = document.getElementById('eventsPagination');
  const pageInfoEl = document.getElementById('eventsPageInfo');
  const pageNumEl = document.getElementById('eventsPageNumber');
  const prevBtn = document.getElementById('eventsPrevBtn');
  const nextBtn = document.getElementById('eventsNextBtn');

  if (!tableBody) return;
  tableBody.innerHTML = '';

  const total = allConfirmedEvents.length;
  if (countBadge) countBadge.textContent = `${total} Event${total === 1 ? '' : 's'}`;

  if (total === 0) {
    if (emptyEl) emptyEl.classList.remove('hidden');
    if (paginationEl) paginationEl.classList.add('hidden');
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');

  const totalPages = Math.ceil(total / EVENTS_PAGE_SIZE) || 1;
  eventsCurrentPage = Math.max(1, Math.min(page, totalPages));

  const startIdx = (eventsCurrentPage - 1) * EVENTS_PAGE_SIZE;
  const endIdx = Math.min(startIdx + EVENTS_PAGE_SIZE, total);
  const pageEvents = allConfirmedEvents.slice(startIdx, endIdx);

  pageEvents.forEach((ev, idx) => {
    const row = document.createElement('tr');
    row.className = 'border-b border-slate-100 text-xs font-mono hover:bg-slate-50 transition';

    let severityBadge = 'bg-slate-100 text-slate-700 border-slate-200';
    if (ev.severity === 'CRITICAL' || ev.severity === 'HIGH') {
      severityBadge = 'bg-rose-50 text-rose-700 border-rose-200 font-bold';
    } else if (ev.severity === 'MEDIUM') {
      severityBadge = 'bg-amber-50 text-amber-700 border-amber-200 font-semibold';
    } else if (ev.severity === 'LOW') {
      severityBadge = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }

    const timeStr = new Date(ev.timestamp_ms).toLocaleTimeString();
    const durationSec = (ev.duration_ms / 1000).toFixed(1);

    row.innerHTML = `
      <td class="py-3 px-4 text-slate-500">#${startIdx + idx + 1}</td>
      <td class="py-3 px-4 font-bold text-slate-900">
        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-900 font-bold">
          ${ev.event_type}
        </span>
      </td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${severityBadge}">
          ${ev.severity}
        </span>
      </td>
      <td class="py-3 px-4 text-indigo-700 font-bold">${(ev.confidence * 100).toFixed(0)}%</td>
      <td class="py-3 px-4 text-slate-700 font-medium">${durationSec}s</td>
      <td class="py-3 px-4 text-slate-600">${timeStr}</td>
      <td class="py-3 px-4 text-slate-500 font-mono text-[10px] truncate max-w-[200px]" title='${JSON.stringify(ev.evidence_metadata)}'>
        ${JSON.stringify(ev.evidence_metadata)}
      </td>
    `;
    tableBody.appendChild(row);
  });

  // Update Pagination Controls
  if (paginationEl) {
    paginationEl.classList.remove('hidden');
    if (pageInfoEl) pageInfoEl.textContent = `Showing ${startIdx + 1} to ${endIdx} of ${total} events`;
    if (pageNumEl) pageNumEl.textContent = `Page ${eventsCurrentPage} of ${totalPages}`;
    if (prevBtn) prevBtn.disabled = eventsCurrentPage <= 1;
    if (nextBtn) nextBtn.disabled = eventsCurrentPage >= totalPages;
  }
}

async function loadForensicChart(sessionId) {
  const chartImg = document.getElementById('detailChartImg');
  const chartLoading = document.getElementById('detailChartLoading');

  try {
    const res = await api.fetchWithTimeout(api.buildUrl(`/fraud/sessions/${sessionId}/analytics/chart`), {
      headers: api.getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    chartImg.src = URL.createObjectURL(blob);
    chartLoading.classList.add('hidden');
    chartImg.classList.remove('hidden');
  } catch (err) {
    chartLoading.textContent = `Forensic telemetry diagram unavailable (${err.message})`;
  }
}

function exportReportAsJson() {
  if (!currentReportData) {
    showToast('No report data available to export.', 'warning');
    return;
  }
  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(currentReportData, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute('href', dataStr);
  downloadAnchor.setAttribute('download', `FACEGUARD_REPORT_${activeSessionId || 'SESSION'}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  showToast('Audit JSON report exported successfully.', 'success');
}

function showEmptyInvestigationNotice() {
  const workArea = document.querySelector('main');
  if (workArea) {
    workArea.innerHTML = `
      <div class="glass-card p-12 text-center rounded-2xl max-w-lg mx-auto space-y-4">
        <span class="text-4xl">📂</span>
        <h3 class="text-base font-bold text-slate-900">No Session Selected</h3>
        <p class="text-xs text-slate-500">Please choose a candidate session from the Session History to view the complete forensic breakdown.</p>
        <a href="/history" class="inline-block bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2.5 px-5 rounded-xl transition">
          View Session History
        </a>
      </div>
    `;
  }
}

document.addEventListener('DOMContentLoaded', initSessionDetails);
