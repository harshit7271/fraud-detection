/**
 * FACEGUARD AI - Client Configuration & Defaults
 * Non-sensitive client runtime preferences.
 */
export const Config = {
  // Base URL for the FastAPI Backend API
  getApiBaseUrl() {
    return localStorage.getItem('faceguard_api_base_url') || `${window.location.origin}/api/v1`;
  },
  setApiBaseUrl(url) {
    if (url) localStorage.setItem('faceguard_api_base_url', url.trim());
    else localStorage.removeItem('faceguard_api_base_url');
  },

  // Active Tenant Authentication Key
  getTenantKey() {
    return localStorage.getItem('faceguard_tenant_key') || 'alorica-live-key-2026';
  },
  setTenantKey(key) {
    if (key) localStorage.setItem('faceguard_tenant_key', key.trim());
    else localStorage.removeItem('faceguard_tenant_key');
  },

  // Active Tenant ID
  getTenantId() {
    return localStorage.getItem('faceguard_tenant_id') || 'alorica-test';
  },
  setTenantId(id) {
    if (id) localStorage.setItem('faceguard_tenant_id', id.trim());
    else localStorage.removeItem('faceguard_tenant_id');
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
    { id: 'alorica-test', name: 'Alorica Global', key: 'alorica-live-key-2026' },
    { id: 'sagility-test', name: 'Sagility Health', key: 'sagility-live-key-2026' },
    { id: 'mastek-test', name: 'Mastek Enterprise', key: 'mastek-live-key-2026' },
  ]
};
