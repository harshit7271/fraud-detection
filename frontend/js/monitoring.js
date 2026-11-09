/**
 * FACEGUARD AI - Live Interview Proctoring Controller
 * Real-time webcam frame batching, non-overlapping fetch loop, HUD overlay, mismatch counters, and fraud warning banners.
 */
import { api } from './api.js';
import { CameraManager } from './camera.js';
import { Config } from './config.js';
import { renderNavigation, renderHeader, showToast } from './components.js';

const camera = new CameraManager();

let activeSessionId = null;
let activeCandidateId = 'Unknown Candidate';
let isMonitoring = false;
let isProcessingBatch = false;
let monitorIntervalId = null;

// Telemetry & Violation Counters
let mismatchCounter = 0;
let absenceCounter = 0;
let multiFaceCounter = 0;
let occlusionCounter = 0;
let totalFramesProcessed = 0;
let fpsFramesCount = 0;
let lastFpsTimestamp = Date.now();
const sessionEventsHistory = [];

async function initMonitoring() {
  renderNavigation('monitor');
  renderHeader('Live Interview Monitoring', 'Real-time proctoring surveillance, automated multi-frame tracking, and fraud anomaly detection.');

  // Parse session_id from URL query params
  const urlParams = new URLSearchParams(window.location.search);
  const paramSessionId = urlParams.get('session_id');
  const paramCandidateId = urlParams.get('candidate_id');

  if (paramSessionId) {
    activeSessionId = paramSessionId;
    if (paramCandidateId) activeCandidateId = decodeURIComponent(paramCandidateId);
    updateSessionHeaderDisplay();
  } else {
    // If no session passed in URL, attempt to select latest registered session
    await loadLatestSession();
  }

  // DOM Elements
  const videoEl = document.getElementById('monitorVideo');
  const canvasEl = document.getElementById('monitorCanvas');
  const toggleCamBtn = document.getElementById('toggleCameraBtn');
  const toggleProctorBtn = document.getElementById('toggleProctorBtn');
  const manualSnapBtn = document.getElementById('manualSnapBtn');
  const cameraSelect = document.getElementById('monitorCameraSelect');
  const viewChartBtn = document.getElementById('viewChartBtn');
  const concludeBtn = document.getElementById('concludeSessionBtn');

  // Start Camera
  try {
    const res = await camera.start(videoEl, Config.getSelectedCameraId());
    document.getElementById('videoResolutionText').textContent = `${res.width}x${res.height}`;
    document.getElementById('cameraStatusText').textContent = 'ACTIVE';
    document.getElementById('cameraStatusPill').className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
    populateCameraDevices(cameraSelect);
  } catch (err) {
    showToast(err.message, 'error');
    document.getElementById('cameraStatusText').textContent = 'OFFLINE';
    document.getElementById('cameraStatusPill').className = 'w-2 h-2 rounded-full bg-rose-500';
  }

  // Camera Toggle
  if (toggleCamBtn) {
    toggleCamBtn.addEventListener('click', async () => {
      if (camera.stream) {
        camera.stop();
        toggleCamBtn.innerHTML = `<span>📹</span><span>Start Camera</span>`;
        toggleCamBtn.className = 'bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2 px-3.5 rounded-xl transition';
        document.getElementById('cameraStatusText').textContent = 'STOPPED';
        document.getElementById('cameraStatusPill').className = 'w-2 h-2 rounded-full bg-slate-500';
        pauseProctoring();
      } else {
        try {
          await camera.start(videoEl, Config.getSelectedCameraId());
          toggleCamBtn.innerHTML = `<span>⏹</span><span>Stop Camera</span>`;
          toggleCamBtn.className = 'bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold py-2 px-3.5 rounded-xl border border-slate-700 transition';
          document.getElementById('cameraStatusText').textContent = 'ACTIVE';
          document.getElementById('cameraStatusPill').className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  }

  // Proctoring Loop Toggle
  if (toggleProctorBtn) {
    toggleProctorBtn.addEventListener('click', () => {
      if (isMonitoring) {
        pauseProctoring();
      } else {
        startProctoring();
      }
    });
  }

  // Manual Frame Capture
  if (manualSnapBtn) {
    manualSnapBtn.addEventListener('click', async () => {
      await processSingleFrameBatch(true);
    });
  }

  // Camera Source Switch
  if (cameraSelect) {
    cameraSelect.addEventListener('change', async (e) => {
      const deviceId = e.target.value;
      if (deviceId) {
        try {
          await camera.start(videoEl, deviceId);
          Config.setSelectedCameraId(deviceId);
          showToast('Switched camera source.', 'info');
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  }

  // Mobile Camera Flip (Front / Back)
  const flipCameraBtn = document.getElementById('flipCameraBtn');
  if (flipCameraBtn) {
    flipCameraBtn.addEventListener('click', async () => {
      try {
        const res = await camera.flipCamera(videoEl);
        document.getElementById('videoResolutionText').textContent = `${res.width}x${res.height}`;
        showToast(`Switched to ${camera.facingMode === 'user' ? 'Front (Selfie)' : 'Back'} Camera`, 'info');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Mobile Orientation & Window Resize: keep HUD canvas sized accurately
  window.addEventListener('resize', () => {
    if (camera.videoElement && canvasEl) {
      canvasEl.width = camera.videoElement.videoWidth || 640;
      canvasEl.height = camera.videoElement.videoHeight || 480;
    }
  });

  // Matplotlib Analytics Modal Handler
  if (viewChartBtn) {
    viewChartBtn.addEventListener('click', () => {
      openAnalyticsChartModal();
    });
  }

  // Conclude Session Button
  if (concludeBtn) {
    concludeBtn.addEventListener('click', () => {
      pauseProctoring();
      camera.stop();
      if (activeSessionId) {
        window.location.href = `/session-details?session_id=${activeSessionId}`;
      } else {
        window.location.href = '/history';
      }
    });
  }

  // Automatically start monitoring if session ID is valid
  if (activeSessionId) {
    startProctoring();
  }

  // Clean up on page unload
  window.addEventListener('beforeunload', () => {
    pauseProctoring();
    camera.stop();
  });
}

async function loadLatestSession() {
  try {
    const sessions = await api.get('/fraud/sessions');
    if (Array.isArray(sessions) && sessions.length > 0) {
      const latest = sessions[0];
      activeSessionId = latest.session_id;
      activeCandidateId = latest.candidate_id;
      updateSessionHeaderDisplay();
      showToast(`Attached to recent session: ${activeCandidateId}`, 'info');
    } else {
      document.getElementById('sessionStatusText').textContent = 'NO ACTIVE SESSION (Please Register Candidate)';
      document.getElementById('sessionStatusText').className = 'text-xs text-amber-400 font-mono';
    }
  } catch (err) {
    console.warn('Could not load existing sessions:', err);
  }
}

function updateSessionHeaderDisplay() {
  const sessionSpan = document.getElementById('activeSessionIdHeader');
  const candSpan = document.getElementById('activeCandidateHeader');
  const statusSpan = document.getElementById('sessionStatusText');

  if (sessionSpan) sessionSpan.textContent = activeSessionId || '—';
  if (candSpan) candSpan.textContent = activeCandidateId;
  if (statusSpan) {
    statusSpan.textContent = isMonitoring ? 'PROCTORING ACTIVE' : 'READY TO PROCTOR';
    statusSpan.className = isMonitoring ? 'text-xs text-emerald-400 font-mono font-bold' : 'text-xs text-indigo-400 font-mono';
  }
}

async function populateCameraDevices(selectEl) {
  if (!selectEl) return;
  const cameras = await camera.getAvailableCameras();
  if (cameras.length > 1) {
    selectEl.innerHTML = cameras.map(c => `<option value="${c.deviceId}">${c.label}</option>`).join('');
    selectEl.classList.remove('hidden');
  }
}

function startProctoring() {
  if (!activeSessionId) {
    showToast('Cannot start proctoring without an active registered session.', 'warning');
    return;
  }
  isMonitoring = true;
  const toggleBtn = document.getElementById('toggleProctorBtn');
  if (toggleBtn) {
    toggleBtn.innerHTML = `<span>⏸</span><span>Pause Proctoring</span>`;
    toggleBtn.className = 'bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold py-2 px-3.5 rounded-xl transition';
  }
  updateSessionHeaderDisplay();

  const intervalMs = Config.getSamplingIntervalMs();
  if (monitorIntervalId) clearInterval(monitorIntervalId);

  monitorIntervalId = setInterval(async () => {
    if (!isProcessingBatch && isMonitoring) {
      await processSingleFrameBatch();
    }
  }, intervalMs);
}

function pauseProctoring() {
  isMonitoring = false;
  if (monitorIntervalId) {
    clearInterval(monitorIntervalId);
    monitorIntervalId = null;
  }
  const toggleBtn = document.getElementById('toggleProctorBtn');
  if (toggleBtn) {
    toggleBtn.innerHTML = `<span>▶</span><span>Resume Proctoring</span>`;
    toggleBtn.className = 'bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2 px-3.5 rounded-xl transition';
  }
  updateSessionHeaderDisplay();
}

/**
 * Captures video frame and calls POST /fraud/sessions/{session_id}/analyze
 */
async function processSingleFrameBatch(manual = false) {
  if (!activeSessionId || !camera.stream) return;

  isProcessingBatch = true;
  const t0 = performance.now();

  try {
    const jpegQuality = Config.getJpegQuality();
    const frame = await camera.captureFrame(jpegQuality);

    const nowMs = Date.now();
    const frameId = `f_${nowMs}`;
    const payload = {
      batch_id: `batch_${nowMs}`,
      frames: [
        {
          frame_id: frameId,
          timestamp_ms: nowMs,
          image_base64: frame.base64,
        },
      ],
      client_metadata: {
        sampling_ms: Config.getSamplingIntervalMs(),
        manual_trigger: manual,
      },
    };

    const result = await api.post(`/fraud/sessions/${activeSessionId}/analyze`, payload);
    const roundtrip = Math.round(performance.now() - t0);

    // Render HUD bounding boxes and update diagnostic cards
    renderAnalysisHUD(result, frame.width, frame.height);
    updateDiagnosticsAndCounters(result, roundtrip);

    totalFramesProcessed++;
    fpsFramesCount++;
    if (Date.now() - lastFpsTimestamp >= 1000) {
      document.getElementById('liveFpsText').textContent = fpsFramesCount;
      fpsFramesCount = 0;
      lastFpsTimestamp = Date.now();
    }
  } catch (err) {
    console.error('Frame batch analysis error:', err);
    document.getElementById('processingStatusText').textContent = 'ERROR';
    document.getElementById('processingStatusText').className = 'text-rose-400 font-bold';
  } finally {
    isProcessingBatch = false;
  }
}

/**
 * Draws AI bounding boxes, facial landmarks, and status labels onto HTML5 HUD Canvas
 */
function renderAnalysisHUD(data, sourceW, sourceH) {
  const canvas = document.getElementById('monitorCanvas');
  const ctx = canvas.getContext('2d');
  const video = document.getElementById('monitorVideo');

  canvas.width = video.videoWidth || sourceW || 640;
  canvas.height = video.videoHeight || sourceH || 480;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const frameResult = data.frame_results && data.frame_results[0];
  if (!frameResult) return;

  const sx = canvas.width / sourceW;
  const sy = canvas.height / sourceH;

  // Render Face Detections
  if (frameResult.detections && frameResult.detections.length > 0) {
    frameResult.detections.forEach(det => {
      const bbox = det.bbox;
      const idMatch = det.identity_match;

      let color = '#10b981'; // Emerald for MATCH
      let label = 'VERIFIED MATCH';

      if (frameResult.quality && frameResult.quality.is_occluded) {
        color = '#f59e0b';
        label = 'OCCLUSION DETECTED';
      } else if (!frameResult.quality.is_acceptable) {
        color = '#f59e0b';
        label = 'POOR QUALITY';
      } else if (!idMatch || idMatch.status === 'MISMATCH') {
        color = '#f43f5e';
        label = 'IDENTITY MISMATCH';
      } else if (idMatch.status === 'UNCERTAIN') {
        color = '#f59e0b';
        label = 'UNCERTAIN IDENTITY';
      }

      const x = bbox.x * sx;
      const y = bbox.y * sy;
      const w = bbox.width * sx;
      const h = bbox.height * sy;

      // Modern Corner Brackets
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(x, y, w, h);

      // Accent marks on corners
      ctx.fillStyle = color;
      ctx.fillRect(x - 2, y - 2, 14, 3.5);
      ctx.fillRect(x - 2, y - 2, 3.5, 14);
      ctx.fillRect(x + w - 12, y - 2, 14, 3.5);
      ctx.fillRect(x + w - 1.5, y - 2, 3.5, 14);

      // Top label badge
      ctx.fillStyle = 'rgba(7, 11, 20, 0.85)';
      const tagWidth = Math.max(160, w * 0.75);
      ctx.fillRect(x, Math.max(0, y - 26), tagWidth, 24);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.strokeRect(x, Math.max(0, y - 26), tagWidth, 24);

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px Inter, sans-serif';
      const simText = idMatch ? `${(idMatch.similarity_score * 100).toFixed(1)}%` : 'N/A';
      ctx.fillText(`${label} (${simText})`, x + 8, Math.max(17, y - 9));
    });
  }
}

/**
 * Updates Real-Time Metric Telemetry, Counter Widgets, and High-Visibility Alert Banners
 */
function updateDiagnosticsAndCounters(data, latencyMs) {
  const frameResult = data.frame_results && data.frame_results[0];
  if (!frameResult) return;

  const facesDetected = frameResult.faces_detected;
  const quality = frameResult.quality;
  const firstDet = frameResult.detections && frameResult.detections[0];
  const idMatch = firstDet ? firstDet.identity_match : null;

  // 1. Telemetry Cards Updates
  document.getElementById('metricFaceCount').textContent = `${facesDetected} Face${facesDetected === 1 ? '' : 's'}`;
  document.getElementById('metricFaceCount').className = facesDetected === 1 ? 'font-mono text-xl font-bold text-emerald-400' : 'font-mono text-xl font-bold text-rose-400';

  // Identity Match Status
  const matchStatusEl = document.getElementById('metricIdentityStatus');
  const simText = idMatch ? `${(idMatch.similarity_score * 100).toFixed(1)}%` : '0.0%';
  if (facesDetected === 0) {
    matchStatusEl.textContent = 'FACE ABSENT';
    matchStatusEl.className = 'font-mono text-base font-bold text-rose-400';
  } else if (quality && quality.is_occluded) {
    matchStatusEl.textContent = 'OCCLUDED (Hands/Object)';
    matchStatusEl.className = 'font-mono text-base font-bold text-amber-400';
  } else if (!idMatch || idMatch.status === 'MISMATCH') {
    matchStatusEl.textContent = `MISMATCH (${simText})`;
    matchStatusEl.className = 'font-mono text-base font-bold text-rose-400';
    mismatchCounter++;
  } else if (idMatch.status === 'UNCERTAIN') {
    matchStatusEl.textContent = `UNCERTAIN (${simText})`;
    matchStatusEl.className = 'font-mono text-base font-bold text-amber-400';
  } else {
    matchStatusEl.textContent = `MATCH (${simText})`;
    matchStatusEl.className = 'font-mono text-base font-bold text-emerald-400';
  }

  // Quality & Occlusion
  const qualityEl = document.getElementById('metricQualityStatus');
  if (quality.is_acceptable) {
    qualityEl.textContent = `PASS (Sharpness: ${Math.round(quality.blur_score)})`;
    qualityEl.className = 'font-mono text-xs font-semibold text-emerald-400';
  } else {
    qualityEl.textContent = quality.quality_issues[0] || 'POOR QUALITY';
    qualityEl.className = 'font-mono text-xs font-semibold text-rose-400';
  }

  // Liveness / Presentation Attack Status
  const livenessEl = document.getElementById('metricLivenessStatus');
  if (frameResult.liveness) {
    const liveness = frameResult.liveness;
    if (liveness.status === 'LIVE') {
      const confText = liveness.confidence ? ` (${Math.round(liveness.confidence * 100)}%)` : '';
      livenessEl.textContent = `LIVE${confText}`;
      livenessEl.className = 'font-mono text-xs font-semibold text-emerald-600';
    } else if (liveness.status === 'SPOOF') {
      livenessEl.textContent = 'SPOOF DETECTED';
      livenessEl.className = 'font-mono text-xs font-bold text-rose-600 animate-pulse';
    } else if (liveness.status === 'UNCERTAIN') {
      livenessEl.textContent = 'UNCERTAIN';
      livenessEl.className = 'font-mono text-xs font-semibold text-amber-600';
    } else {
      livenessEl.textContent = 'NOT_EVALUATED';
      livenessEl.className = 'font-mono text-xs font-semibold text-slate-400';
    }
  } else {
    livenessEl.textContent = 'NOT_EVALUATED';
    livenessEl.className = 'font-mono text-xs font-semibold text-slate-400';
  }

  // Processing & Latency
  document.getElementById('metricLatencyText').textContent = `${latencyMs}ms`;
  document.getElementById('metricTimestampText').textContent = new Date(frameResult.timestamp_ms).toLocaleTimeString();
  document.getElementById('processingStatusText').textContent = 'ACTIVE';
  document.getElementById('processingStatusText').className = 'text-emerald-400 font-bold';

  // 2. Incremental Violations Counter Cards
  if (facesDetected === 0) absenceCounter++;
  if (facesDetected > 1) multiFaceCounter++;
  if (quality.is_occluded) occlusionCounter++;

  document.getElementById('counterMismatchVal').textContent = mismatchCounter;
  document.getElementById('counterAbsenceVal').textContent = absenceCounter;
  document.getElementById('counterMultiFaceVal').textContent = multiFaceCounter;
  document.getElementById('counterOcclusionVal').textContent = occlusionCounter;

  // 3. High-Visibility Animated Warning Banner
  const alertBanner = document.getElementById('proctorAlertBanner');
  const alertText = document.getElementById('alertBannerText');

  const activeWarnings = [];
  if (facesDetected === 0) {
    activeWarnings.push('⚠️ WARNING: NO FACE DETECTED IN FRAME (Face Absent)');
  } else if (facesDetected > 1) {
    activeWarnings.push(`🚨 CRITICAL: ${facesDetected} FACES DETECTED (Multiple Persons Warning)`);
  }

  if (quality.is_occluded) {
    activeWarnings.push('⚠️ OCCLUSION DETECTED: Hands or objects covering facial landmarks');
  }

  if (idMatch && idMatch.status === 'MISMATCH') {
    activeWarnings.push('🚨 IDENTITY MISMATCH: Candidate does not match registered baseline!');
  }

  if (activeWarnings.length > 0) {
    alertBanner.classList.remove('hidden');
    alertText.textContent = activeWarnings.join('  |  ');
    alertBanner.className = activeWarnings.some(w => w.includes('CRITICAL') || w.includes('MISMATCH'))
      ? 'p-3 rounded-xl bg-rose-950/90 border border-rose-500 text-rose-200 text-xs font-mono font-bold flex items-center justify-between shadow-2xl animate-pulse'
      : 'p-3 rounded-xl bg-amber-950/90 border border-amber-500 text-amber-200 text-xs font-mono font-bold flex items-center justify-between shadow-2xl';
  } else {
    alertBanner.classList.add('hidden');
  }

  // 4. Update Risk Score Gauge
  if (data.current_risk) {
    const r = data.current_risk;
    const score = r.risk_score || 0;
    document.getElementById('riskScoreNumber').textContent = score.toFixed(1);
    document.getElementById('riskScoreBar').style.width = `${Math.min(100, score)}%`;

    const levelBadge = document.getElementById('riskLevelBadge');
    levelBadge.textContent = r.risk_level || 'LOW';

    if (r.risk_level === 'CRITICAL' || r.risk_level === 'HIGH') {
      levelBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200';
      document.getElementById('riskScoreBar').className = 'h-full bg-gradient-to-r from-amber-500 to-rose-600 rounded-full transition-all duration-300';
    } else if (r.risk_level === 'MEDIUM') {
      levelBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200';
      document.getElementById('riskScoreBar').className = 'h-full bg-gradient-to-r from-emerald-500 to-amber-500 rounded-full transition-all duration-300';
    } else {
      levelBadge.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200';
      document.getElementById('riskScoreBar').className = 'h-full bg-gradient-to-r from-emerald-500 to-sky-500 rounded-full transition-all duration-300';
    }
  }

  // 5. Update Timeline with Confirmed Fraud Events
  if (data.confirmed_events && data.confirmed_events.length > 0) {
    data.confirmed_events.forEach(ev => {
      // Deduplicate event entry
      if (!sessionEventsHistory.some(existing => existing.event_id === ev.event_id)) {
        sessionEventsHistory.push(ev);
        appendEventToTimeline(ev);
      }
    });
  }
}

function appendEventToTimeline(ev) {
  const container = document.getElementById('eventsTimelineContainer');
  const emptyNotice = document.getElementById('noEventsNotice');
  const badge = document.getElementById('confirmedEventsBadge');

  if (emptyNotice) emptyNotice.classList.add('hidden');
  if (badge) badge.textContent = `${sessionEventsHistory.length} Event${sessionEventsHistory.length === 1 ? '' : 's'}`;

  const item = document.createElement('div');
  const severityColors = {
    CRITICAL: 'border-rose-200 bg-rose-50 text-rose-900',
    HIGH: 'border-rose-200 bg-rose-50 text-rose-900',
    MEDIUM: 'border-amber-200 bg-amber-50 text-amber-900',
    LOW: 'border-slate-200 bg-slate-50 text-slate-800',
  };

  item.className = `flex items-center justify-between p-3 rounded-xl border text-xs font-mono transition-all ${severityColors[ev.severity] || severityColors.MEDIUM}`;
  item.innerHTML = `
    <div class="flex items-center gap-3">
      <span class="w-2.5 h-2.5 rounded-full ${ev.severity === 'CRITICAL' || ev.severity === 'HIGH' ? 'bg-rose-500' : 'bg-amber-400'}"></span>
      <div>
        <span class="font-bold text-slate-900">${ev.event_type}</span>
        <span class="text-[10px] text-slate-500 ml-2">Conf: ${(ev.confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
    <div class="flex items-center gap-4 text-right">
      <span class="text-slate-600 text-[11px] font-medium">${(ev.duration_ms / 1000).toFixed(1)}s duration</span>
      <span class="text-slate-500 text-[10px]">${new Date(ev.timestamp_ms).toLocaleTimeString()}</span>
    </div>
  `;

  container.prepend(item);
}

async function openAnalyticsChartModal() {
  if (!activeSessionId) {
    showToast('Select an active session first.', 'warning');
    return;
  }
  const modal = document.getElementById('analyticsChartModal');
  const img = document.getElementById('analyticsChartImg');
  const spinner = document.getElementById('chartSpinner');
  const closeBtn = document.getElementById('closeChartModalBtn');

  modal.classList.remove('hidden');
  spinner.classList.remove('hidden');
  img.classList.add('hidden');

  try {
    const res = await api.fetchWithTimeout(api.buildUrl(`/fraud/sessions/${activeSessionId}/analytics/chart`), {
      headers: api.getHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    img.src = URL.createObjectURL(blob);
    spinner.classList.add('hidden');
    img.classList.remove('hidden');
  } catch (err) {
    spinner.textContent = `Chart rendering unavailable: ${err.message}`;
  }

  closeBtn.onclick = () => {
    modal.classList.add('hidden');
  };
}

document.addEventListener('DOMContentLoaded', initMonitoring);
