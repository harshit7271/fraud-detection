/**
 * FACEGUARD AI - Client Configuration & Defaults
 * Non-sensitive client runtime preferences.
 */
export const Config = {
  // Base URL for the FastAPI Backend API
  getApiBaseUrl() {
    const stored = localStorage.getItem('faceguard_api_base_url');
    if (stored) {
      try {
        const parsed = new URL(stored);
        // If current window is localhost/127.0.0.1, and stored points to remote HF space, prefer local
        if ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') &&
            parsed.hostname !== 'localhost' && parsed.hostname !== '127.0.0.1') {
          return `${window.location.origin}/api/v1`;
        }
        return stored.replace(/\/+$/, '');
      } catch (e) {
        return `${window.location.origin}/api/v1`;
      }
    }
    return `${window.location.origin}/api/v1`;
  },
  setApiBaseUrl(url) {
    if (url) localStorage.setItem('faceguard_api_base_url', url.trim());
    else localStorage.removeItem('faceguard_api_base_url');
  },

  // Active Tenant Authentication Key
  getTenantKey() {
    const key = localStorage.getItem('faceguard_tenant_key');
    if (!key || key === 'alorica-test' || key === 'default' || key.trim() === '') {
      return 'alorica-live-key-2026';
    }
    return key.trim();
  },
  setTenantKey(key) {
    if (key) localStorage.setItem('faceguard_tenant_key', key.trim());
    else localStorage.removeItem('faceguard_tenant_key');
  },

  // Active Tenant ID / Slug
  getTenantId() {
    const id = localStorage.getItem('faceguard_tenant_id');
    if (!id || id === 'alorica-test') return 'alorica';
    if (id === 'sagility-test') return 'sagility';
    if (id === 'mastek-test') return 'mastek';
    return id.trim();
  },
  setTenantId(id) {
    if (id) {
      const sanitized = id === 'alorica-test' ? 'alorica' :
                        id === 'sagility-test' ? 'sagility' :
                        id === 'mastek-test' ? 'mastek' : id.trim();
      localStorage.setItem('faceguard_tenant_id', sanitized);
    } else {
      localStorage.removeItem('faceguard_tenant_id');
    }
  },

  // Frame Sampling Cadence (ms)
  getSamplingIntervalMs() {
    const val = parseInt(localStorage.getItem('faceguard_sampling_ms'), 10);
    return isNaN(val) ? 800 : Math.max(300, Math.min(3000, val));
  },
  setSamplingIntervalMs(ms) {
    localStorage.setItem('faceguard_sampling_ms', String(ms));
  },

  // Captured JPEG compression quality (0.1 to 1.0)
  getJpegQuality() {
    const val = parseFloat(localStorage.getItem('faceguard_jpeg_quality'));
    return isNaN(val) ? 0.85 : Math.max(0.5, Math.min(1.0, val));
  },
  setJpegQuality(q) {
    localStorage.setItem('faceguard_jpeg_quality', String(q));
  },

  // Selected Camera Device ID
  getSelectedCameraId() {
    return localStorage.getItem('faceguard_camera_id') || '';
  },
  setSelectedCameraId(id) {
    if (id) localStorage.setItem('faceguard_camera_id', id);
    else localStorage.removeItem('faceguard_camera_id');
  },

  // Pre-configured Enterprise Tenants
  AVAILABLE_TENANTS: [
    { id: 'alorica', name: 'Alorica Global', key: 'alorica-live-key-2026' },
    { id: 'sagility', name: 'Sagility Health', key: 'sagility-live-key-2026' },
    { id: 'mastek', name: 'Mastek Enterprise', key: 'mastek-live-key-2026' },
  ]
};
