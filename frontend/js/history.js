/**
 * FACEGUARD AI - Session History Controller
 * Searchable, filterable table for audit trail and compliance verification.
 */
import { api } from './api.js?v=3.0.0';
import { Config } from './config.js?v=3.0.0';
import { renderNavigation, renderHeader, showToast } from './components.js?v=3.0.0';

let allSessions = [];
let currentFilteredSessions = [];
let historyCurrentPage = 1;
const HISTORY_PAGE_SIZE = 10;

function formatTenantDisplay(tenantId) {
  if (!tenantId) return 'Enterprise A';
  const lower = String(tenantId).toLowerCase();
  if (lower.includes('alorica') || lower.includes('enterprise-a')) return 'Enterprise A';
  if (lower.includes('sagility') || lower.includes('enterprise-b')) return 'Enterprise B';
  if (lower.includes('mastek') || lower.includes('enterprise-c')) return 'Enterprise C';
  return tenantId;
}

async function initHistory() {
  renderNavigation('history');
  renderHeader('Session History', 'Audit log of all registered candidates, proctoring sessions, and risk assessments.');

  // Attach Pagination Listeners
  const prevBtn = document.getElementById('historyPrevBtn');
  const nextBtn = document.getElementById('historyNextBtn');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (historyCurrentPage > 1) {
        historyCurrentPage--;
        renderHistoryPage(historyCurrentPage);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const maxPages = Math.ceil(currentFilteredSessions.length / HISTORY_PAGE_SIZE) || 1;
      if (historyCurrentPage < maxPages) {
        historyCurrentPage++;
        renderHistoryPage(historyCurrentPage);
      }
    });
  }

  await loadSessions();

  // Search input
  const searchInput = document.getElementById('sessionSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', applyFilters);
  }

  // Filter dropdowns
  const riskFilter = document.getElementById('riskFilterSelect');
  const statusFilter = document.getElementById('statusFilterSelect');

  if (riskFilter) riskFilter.addEventListener('change', applyFilters);
  if (statusFilter) statusFilter.addEventListener('change', applyFilters);

  // Tenant change listener
  window.addEventListener('tenantChanged', () => {
    loadSessions();
  });
}

async function loadSessions() {
  const countBadge = document.getElementById('totalSessionsBadge');
  const emptyEl = document.getElementById('historyEmptyState');

  try {
    const data = await api.get('/fraud/sessions');
    allSessions = Array.isArray(data) ? data : [];
    currentFilteredSessions = allSessions;

    if (countBadge) {
      countBadge.textContent = `${allSessions.length} Session${allSessions.length === 1 ? '' : 's'}`;
    }

    historyCurrentPage = 1;
    renderHistoryPage(historyCurrentPage);
  } catch (err) {
    console.error('Failed to load session history:', err);
    const tableBody = document.getElementById('historyTableBody');
    if (tableBody) tableBody.innerHTML = '';
    if (emptyEl) {
      emptyEl.textContent = `Error loading sessions: ${err.message}`;
      emptyEl.classList.remove('hidden');
    }
  }
}

function applyFilters() {
  const query = document.getElementById('sessionSearchInput')?.value.toLowerCase().trim() || '';
  const selectedRisk = document.getElementById('riskFilterSelect')?.value || 'ALL';
  const selectedStatus = document.getElementById('statusFilterSelect')?.value || 'ALL';

  currentFilteredSessions = allSessions.filter(s => {
    // Search match
    const matchSearch =
      !query ||
      s.session_id.toLowerCase().includes(query) ||
      s.candidate_id.toLowerCase().includes(query) ||
      s.interview_id.toLowerCase().includes(query);

    // Risk match
    const riskLevel = (s.current_risk && s.current_risk.risk_level) || 'LOW';
    const matchRisk = selectedRisk === 'ALL' || riskLevel === selectedRisk;

    // Status match
    const matchStatus = selectedStatus === 'ALL' || s.status === selectedStatus;

    return matchSearch && matchRisk && matchStatus;
  });

  historyCurrentPage = 1;
  renderHistoryPage(historyCurrentPage);
}

