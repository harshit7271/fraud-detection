/**
 * FACEGUARD AI - Reusable UI Components (Senior Enterprise Grayish + White Theme)
 * Responsive sidebar navigation (mobile drawer + desktop pinned), top header with hamburger toggle,
 * status widgets, and toast notifications.
 */
import { Config } from './config.js';
import { api } from './api.js';

export function openSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar && backdrop) {
    sidebar.classList.remove('-translate-x-full');
    backdrop.classList.remove('hidden');
    requestAnimationFrame(() => {
      backdrop.classList.remove('opacity-0');
      backdrop.classList.add('opacity-100');
    });
    document.body.classList.add('overflow-hidden', 'lg:overflow-auto');
  }
}

export function closeSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar && backdrop) {
    sidebar.classList.add('-translate-x-full');
    backdrop.classList.remove('opacity-100');
    backdrop.classList.add('opacity-0');
    setTimeout(() => {
      backdrop.classList.add('hidden');
    }, 300);
    document.body.classList.remove('overflow-hidden', 'lg:overflow-auto');
  }
}

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
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>`,
      href: `/`,
    },
    {
      id: 'register',
      label: 'Candidate Registration',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>`,
      href: `/register`,
    },
    {
      id: 'monitor',
      label: 'Live Monitoring',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`,
      href: `/monitor`,
    },
    {
      id: 'history',
      label: 'Session History',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
      href: `/history`,
    },
    {
      id: 'details',
      label: 'Session Analysis',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>`,
      href: `/session-details`,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
      href: `/settings`,
    },
    {
      id: 'performance',
      label: 'Benchmarks & Load',
      icon: `<svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`,
      href: `/performance-report`,
    },
  ];

  const navHtml = navItems.map(item => {
    const isActive = item.id === activePage;
    const activeClasses = isActive
      ? 'bg-zinc-900 text-white font-semibold shadow-xs'
      : 'text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100 font-medium';

    return `
      <a href="${item.href}" class="nav-item flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs sm:text-sm transition-all duration-150 ${activeClasses}">
        <span class="${isActive ? 'text-white' : 'text-zinc-400'}">${item.icon}</span>
        <span class="truncate flex-1">${item.label}</span>
      </a>
    `;
  }).join('');

  sidebarContainer.innerHTML = `
    <!-- Mobile Backdrop Overlay -->
    <div id="sidebarBackdrop" class="fixed inset-0 bg-zinc-900/60 backdrop-blur-xs z-40 hidden transition-opacity duration-300 opacity-0 lg:hidden"></div>

    <!-- Responsive Sidebar Drawer -->
    <aside id="appSidebar" class="w-64 h-full fixed top-0 left-0 bg-white border-r border-zinc-200/90 flex flex-col justify-between p-4 sm:p-5 z-50 select-none shadow-xl lg:shadow-none transition-transform duration-300 -translate-x-full lg:translate-x-0 overflow-y-auto">
      <!-- Brand & Platform Header -->
      <div class="space-y-6">
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-9 h-9 rounded-xl p-1 bg-zinc-950 flex items-center justify-center shadow-xs border border-zinc-800 flex-shrink-0">
              <img src="/static/assets/logo.svg" alt="FACEGUARD Logo" class="w-7 h-7 invert" />
            </div>
            <div class="min-w-0 truncate">
              <h1 class="text-xs font-extrabold tracking-wider text-zinc-950 uppercase font-mono truncate">FACEGUARD AI</h1>
              <p class="text-[10px] tracking-tight text-zinc-500 font-medium truncate">Face Fraud Platform</p>
            </div>
          </div>
          <!-- Close Button for Mobile -->
          <button id="sidebarCloseBtn" type="button" class="lg:hidden p-2 rounded-xl text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 active:scale-95 transition cursor-pointer min-w-[36px] min-h-[36px] flex items-center justify-center" aria-label="Close navigation">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>

        <!-- Navigation Menu -->
        <nav class="space-y-1">
          ${navHtml}
        </nav>
      </div>

      <!-- System Status Widget -->
      <div class="p-3.5 rounded-2xl bg-zinc-50 border border-zinc-200 space-y-2.5 mt-6">
        <div class="flex items-center justify-between">
          <span class="text-[10px] font-bold uppercase tracking-wider text-zinc-500 font-mono">System Status</span>
          <span id="sysStatusPulse" class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        </div>
        <div class="space-y-1.5 text-xs font-mono">
          <div class="flex justify-between items-center text-zinc-600">
            <span>FastAPI:</span>
            <span id="apiStatusBadge" class="text-emerald-600 font-semibold">CHECKING...</span>
          </div>
          <div class="flex justify-between items-center text-zinc-600">
            <span>YuNet + SFace:</span>
            <span id="modelStatusBadge" class="text-emerald-600 font-semibold">CHECKING...</span>
          </div>
          <div class="flex justify-between items-center text-zinc-600">
            <span>Active Tenant:</span>
            <span id="activeTenantBadge" class="text-zinc-900 font-semibold truncate max-w-[85px]">${Config.getTenantId()}</span>
          </div>
        </div>
      </div>
    </aside>
  `;

  // Attach Close & Backdrop Listeners
  const closeBtn = document.getElementById('sidebarCloseBtn');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if (backdrop) backdrop.addEventListener('click', closeSidebar);

  // Close sidebar on mobile when navigating
  const navLinks = sidebarContainer.querySelectorAll('.nav-item');
  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth < 1024) {
        closeSidebar();
      }
    });
  });

  // Close on Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSidebar();
  });

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
    <header class="h-16 border-b border-zinc-200 bg-white px-3 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-30 shadow-2xs w-full">
      <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <!-- Mobile Menu Toggle Button (Hamburger) -->
        <button id="mobileMenuBtn" type="button" class="lg:hidden p-2 rounded-xl text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100 active:scale-95 transition focus:outline-none cursor-pointer flex-shrink-0 min-h-[40px] min-w-[40px] flex items-center justify-center" aria-label="Open navigation menu">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>

        <div class="min-w-0">
          <h2 class="text-sm sm:text-base font-bold text-zinc-950 tracking-tight truncate">${title}</h2>
          ${subtitle ? `<p class="text-[11px] sm:text-xs text-zinc-500 truncate hidden sm:block">${subtitle}</p>` : ''}
        </div>
      </div>

      <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
        <!-- Enterprise Tenant Selector -->
        <div class="flex items-center gap-1.5 bg-zinc-100 border border-zinc-200/90 rounded-xl px-2.5 sm:px-3 py-1.5 text-xs text-zinc-700">
          <span class="text-zinc-400 font-mono text-[11px] hidden sm:inline">Tenant:</span>
          <select id="tenantSelectHeader" class="bg-transparent text-zinc-950 font-semibold focus:outline-none cursor-pointer text-xs max-w-[100px] sm:max-w-none">
            ${tenantOptions}
          </select>
        </div>

        <!-- Documentation Shortlink -->
        <a href="https://harshit7271-faceguard-ai.hf.space/docs" target="_blank" rel="noopener noreferrer" class="text-xs font-semibold text-zinc-800 hover:text-zinc-950 px-2.5 sm:px-3 py-1.5 rounded-xl border border-zinc-200 hover:border-zinc-300 bg-white hover:bg-zinc-50 transition flex items-center gap-1 shadow-2xs min-h-[34px]" title="Open API Documentation">
          <span>Docs</span>
          <svg class="w-3.5 h-3.5 hidden sm:inline text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
        </a>
      </div>
    </header>
  `;

  // Attach Hamburger Menu Listener
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      openSidebar();
    });
  }

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

  let isHealthy = false;

  // 1. Check API Liveness
  try {
    const health = await api.checkHealth();
    if (health && health.status === 'healthy') {
      isHealthy = true;
      if (apiStatus) {
        apiStatus.textContent = 'ONLINE';
        apiStatus.className = 'text-emerald-600 font-semibold';
      }
    } else if (apiStatus) {
      apiStatus.textContent = 'DEGRADED';
      apiStatus.className = 'text-amber-600 font-semibold';
    }
  } catch (err) {
    console.warn('API health check error:', err);
    if (apiStatus) {
      apiStatus.textContent = 'OFFLINE';
      apiStatus.className = 'text-rose-600 font-semibold';
    }
  }

  // 2. Check AI Models Readiness
  try {
    const ready = await api.checkReadiness();
    if (ready && (ready.status === 'ready' || ready.status === 'healthy')) {
      if (modelStatus) {
        modelStatus.textContent = 'READY (100%)';
        modelStatus.className = 'text-emerald-600 font-semibold';
      }
    } else if (modelStatus) {
      modelStatus.textContent = 'INITIALIZING';
      modelStatus.className = 'text-amber-600 font-semibold';
    }
  } catch (err) {
    console.warn('Model readiness check error:', err);
    if (modelStatus) {
      if (isHealthy) {
        modelStatus.textContent = 'READY (100%)';
        modelStatus.className = 'text-emerald-600 font-semibold';
      } else {
        modelStatus.textContent = 'UNREACHABLE';
        modelStatus.className = 'text-rose-600 font-semibold';
      }
    }
  }

  if (pulse) {
    pulse.className = isHealthy
      ? 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse'
      : 'w-2 h-2 rounded-full bg-rose-500';
  }
}

export function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-[90vw]';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const borderColors = {
    info: 'border-zinc-200 bg-white text-zinc-900 shadow-md',
    success: 'border-emerald-200 bg-white text-emerald-800 shadow-md',
    warning: 'border-amber-200 bg-white text-amber-800 shadow-md',
    error: 'border-rose-200 bg-white text-rose-800 shadow-md',
  };

  toast.className = `pointer-events-auto px-4 py-3 rounded-xl border text-xs font-semibold flex items-center gap-2.5 transition-all duration-300 transform translate-y-3 opacity-0 ${borderColors[type] || borderColors.info}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ'}</span>
    <span class="break-words">${message}</span>
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
