/**
 * FACEGUARD AI - Dashboard Controller
 * Connects to live backend APIs to display real session metrics and system health.
 */
import { api } from './api.js?v=3.0.0';
import { renderNavigation, renderHeader, showToast } from './components.js?v=3.0.0';

let allDashboardSessions = [];
let dashboardCurrentPage = 1;
const SESSIONS_PER_PAGE = 10;

async function initDashboard() {
  renderNavigation('dashboard');
  renderHeader('Executive Dashboard', 'Overview of enterprise proctoring sessions, biometric telemetry, and active fraud events.');

  // Attach Pagination Listeners
  const prevBtn = document.getElementById('recentSessionsPrevBtn');
  const nextBtn = document.getElementById('recentSessionsNextBtn');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (dashboardCurrentPage > 1) {
        dashboardCurrentPage--;
        renderRecentSessionsPage(dashboardCurrentPage);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const maxPages = Math.ceil(allDashboardSessions.length / SESSIONS_PER_PAGE) || 1;
      if (dashboardCurrentPage < maxPages) {
        dashboardCurrentPage++;
        renderRecentSessionsPage(dashboardCurrentPage);
      }
    });
  }

  await loadDashboardMetrics();

  // Listen for tenant switch to re-fetch
  window.addEventListener('tenantChanged', () => {
    dashboardCurrentPage = 1;
    loadDashboardMetrics();
  });
}

async function loadDashboardMetrics() {
  const totalSessionsEl = document.getElementById('statTotalSessions');
  const analyzedSessionsEl = document.getElementById('statAnalyzedSessions');
  const suspiciousSessionsEl = document.getElementById('statSuspiciousSessions');
  const fraudEventsEl = document.getElementById('statFraudEvents');
  const emptyStateEl = document.getElementById('recentSessionsEmpty');

  try {
    // 1. Query sessions for the active tenant
    const sessions = await api.get('/fraud/sessions');
    allDashboardSessions = Array.isArray(sessions) ? sessions : [];

    let totalSessions = 0;
    let analyzedCount = 0;
    let suspiciousCount = 0;
    let totalFraudEvents = 0;

    if (allDashboardSessions.length > 0) {
      totalSessions = allDashboardSessions.length;

      allDashboardSessions.forEach(s => {
        const risk = s.current_risk;
        if (risk && risk.risk_score > 0) {
          analyzedCount++;
        }
        if (risk && risk.risk_score >= 25.0) {
          suspiciousCount++;
        }
        const count = s.total_events ?? (risk ? risk.total_events : 0) ?? 0;
        totalFraudEvents += count;
      });

      renderRecentSessionsPage(dashboardCurrentPage);
    } else {
      const sessionsTableBody = document.getElementById('recentSessionsTableBody');
      if (sessionsTableBody) sessionsTableBody.innerHTML = '';
      if (emptyStateEl) emptyStateEl.classList.remove('hidden');
      const paginationEl = document.getElementById('recentSessionsPagination');
      if (paginationEl) paginationEl.classList.add('hidden');
    }

    // Update Telemetry Metrics
    if (totalSessionsEl) totalSessionsEl.textContent = totalSessions;
    if (analyzedSessionsEl) analyzedSessionsEl.textContent = analyzedCount;
    if (suspiciousSessionsEl) suspiciousSessionsEl.textContent = suspiciousCount;
    if (fraudEventsEl) fraudEventsEl.textContent = totalFraudEvents;

  } catch (err) {
    console.error('Failed to load dashboard metrics:', err);
    if (totalSessionsEl) totalSessionsEl.textContent = '0';
    if (analyzedSessionsEl) analyzedSessionsEl.textContent = '0';
    if (suspiciousSessionsEl) suspiciousSessionsEl.textContent = '0';
    if (fraudEventsEl) fraudEventsEl.textContent = '0';
    if (emptyStateEl) {
      emptyStateEl.textContent = `Backend status: ${err.message}`;
      emptyStateEl.classList.remove('hidden');
    }
  }
}