function renderHistoryPage(page) {
  const tableBody = document.getElementById('historyTableBody');
  const emptyEl = document.getElementById('historyEmptyState');
  const paginationEl = document.getElementById('historyPagination');
  const pageInfoEl = document.getElementById('historyPageInfo');
  const pageNumEl = document.getElementById('historyPageNumber');
  const prevBtn = document.getElementById('historyPrevBtn');
  const nextBtn = document.getElementById('historyNextBtn');

  if (!tableBody) return;
  tableBody.innerHTML = '';

  const total = currentFilteredSessions.length;
  if (total === 0) {
    if (emptyEl) emptyEl.classList.remove('hidden');
    if (paginationEl) paginationEl.classList.add('hidden');
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');

  const totalPages = Math.ceil(total / HISTORY_PAGE_SIZE) || 1;
  historyCurrentPage = Math.max(1, Math.min(page, totalPages));

  const startIdx = (historyCurrentPage - 1) * HISTORY_PAGE_SIZE;
  const endIdx = Math.min(startIdx + HISTORY_PAGE_SIZE, total);
  const pageSessions = currentFilteredSessions.slice(startIdx, endIdx);

  pageSessions.forEach(s => {
    const row = document.createElement('tr');
    row.className = 'border-b border-zinc-100 hover:bg-zinc-50 transition cursor-pointer text-xs font-mono';
    row.onclick = () => {
      window.location.href = `/session-details?session_id=${s.session_id}`;
    };

    const risk = s.current_risk;
    const score = risk ? risk.risk_score.toFixed(1) : '0.0';
    const level = risk ? risk.risk_level : 'LOW';
    const eventsCount = s.total_events ?? (risk ? risk.total_events : 0) ?? 0;

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
      <td class="py-3 px-4 font-mono font-semibold text-zinc-600 hover:text-zinc-900 truncate max-w-[130px]" title="${s.session_id}">
        ${s.session_id.substring(0, 8)}...
      </td>
      <td class="py-3 px-4 text-zinc-950 font-bold">${s.candidate_id}</td>
      <td class="py-3 px-4 text-zinc-700 font-medium">${s.interview_id}</td>
      <td class="py-3 px-4 text-zinc-800 font-medium">${formatTenantDisplay(s.tenant_id)}</td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
          ${s.status}
        </span>
      </td>
      <td class="py-3 px-4">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-bold border ${badgeColor}">
          <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
          <span>${score}</span>
        </span>
      </td>
      <td class="py-3 px-4 font-bold ${level === 'CRITICAL' || level === 'HIGH' ? 'text-rose-700' : level === 'MEDIUM' ? 'text-amber-700' : 'text-emerald-700'}">
        ${level}
      </td>
      <td class="py-3 px-4 text-zinc-900 font-bold">${eventsCount}</td>
      <td class="py-3 px-4 text-zinc-600">${createdDate}</td>
      <td class="py-3 px-4 text-right">
        <a href="/session-details?session_id=${s.session_id}" class="text-zinc-900 hover:text-black font-semibold text-xs flex items-center justify-end gap-1">
          <span>Details</span>
          <span>→</span>
        </a>
      </td>
    `;
    tableBody.appendChild(row);
  });

  // Update Pagination Controls
  if (paginationEl) {
    paginationEl.classList.remove('hidden');
    if (pageInfoEl) pageInfoEl.textContent = `Showing ${startIdx + 1} to ${endIdx} of ${total} sessions`;
    if (pageNumEl) pageNumEl.textContent = `Page ${historyCurrentPage} of ${totalPages}`;
    if (prevBtn) prevBtn.disabled = historyCurrentPage <= 1;
    if (nextBtn) nextBtn.disabled = historyCurrentPage >= totalPages;
  }
}

document.addEventListener('DOMContentLoaded', initHistory);
