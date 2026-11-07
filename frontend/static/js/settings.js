/**
 * FACEGUARD AI - Settings & Client Preferences Controller
 * Configures frame sampling rates, JPEG compression, preferred camera, and API connectivity.
 */
import { Config } from './config.js';
import { api } from './api.js';
import { CameraManager } from './camera.js';
import { renderNavigation, renderHeader, showToast } from './components.js';

const camera = new CameraManager();

async function initSettings() {
  renderNavigation('settings');
  renderHeader('Platform Settings', 'Configure frame capture telemetry, camera devices, and backend connectivity.');

  // DOM Elements
  const apiUrlInput = document.getElementById('settingApiUrl');
  const samplingInput = document.getElementById('settingSampling');
  const jpegQualityInput = document.getElementById('settingJpegQuality');
  const jpegQualityVal = document.getElementById('jpegQualityDisplay');
  const cameraSelect = document.getElementById('settingCameraSelect');
  const saveBtn = document.getElementById('saveSettingsBtn');
  const resetBtn = document.getElementById('resetSettingsBtn');
  const testConnBtn = document.getElementById('testConnectionBtn');
  const connResult = document.getElementById('connectionTestResult');

  // Load current values
  apiUrlInput.value = Config.getApiBaseUrl();
  samplingInput.value = Config.getSamplingIntervalMs();
  jpegQualityInput.value = Math.round(Config.getJpegQuality() * 100);
  jpegQualityVal.textContent = `${jpegQualityInput.value}%`;

  // Populate Cameras
  const cameras = await camera.getAvailableCameras();
  if (cameras.length > 0) {
    const selectedCamId = Config.getSelectedCameraId();
    cameraSelect.innerHTML = cameras
      .map(c => `<option value="${c.deviceId}" ${c.deviceId === selectedCamId ? 'selected' : ''}>${c.label}</option>`)
      .join('');
  } else {
    cameraSelect.innerHTML = `<option value="">Default Browser Camera</option>`;
  }

  // Range Slider Feedback
  jpegQualityInput.addEventListener('input', (e) => {
    jpegQualityVal.textContent = `${e.target.value}%`;
  });

  // Test Connectivity Button
  testConnBtn.addEventListener('click', async () => {
    connResult.textContent = 'Testing backend reachability...';
    connResult.className = 'text-xs font-mono text-slate-400';
    const t0 = performance.now();
    try {
      const health = await api.checkHealth();
      const ready = await api.checkReadiness();
      const ms = Math.round(performance.now() - t0);
      connResult.textContent = `✓ Backend reachable in ${ms}ms. Status: ${health.status}, Models: ${ready.status} (YuNet & SFace ready).`;
      connResult.className = 'text-xs font-mono text-emerald-400';
      showToast('Backend connectivity verified.', 'success');
    } catch (err) {
      connResult.textContent = `✕ Connection failed: ${err.message}`;
      connResult.className = 'text-xs font-mono text-rose-400';
      showToast('Connection failed: ' + err.message, 'error');
    }
  });

  // Save Settings Button
  saveBtn.addEventListener('click', () => {
    const url = apiUrlInput.value.trim();
    const sampling = parseInt(samplingInput.value, 10);
    const quality = parseFloat(jpegQualityInput.value) / 100.0;
    const selectedCam = cameraSelect.value;

    Config.setApiBaseUrl(url);
    Config.setSamplingIntervalMs(sampling);
    Config.setJpegQuality(quality);
    Config.setSelectedCameraId(selectedCam);

    showToast('Preferences saved successfully.', 'success');
  });

  // Reset to Defaults Button
  resetBtn.addEventListener('click', () => {
    localStorage.removeItem('faceguard_api_base_url');
    localStorage.removeItem('faceguard_sampling_ms');
    localStorage.removeItem('faceguard_jpeg_quality');
    localStorage.removeItem('faceguard_camera_id');

    apiUrlInput.value = Config.getApiBaseUrl();
    samplingInput.value = Config.getSamplingIntervalMs();
    jpegQualityInput.value = Math.round(Config.getJpegQuality() * 100);
    jpegQualityVal.textContent = `${jpegQualityInput.value}%`;

    showToast('Reset settings to factory defaults.', 'info');
  });
}

document.addEventListener('DOMContentLoaded', initSettings);