function renderRecentSessionsPage(page) {
  const sessionsTableBody = document.getElementById('recentSessionsTableBody');
  const emptyStateEl = document.getElementById('recentSessionsEmpty');
  const paginationEl = document.getElementById('recentSessionsPagination');
  const pageInfoEl = document.getElementById('recentSessionsPageInfo');
  const pageNumEl = document.getElementById('recentSessionsPageNumber');
  const prevBtn = document.getElementById('recentSessionsPrevBtn');
  const nextBtn = document.getElementById('recentSessionsNextBtn');

  if (!sessionsTableBody) return;
  sessionsTableBody.innerHTML = '';

  if (allDashboardSessions.length === 0) {
    if (emptyStateEl) emptyStateEl.classList.remove('hidden');
    if (paginationEl) paginationEl.classList.add('hidden');
    return;
  }
  if (emptyStateEl) emptyStateEl.classList.add('hidden');

  const total = allDashboardSessions.length;
  const totalPages = Math.ceil(total / SESSIONS_PER_PAGE) || 1;
  dashboardCurrentPage = Math.max(1, Math.min(page, totalPages));

  const startIdx = (dashboardCurrentPage - 1) * SESSIONS_PER_PAGE;
  const endIdx = Math.min(startIdx + SESSIONS_PER_PAGE, total);
  const pageSessions = allDashboardSessions.slice(startIdx, endIdx);

  pageSessions.forEach(s => {
    const row = document.createElement('tr');
    row.className = 'border-b border-zinc-100 hover:bg-zinc-50 transition cursor-pointer text-xs';
    row.onclick = () => {
      window.location.href = `/session-details?session_id=${s.session_id}`;
    };

    const risk = s.current_risk;
    const score = risk ? risk.risk_score.toFixed(1) : '0.0';
    const level = risk ? risk.risk_level : 'LOW';

    let badgeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    let dotColor = 'bg-emerald-500';
    if (level === 'CRITICAL' || level === 'HIGH') {
      badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';
      dotColor = 'bg-rose-500';
    } else if (level === 'MEDIUM') {
      badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';
      dotColor = 'bg-amber-500';
    }

    const createdDate = new Date(s.created_at).toLocaleString();

    row.innerHTML = `
      <td class="py-3 px-4">
        <div class="font-mono font-bold text-zinc-950">${s.candidate_id}</div>
        <div class="text-[10px] text-zinc-500 font-mono font-semibold" title="${s.session_id}">UUID: ${s.session_id.substring(0, 8)}...</div>
      </td>
      <td class="py-3 px-4 font-mono text-zinc-700 font-medium">${s.interview_id}</td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
          ${s.status}
        </span>
      </td>
      <td class="py-3 px-4">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-bold border ${badgeColor}">
          <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
          <span>${score}</span>
          <span class="text-[10px] font-semibold opacity-75">(${level})</span>
        </span>
      </td>
      <td class="py-3 px-4 font-mono text-zinc-600">${createdDate}</td>
      <td class="py-3 px-4 text-right">
        <a href="/session-details?session_id=${s.session_id}" class="text-zinc-900 hover:text-black font-semibold text-xs flex items-center justify-end gap-1">
          <span>Investigate</span>
          <span>→</span>
        </a>
      </td>
    `;
    sessionsTableBody.appendChild(row);
  });

  // Update Pagination Controls
  if (paginationEl) {
    paginationEl.classList.remove('hidden');
    if (pageInfoEl) pageInfoEl.textContent = `Showing ${startIdx + 1} to ${endIdx} of ${total} sessions`;
    if (pageNumEl) pageNumEl.textContent = `Page ${dashboardCurrentPage} of ${totalPages}`;
    if (prevBtn) prevBtn.disabled = dashboardCurrentPage <= 1;
    if (nextBtn) nextBtn.disabled = dashboardCurrentPage >= totalPages;
  }
}

document.addEventListener('DOMContentLoaded', initDashboard);
