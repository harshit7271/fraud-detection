/**
 * FACEGUARD AI - Settings & Client Preferences Controller
 * Configures frame sampling rates, JPEG compression, preferred camera, tenant auth, and API connectivity.
 */
import { Config } from './config.js?v=3.0.0';
import { api } from './api.js?v=3.0.0';
import { CameraManager } from './camera.js?v=3.0.0';
import { renderNavigation, renderHeader, showToast } from './components.js?v=3.0.0';

const camera = new CameraManager();

async function initSettings() {
  renderNavigation('settings');
  renderHeader('Platform Settings', 'Configure frame capture telemetry, camera devices, and backend connectivity.');

  // DOM Elements
  const apiUrlInput = document.getElementById('settingApiUrl');
  const tenantIdInput = document.getElementById('settingTenantId');
  const tenantKeyInput = document.getElementById('settingTenantKey');
  const samplingInput = document.getElementById('settingSampling');
  const jpegQualityInput = document.getElementById('settingJpegQuality');
  const jpegQualityVal = document.getElementById('jpegQualityDisplay');
  const cameraSelect = document.getElementById('settingCameraSelect');
  const saveBtn = document.getElementById('saveSettingsBtn');
  const resetBtn = document.getElementById('resetSettingsBtn');
  const testConnBtn = document.getElementById('testConnectionBtn');
  const connResult = document.getElementById('connectionTestResult');

  // Load current values
  if (apiUrlInput) apiUrlInput.value = Config.getApiBaseUrl();
  if (tenantIdInput) tenantIdInput.value = Config.getTenantId();
  if (tenantKeyInput) tenantKeyInput.value = Config.getTenantKey();
  if (samplingInput) samplingInput.value = Config.getSamplingIntervalMs();
  if (jpegQualityInput) {
    jpegQualityInput.value = Math.round(Config.getJpegQuality() * 100);
    if (jpegQualityVal) jpegQualityVal.textContent = `${jpegQualityInput.value}%`;
  }

  // Populate Cameras
  if (cameraSelect) {
    const cameras = await camera.getAvailableCameras();
    if (cameras.length > 0) {
      const selectedCamId = Config.getSelectedCameraId();
      cameraSelect.innerHTML = cameras
        .map(c => `<option value="${c.deviceId}" ${c.deviceId === selectedCamId ? 'selected' : ''}>${c.label}</option>`)
        .join('');
    } else {
      cameraSelect.innerHTML = `<option value="">Default Browser Camera</option>`;
    }
  }

  // Range Slider Feedback
  if (jpegQualityInput && jpegQualityVal) {
    jpegQualityInput.addEventListener('input', (e) => {
      jpegQualityVal.textContent = `${e.target.value}%`;
    });
  }

  // Test Connectivity Button
  if (testConnBtn && connResult) {
    testConnBtn.addEventListener('click', async () => {
      connResult.textContent = 'Testing backend reachability...';
      connResult.className = 'text-xs font-mono text-zinc-500';
      const t0 = performance.now();
      try {
        const health = await api.checkHealth();
        const ready = await api.checkReadiness();
        const ms = Math.round(performance.now() - t0);
        connResult.textContent = `✓ Backend reachable in ${ms}ms. Status: ${health.status}, Models: ${ready.status} (YuNet & SFace ready).`;
        connResult.className = 'text-xs font-mono text-emerald-600 font-semibold';
        showToast('Backend connectivity verified.', 'success');
      } catch (err) {
        connResult.textContent = `✕ Connection failed: ${err.message}`;
        connResult.className = 'text-xs font-mono text-rose-600 font-semibold';
        showToast('Connection failed: ' + err.message, 'error');
      }
    });
  }

  // Save Settings Button
  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      if (apiUrlInput) Config.setApiBaseUrl(apiUrlInput.value.trim());
      if (tenantIdInput) Config.setTenantId(tenantIdInput.value.trim());
      if (tenantKeyInput) Config.setTenantKey(tenantKeyInput.value.trim());
      if (samplingInput) Config.setSamplingIntervalMs(parseInt(samplingInput.value, 10));
      if (jpegQualityInput) Config.setJpegQuality(parseFloat(jpegQualityInput.value) / 100.0);
      if (cameraSelect) Config.setSelectedCameraId(cameraSelect.value);

      showToast('Preferences saved successfully.', 'success');
    });
  }

  // Reset to Defaults Button
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      localStorage.removeItem('faceguard_api_base_url');
      localStorage.removeItem('faceguard_tenant_id');
      localStorage.removeItem('faceguard_tenant_key');
      localStorage.removeItem('faceguard_sampling_ms');
      localStorage.removeItem('faceguard_jpeg_quality');
      localStorage.removeItem('faceguard_camera_id');

      if (apiUrlInput) apiUrlInput.value = Config.getApiBaseUrl();
      if (tenantIdInput) tenantIdInput.value = Config.getTenantId();
      if (tenantKeyInput) tenantKeyInput.value = Config.getTenantKey();
      if (samplingInput) samplingInput.value = Config.getSamplingIntervalMs();
      if (jpegQualityInput) {
        jpegQualityInput.value = Math.round(Config.getJpegQuality() * 100);
        if (jpegQualityVal) jpegQualityVal.textContent = `${jpegQualityInput.value}%`;
      }

      showToast('Reset settings to factory defaults.', 'info');
    });
  }
}

document.addEventListener('DOMContentLoaded', initSettings);
