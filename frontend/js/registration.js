/**
 * FACEGUARD AI - Candidate Registration Controller
 * Webcam selfie capture, local file upload, pre-validation diagnostics, and session registration.
 */
import { api } from './api.js';
import { CameraManager } from './camera.js';
import { Config } from './config.js';
import { renderNavigation, renderHeader, showToast } from './components.js';

const camera = new CameraManager();
let currentSelfieBlob = null;
let isSelfieValidated = false;

async function initRegistration() {
  renderNavigation('register');
  renderHeader('Candidate Registration', 'Enroll candidate biometric baseline and generate encrypted reference vector.');

  const videoEl = document.getElementById('registerVideo');
  const snapBtn = document.getElementById('snapBtn');
  const retakeBtn = document.getElementById('retakeBtn');
  const uploadInput = document.getElementById('selfieFileInput');
  const registerBtn = document.getElementById('submitRegisterBtn');
  const cameraSelect = document.getElementById('cameraSelect');

  // Auto-generate fresh unique candidate & interview IDs
  generateUniqueIdentifiers();

  const randomizeBtn = document.getElementById('randomizeIdsBtn');
  if (randomizeBtn) {
    randomizeBtn.addEventListener('click', () => {
      generateUniqueIdentifiers();
      showToast('Generated fresh candidate and interview identifiers.', 'info');
    });
  }

  // Start Webcam Preview
  try {
    const res = await camera.start(videoEl);
    showToast(`Camera active: ${res.label} (${res.width}x${res.height})`, 'success');
    populateCameraDevices(cameraSelect);
  } catch (err) {
    showToast(err.message, 'warning');
    const previewContainer = document.getElementById('cameraPreviewNotice');
    if (previewContainer) {
      previewContainer.textContent = err.message;
      previewContainer.classList.remove('hidden');
    }
  }

  // Snap Snapshot from Webcam
  if (snapBtn) {
    snapBtn.addEventListener('click', async () => {
      try {
        const frame = await camera.captureFrame(0.95);
        displayCapturedSelfie(frame.dataUrl, frame.blob);
        await validateSelfieWithBackend(frame.blob);
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Retake Photo
  if (retakeBtn) {
    retakeBtn.addEventListener('click', () => {
      resetToLiveCamera();
    });
  }

  // Mobile Camera Flip (Front / Back)
  const flipCamBtn = document.getElementById('flipCamBtn');
  if (flipCamBtn) {
    flipCamBtn.addEventListener('click', async () => {
      try {
        const res = await camera.flipCamera(videoEl);
        showToast(`Switched to ${camera.facingMode === 'user' ? 'Front (Selfie)' : 'Back'} Camera`, 'info');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Local Image Upload Fallback
  if (uploadInput) {
    uploadInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        if (!file.type.startsWith('image/')) {
          showToast('Invalid file format. Please select a valid JPEG, PNG or WebP image.', 'error');
          return;
        }
        const reader = new FileReader();
        reader.onload = async (event) => {
          displayCapturedSelfie(event.target.result, file);
          await validateSelfieWithBackend(file);
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Camera Switch Listener
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

  // Consent Checkbox listener
  const consentBox = document.getElementById('consentCheckbox');
  if (consentBox) {
    consentBox.addEventListener('change', () => {
      updateRegisterButtonState();
    });
  }

  // Submit Registration Button
  if (registerBtn) {
    registerBtn.addEventListener('click', async () => {
      await submitCandidateRegistration();
    });
  }

  // Clean up stream if page is unloaded
  window.addEventListener('beforeunload', () => {
    camera.stop();
  });
}

async function populateCameraDevices(selectEl) {
  if (!selectEl) return;
  const cameras = await camera.getAvailableCameras();
  if (cameras.length > 1) {
    selectEl.innerHTML = cameras.map(c => `<option value="${c.deviceId}">${c.label}</option>`).join('');
    selectEl.classList.remove('hidden');
  }
}

function displayCapturedSelfie(dataUrl, blob) {
  currentSelfieBlob = blob;
  const livePreview = document.getElementById('liveVideoContainer');
  const capturedPreview = document.getElementById('capturedPreviewContainer');
  const selfieImg = document.getElementById('capturedSelfieImg');
  const snapBtn = document.getElementById('snapBtn');
  const retakeBtn = document.getElementById('retakeBtn');

  if (livePreview) livePreview.classList.add('hidden');
  if (capturedPreview) capturedPreview.classList.remove('hidden');
  if (selfieImg) selfieImg.src = dataUrl;
  if (snapBtn) snapBtn.classList.add('hidden');
  if (retakeBtn) retakeBtn.classList.remove('hidden');
}

function generateUniqueIdentifiers() {
  const candidateInput = document.getElementById('candidateIdInput');
  const interviewInput = document.getElementById('interviewIdInput');
  const randNum = Math.floor(1000 + Math.random() * 9000);
  const timeSlice = Date.now().toString().slice(-4);

  if (candidateInput) {
    candidateInput.value = `cand_${timeSlice}${randNum.toString().slice(-2)}`;
  }
  if (interviewInput) {
    interviewInput.value = `int_eval_${randNum}`;
  }
}

function resetToLiveCamera() {
  currentSelfieBlob = null;
  isSelfieValidated = false;

  const livePreview = document.getElementById('liveVideoContainer');
  const capturedPreview = document.getElementById('capturedPreviewContainer');
  const snapBtn = document.getElementById('snapBtn');
  const retakeBtn = document.getElementById('retakeBtn');

  if (livePreview) livePreview.classList.remove('hidden');
  if (capturedPreview) capturedPreview.classList.add('hidden');
  if (snapBtn) snapBtn.classList.remove('hidden');
  if (retakeBtn) retakeBtn.classList.add('hidden');

  // Reset telemetry cards
  document.getElementById('diagBlurVal').textContent = '—';
  document.getElementById('diagBrightVal').textContent = '—';
  document.getElementById('diagContrastVal').textContent = '—';
  document.getElementById('diagFacesVal').textContent = '—';

  const badge = document.getElementById('validationBadge');
  badge.textContent = 'AWAITING IMAGE';
  badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200';

  document.getElementById('validationMessage').textContent = 'Capture or upload a front-facing selfie to run server-side quality diagnostics.';
  updateRegisterButtonState();
}

async function validateSelfieWithBackend(blob) {
  const badge = document.getElementById('validationBadge');
  const msg = document.getElementById('validationMessage');
  const blurEl = document.getElementById('diagBlurVal');
  const brightEl = document.getElementById('diagBrightVal');
  const contrastEl = document.getElementById('diagContrastVal');
  const facesEl = document.getElementById('diagFacesVal');

  badge.textContent = 'EVALUATING...';
  badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200';
  msg.textContent = 'Analyzing Laplacian variance, luminance, contrast, and landmark occlusion via YuNet detector...';

  const formData = new FormData();
  formData.append('selfie_file', blob, 'selfie.jpg');

  try {
    const data = await api.postFormData('/fraud/sessions/validate-selfie', formData);

    blurEl.textContent = data.blur_score !== undefined ? data.blur_score : 'N/A';
    brightEl.textContent = data.brightness_score !== undefined ? data.brightness_score : 'N/A';
    contrastEl.textContent = data.contrast_score !== undefined ? data.contrast_score : 'N/A';
    facesEl.textContent = data.faces_detected !== undefined ? data.faces_detected : '0';

    if (data.valid) {
      isSelfieValidated = true;
      badge.textContent = 'PASSED';
      badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200';
      msg.textContent = '✓ 1 unoccluded face verified with high biometric confidence. Ready for registration.';
      showToast('Selfie quality check passed.', 'success');
    } else {
      isSelfieValidated = false;
      badge.textContent = 'REJECTED';
      badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200';
      msg.textContent = `❌ ${data.error || 'Face quality standards not met. Remove hands/objects and ensure clear lighting.'}`;
      showToast('Selfie rejected: ' + (data.error || 'Quality issues detected'), 'warning');
    }
  } catch (err) {
    isSelfieValidated = false;
    badge.textContent = 'ERROR';
    badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200';
    msg.textContent = `Pre-validation request failed: ${err.message}`;
  } finally {
    updateRegisterButtonState();
  }
}

function updateRegisterButtonState() {
  const registerBtn = document.getElementById('submitRegisterBtn');
  const consent = document.getElementById('consentCheckbox')?.checked;

  if (!registerBtn) return;

  if (currentSelfieBlob && isSelfieValidated && consent) {
    registerBtn.disabled = false;
    registerBtn.className = 'bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-3 px-6 rounded-xl transition shadow-lg shadow-emerald-600/25 cursor-pointer flex items-center justify-center gap-2 w-full';
    registerBtn.innerHTML = `<span>✓</span><span>Complete Registration & Generate Baseline</span>`;
  } else {
    registerBtn.disabled = true;
    registerBtn.className = 'bg-slate-800 text-slate-500 text-xs font-bold py-3 px-6 rounded-xl transition cursor-not-allowed flex items-center justify-center gap-2 w-full';
    if (!currentSelfieBlob) {
      registerBtn.innerHTML = `<span>Snap or Upload Selfie to Proceed</span>`;
    } else if (!isSelfieValidated) {
      registerBtn.innerHTML = `<span>Selfie Quality Check Failed (Re-take Photo)</span>`;
    } else if (!consent) {
      registerBtn.innerHTML = `<span>Check Biometric Consent to Continue</span>`;
    }
  }
}

async function submitCandidateRegistration() {
  const candidateId = document.getElementById('candidateIdInput').value.trim();
  const interviewId = document.getElementById('interviewIdInput').value.trim();
  const consent = document.getElementById('consentCheckbox').checked;
  const registerBtn = document.getElementById('submitRegisterBtn');

  if (!candidateId || !interviewId) {
    showToast('Candidate ID and Interview ID are mandatory.', 'warning');
    return;
  }
  if (!currentSelfieBlob || !isSelfieValidated) {
    showToast('Valid baseline selfie is required.', 'warning');
    return;
  }

  registerBtn.disabled = true;
  registerBtn.innerHTML = `
    <svg class="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
    <span>Encrypting & Registering Reference Vector...</span>
  `;

  const formData = new FormData();
  formData.append('candidate_id', candidateId);
  formData.append('interview_id', interviewId);
  formData.append('consent', consent ? 'true' : 'false');
  formData.append('selfie_file', currentSelfieBlob, 'selfie.jpg');

  try {
    const data = await api.postFormData('/fraud/sessions', formData);

    // Show Success State Modal / Overlay
    displayRegistrationSuccess(data);
    showToast(`Session successfully initialized: ${data.session_id}`, 'success');
  } catch (err) {
    showToast(`Registration failed: ${err.message}`, 'error');
    registerBtn.disabled = false;
    registerBtn.innerHTML = `<span>Retry Registration</span>`;
  }
}

function displayRegistrationSuccess(result) {
  const successModal = document.getElementById('registrationSuccessModal');
  const sessionSpan = document.getElementById('successSessionId');
  const candSpan = document.getElementById('successCandidateId');
  const confSpan = document.getElementById('successConfidence');
  const monitorLink = document.getElementById('goToMonitoringBtn');

  if (sessionSpan) sessionSpan.textContent = result.session_id;
  if (candSpan) candSpan.textContent = result.candidate_id;
  if (confSpan) confSpan.textContent = `${(result.reference_face.confidence * 100).toFixed(1)}%`;
  if (monitorLink) {
    monitorLink.href = `/monitor?session_id=${result.session_id}&candidate_id=${encodeURIComponent(result.candidate_id)}`;
  }

  if (successModal) {
    successModal.classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', initRegistration);
