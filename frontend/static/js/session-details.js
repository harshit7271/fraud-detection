/**
 * FACEGUARD AI - Forensic Session Details & Audit Controller
 * Displays complete fraud assessment, confirmed event breakdown, Matplotlib chart, and JSON export.
 */
import { api } from './api.js';
import { renderNavigation, renderHeader, showToast } from './components.js';

let activeSessionId = null;
let currentReportData = null;
let allConfirmedEvents = [];

function setElText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

async function initSessionDetails() {
  renderNavigation('details');
  renderHeader('Session Forensic Analysis', 'Auditor investigation view, algorithmic decision breakdown, and compliance export.');

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

    // Populate Candidate & Session Metadata safely
    setElText('detailSessionId', session.session_id || '—');
    setElText('detailCandidateId', session.candidate_id || '—');
    setElText('detailInterviewId', session.interview_id || '—');
    setElText('detailTenantId', session.tenant_id || '—');
    setElText('detailStatus', session.status || 'ACTIVE');

    // Populate Risk Assessment
    const risk = report.risk_assessment;
    const score = risk ? risk.risk_score : 0.0;
    const level = risk ? risk.risk_level : 'LOW';

    setElText('detailRiskScore', score.toFixed(1));

    // Risk badge styling
    const riskBadge = document.getElementById('detailRiskBadge');
    if (riskBadge) {
      riskBadge.textContent = level;
      if (level === 'CRITICAL' || level === 'HIGH') {
        riskBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-rose-50 text-rose-700 border border-rose-200';
      } else if (level === 'MEDIUM') {
        riskBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-amber-50 text-amber-700 border border-amber-200';
      } else {
        riskBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-emerald-50 text-emerald-700 border border-emerald-200';
      }
    }

    // Recommendation text
    let recText = 'NO ACTION REQUIRED (CLEARED)';
    if (level === 'CRITICAL') {
      recText = 'CRITICAL FRAUD RISK — AUDITOR REVIEW MANDATORY';
    } else if (level === 'HIGH') {
      recText = 'HIGH RISK DETECTED — RE-AUTHENTICATION REQUIRED';
    } else if (level === 'MEDIUM') {
      recText = 'MODERATE SUSPICION — AUDITOR RE-EVALUATION ADVISED';
    }
    setElText('detailRecommendation', recText);

    // Confirmed Events
    allConfirmedEvents = report.confirmed_events || [];

    // Counters
    setElText('detailTotalEvents', allConfirmedEvents.length);
    const mismatchCount = allConfirmedEvents.filter(e => e.event_type === 'IDENTITY_MISMATCH').length;
    const absenceCount = allConfirmedEvents.filter(e => e.event_type === 'FACE_ABSENT').length;
    setElText('detailMismatchEvents', mismatchCount);
    setElText('detailAbsenceEvents', absenceCount);

    // Render Events Ledger
    renderConfirmedEventsLedger(allConfirmedEvents);

    // Load Matplotlib Forensic Trajectory Graphic
    await loadForensicChart(sessionId);

  } catch (err) {
    console.error('Failed to load investigation details:', err);
    showToast(`Failed to load investigation details: ${err.message}`, 'error');
  }
}

function renderConfirmedEventsLedger(events) {
  const tableBody = document.getElementById('eventsLedgerTableBody');
  const emptyEl = document.getElementById('eventsLedgerEmpty');
  const countBadge = document.getElementById('eventsLedgerBadge');

  if (!tableBody) return;
  tableBody.innerHTML = '';

  const total = events ? events.length : 0;
  if (countBadge) countBadge.textContent = `${total} Event${total === 1 ? '' : 's'}`;

  if (total === 0) {
    if (emptyEl) emptyEl.classList.remove('hidden');
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');

  events.forEach((ev, idx) => {
    const row = document.createElement('tr');
    row.className = 'border-b border-zinc-100 text-xs font-mono hover:bg-zinc-50 transition';

    let severityBadge = 'bg-zinc-100 text-zinc-700 border-zinc-200';
    if (ev.severity === 'CRITICAL' || ev.severity === 'HIGH') {
      severityBadge = 'bg-rose-50 text-rose-700 border-rose-200 font-bold';
    } else if (ev.severity === 'MEDIUM') {
      severityBadge = 'bg-amber-50 text-amber-700 border-amber-200 font-semibold';
    } else if (ev.severity === 'LOW') {
      severityBadge = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }

    const timeStr = ev.timestamp_ms ? new Date(ev.timestamp_ms).toLocaleTimeString() : '—';
    const durationSec = typeof ev.duration_ms === 'number' ? (ev.duration_ms / 1000).toFixed(1) : '—';
    const metadataStr = ev.evidence_metadata ? JSON.stringify(ev.evidence_metadata) : '{}';

    row.innerHTML = `
      <td class="py-3 px-4 font-bold text-zinc-950">
        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-900 font-bold">
          ${ev.event_type}
        </span>
      </td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${severityBadge}">
          ${ev.severity}
        </span>
      </td>
      <td class="py-3 px-4 text-zinc-900 font-bold">${typeof ev.confidence === 'number' ? (ev.confidence * 100).toFixed(0) + '%' : '100%'}</td>
      <td class="py-3 px-4 text-zinc-600">${timeStr}</td>
      <td class="py-3 px-4 text-zinc-700 font-medium">${durationSec}s</td>
      <td class="py-3 px-4 text-zinc-500 font-mono text-[10px] text-right truncate max-w-[220px]" title='${metadataStr}'>
        ${metadataStr}
      </td>
    `;
    tableBody.appendChild(row);
  });
}

async function loadForensicChart(sessionId) {
  const chartImg = document.getElementById('detailChartImg');
  const chartSpinner = document.getElementById('detailChartSpinner');

  try {
    const res = await api.fetchWithTimeout(api.buildUrl(`/fraud/sessions/${sessionId}/analytics/chart`), {
      headers: api.getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    if (chartImg) {
      chartImg.src = URL.createObjectURL(blob);
      chartImg.classList.remove('hidden');
    }
    if (chartSpinner) {
      chartSpinner.classList.add('hidden');
    }
  } catch (err) {
    console.error('Forensic chart rendering error:', err);
    if (chartSpinner) {
      chartSpinner.innerHTML = `
        <span class="text-xs font-mono text-zinc-500">Forensic Trajectory graphic not available for this session (${err.message})</span>
      `;
    }
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
        <h3 class="text-base font-bold text-zinc-950">No Session Selected</h3>
        <p class="text-xs text-zinc-500">Please choose a candidate session from the Session History to view the complete forensic breakdown.</p>
        <a href="/history" class="inline-block bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-2.5 px-5 rounded-xl transition shadow-xs">
          View Session History
        </a>
      </div>
    `;
  }
}

document.addEventListener('DOMContentLoaded', initSessionDetails);
