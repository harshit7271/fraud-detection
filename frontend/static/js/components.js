/**
 * FACEGUARD AI - Reusable UI Components (Light Enterprise Theme)
 * Sidebar navigation, top header, status widgets, and toast notifications.
 */
import { Config } from './config.js';
import { api } from './api.js';

export function renderNavigation(activePage = 'dashboard') {
  const sidebarContainer = document.getElementById('sidebarContainer');
  if (!sidebarContainer) return;

  const currentPath = window.location.pathname;
  if (!activePage || activePage === 'dashboard') {
    if (currentPath.includes('register')) activePage = 'register';
    else if (currentPath.includes('monitor')) activePage = 'monitor';
    else if (currentPath.includes('history')) activePage = 'history';
    else if (currentPath.includes('session-details')) activePage = 'details';
    else if (currentPath.includes('settings')) activePage = 'settings';
    else activePage = 'dashboard';
  }

  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>`,
      href: `/`,
    },
    {
      id: 'register',
      label: 'Candidate Registration',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>`,
      href: `/register`,
    },
    {
      id: 'monitor',
      label: 'Live Monitoring',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`,
      href: `/monitor`,
    },
    {
      id: 'history',
      label: 'Session History',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      href: `/history`,
    },
    {
      id: 'details',
      label: 'Session Analysis',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>`,
      href: `/session-details`,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
      href: `/settings`,
    },
    {
      id: 'performance',
      label: 'Performance & Benchmarks',
      icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`,
      href: `/performance-report`,
    },

  ];

  const navHtml = navItems.map(item => {
    const isActive = item.id === activePage;
    const activeClasses = isActive
      ? 'bg-indigo-50 text-indigo-700 border-indigo-200 font-semibold shadow-xs'
      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70 border-transparent';

    return `
      <a href="${item.href}" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl border text-sm transition-all duration-150 ${activeClasses}">
        <span class="${isActive ? 'text-indigo-600' : 'text-slate-400'}">${item.icon}</span>
        <span>${item.label}</span>
      </a>
    `;
  }).join('');

  sidebarContainer.innerHTML = `
    <aside class="w-64 h-screen fixed top-0 left-0 bg-white border-r border-slate-200 flex flex-col justify-between p-5 z-40 select-none shadow-xs">
      <!-- Brand & Platform Header -->
      <div class="space-y-6">
        <div class="flex items-center gap-3 px-1">
          <div class="w-9 h-9 rounded-xl p-1 bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-600/20">
            <img src="/static/assets/logo.svg" alt="FACEGUARD Logo" class="w-7 h-7" />
          </div>
          <div>
            <h1 class="text-sm font-extrabold tracking-wider text-slate-900 uppercase font-mono">FACEGUARD AI</h1>
            <p class="text-[10px] tracking-tight text-slate-500 font-medium">Face Fraud Detection Platform</p>
          </div>
        </div>

        <!-- Navigation Menu -->
        <nav class="space-y-1">
          ${navHtml}
        </nav>
      </div>

      <!-- System Status Widget -->
      <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-500 font-mono">System Status</span>
          <span id="sysStatusPulse" class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        </div>
        <div class="space-y-1.5 text-xs font-mono">
          <div class="flex justify-between items-center text-slate-600">
            <span>FastAPI Core:</span>
            <span id="apiStatusBadge" class="text-emerald-600 font-semibold">CHECKING...</span>
          </div>
          <div class="flex justify-between items-center text-slate-600">
            <span>YuNet & SFace:</span>
            <span id="modelStatusBadge" class="text-emerald-600 font-semibold">CHECKING...</span>
          </div>
          <div class="flex justify-between items-center text-slate-600">
            <span>Active Tenant:</span>
            <span id="activeTenantBadge" class="text-indigo-600 font-semibold truncate max-w-[90px]">${Config.getTenantId()}</span>
          </div>
        </div>
      </div>
    </aside>
  `;

  // Start Background Status Probe
  checkSystemStatus();
}

export function renderHeader(title = 'Dashboard', subtitle = '') {
  const headerContainer = document.getElementById('headerContainer');
  if (!headerContainer) return;

  const currentTenant = Config.getTenantId();
  const availableTenants = Config.AVAILABLE_TENANTS;

  const tenantOptions = availableTenants.map(t => `
    <option value="${t.id}" data-key="${t.key}" ${t.id === currentTenant ? 'selected' : ''}>
      ${t.name}
    </option>
  `).join('');

  headerContainer.innerHTML = `
    <header class="h-16 border-b border-slate-200 bg-white/90 backdrop-blur-xl px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      <div>
        <h2 class="text-base font-bold text-slate-900 tracking-tight">${title}</h2>
        ${subtitle ? `<p class="text-xs text-slate-500">${subtitle}</p>` : ''}
      </div>

      <div class="flex items-center gap-4">
        <!-- Enterprise Tenant Selector -->
        <div class="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-600">
          <span class="text-slate-400 font-mono text-[11px]">Tenant:</span>
          <select id="tenantSelectHeader" class="bg-transparent text-slate-800 font-medium focus:outline-none cursor-pointer">
            ${tenantOptions}
          </select>
        </div>

        <!-- Documentation Shortlink -->
        <a href="/docs" target="_blank" class="text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-slate-300 bg-white transition flex items-center gap-1.5 shadow-xs">
          <span>API Docs</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
        </a>
      </div>
    </header>
  `;

  // Attach Tenant Switch Listener
  const tenantSelect = document.getElementById('tenantSelectHeader');
  if (tenantSelect) {
    tenantSelect.addEventListener('change', (e) => {
      const selected = e.target.selectedOptions[0];
      const key = selected.dataset.key;
      Config.setTenantId(e.target.value);
      Config.setTenantKey(key);
      showToast(`Switched active tenant to ${selected.text}`, 'info');
      window.dispatchEvent(new CustomEvent('tenantChanged', { detail: { tenantId: e.target.value, tenantKey: key } }));
    });
  }
}

export async function checkSystemStatus() {
  const apiStatus = document.getElementById('apiStatusBadge');
  const modelStatus = document.getElementById('modelStatusBadge');
  const pulse = document.getElementById('sysStatusPulse');

  try {
    const health = await api.checkHealth();
    if (apiStatus) {
      apiStatus.textContent = health.status === 'healthy' ? 'ONLINE' : 'DEGRADED';
      apiStatus.className = health.status === 'healthy' ? 'text-emerald-600 font-semibold' : 'text-amber-600 font-semibold';
    }

    const ready = await api.checkReadiness();
    if (modelStatus) {
      modelStatus.textContent = ready.status === 'ready' ? 'READY (100%)' : 'OFFLINE';
      modelStatus.className = ready.status === 'ready' ? 'text-emerald-600 font-semibold' : 'text-rose-600 font-semibold';
    }

    if (pulse) {
      pulse.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
    }
  } catch (err) {
    if (apiStatus) {
      apiStatus.textContent = 'OFFLINE';
      apiStatus.className = 'text-rose-600 font-semibold';
    }
    if (modelStatus) {
      modelStatus.textContent = 'UNREACHABLE';
      modelStatus.className = 'text-rose-600 font-semibold';
    }
    if (pulse) {
      pulse.className = 'w-2 h-2 rounded-full bg-rose-500';
    }
  }
}

export function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const borderColors = {
    info: 'border-indigo-200 bg-white text-indigo-800 shadow-lg',
    success: 'border-emerald-200 bg-white text-emerald-800 shadow-lg',
    warning: 'border-amber-200 bg-white text-amber-800 shadow-lg',
    error: 'border-rose-200 bg-white text-rose-800 shadow-lg',
  };

  toast.className = `pointer-events-auto px-4 py-3 rounded-xl border text-xs font-semibold flex items-center gap-2.5 transition-all duration-300 transform translate-y-3 opacity-0 ${borderColors[type] || borderColors.info}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ'}</span>
    <span>${message}</span>
  `;

  toastContainer.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-3', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-3');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
