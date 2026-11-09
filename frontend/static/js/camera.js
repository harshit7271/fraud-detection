/**
 * FACEGUARD AI - Camera Lifecycle & Frame Capture Manager
 * Safe handling of MediaDevices API, mobile compatibility (iOS Safari & Android Chrome),
 * device enumeration, camera flipping, canvas rendering, and track cleanup.
 */
export class CameraManager {
  constructor() {
    this.stream = null;
    this.videoElement = null;
    this.activeTrack = null;
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.facingMode = 'user'; // 'user' (selfie/front) or 'environment' (back)
    this.currentDeviceId = null;
  }

  /**
   * Detects if the current user agent is a smartphone / mobile browser
   */
  isMobileDevice() {
    return (
      /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      (navigator.maxTouchPoints && navigator.maxTouchPoints > 2)
    );
  }

  /**
   * Enumerates available video input devices
   */
  async getAvailableCameras() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return [];
      }
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices
        .filter(d => d.kind === 'videoinput')
        .map((d, index) => {
          let label = d.label;
          if (!label) {
            label = index === 0 ? 'Front Camera (Default)' : `Camera ${index + 1}`;
          }
          return {
            deviceId: d.deviceId,
            label,
          };
        });
    } catch (err) {
      console.warn('Unable to enumerate video devices:', err);
      return [];
    }
  }

  /**
   * Starts camera stream attached to provided HTMLVideoElement
   * Fully compatible with iOS Safari (WebKit) and Android Chrome
   */
  async start(videoElement, deviceId = null) {
    this.stop(); // Stop any existing stream
    this.videoElement = videoElement;
    this.currentDeviceId = deviceId;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Camera MediaDevices API is not supported in this browser. Please ensure you are using HTTPS.');
    }

    // MANDATORY iOS Safari attributes: must be set before playback
    this.videoElement.setAttribute('autoplay', '');
    this.videoElement.setAttribute('playsinline', '');
    this.videoElement.setAttribute('webkit-playsinline', '');
    this.videoElement.playsInline = true;
    this.videoElement.muted = true;
    this.videoElement.setAttribute('muted', '');

    const isMobile = this.isMobileDevice();

    // Construct primary constraints
    let videoConstraint = {};
    if (deviceId) {
      // When deviceId is specified, do NOT specify facingMode (avoids OverconstrainedError in Safari/WebKit)
      videoConstraint = {
        deviceId: { exact: deviceId },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      };
    } else {
      videoConstraint = {
        facingMode: { ideal: this.facingMode },
        width: { ideal: isMobile ? 720 : 1280 },
        height: { ideal: isMobile ? 1280 : 720 },
      };
    }

    const primaryConstraints = {
      audio: false,
      video: videoConstraint,
    };

    try {
      this.stream = await this._getUserMediaWithFallback(primaryConstraints);
      this.videoElement.srcObject = this.stream;

      // Handle iOS Safari autoplay promise rejection gracefully
      try {
        await this.videoElement.play();
      } catch (playErr) {
        console.warn('Autoplay was restricted by browser policy; retrying with explicit muted state:', playErr);
        this.videoElement.muted = true;
        await this.videoElement.play();
      }

      this.activeTrack = this.stream.getVideoTracks()[0] || null;

      // Wait briefly for video metadata to populate natural dimensions
      const videoW = this.videoElement.videoWidth || (isMobile ? 720 : 1280);
      const videoH = this.videoElement.videoHeight || (isMobile ? 1280 : 720);

      return {
        width: videoW,
        height: videoH,
        label: this.activeTrack ? this.activeTrack.label : (this.facingMode === 'user' ? 'Front Camera' : 'Back Camera'),
        facingMode: this.facingMode,
        isMobile,
      };
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        throw new Error('Camera access permission was denied. Please allow camera permissions in your phone/browser settings.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        throw new Error('No video camera was detected on this mobile or desktop device.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        throw new Error('Camera is currently locked or in use by another app.');
      } else if (err.name === 'OverconstrainedError') {
        throw new Error('Camera resolution constraints could not be satisfied by this phone.');
      }
      throw new Error(`Failed to initialize camera: ${err.message}`);
    }
  }

  /**
   * Robust multi-stage fallback for mobile cameras
   */
  async _getUserMediaWithFallback(constraints) {
    try {
      return await navigator.mediaDevices.getUserMedia(constraints);
    } catch (primaryErr) {
      console.warn('Primary camera constraints failed, attempting fallback with facingMode:', primaryErr);
      try {
        // Fallback 1: Simple facingMode
        return await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: this.facingMode } },
        });
      } catch (fbErr1) {
        console.warn('Fallback 1 failed, trying generic video constraint:', fbErr1);
        // Fallback 2: Basic video
        return await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: true,
        });
      }
    }
  }

  /**
   * Toggles between Front (selfie) and Back (environment) camera on smartphones
   */
  async flipCamera(videoElement) {
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
    this.currentDeviceId = null;
    return await this.start(videoElement || this.videoElement, null);
  }

  /**
   * Grabs a single frame from the active video stream as Blob and Base64
   */
  captureFrame(quality = 0.85) {
    if (!this.videoElement || this.videoElement.readyState < 2) {
      throw new Error('Camera stream is not ready for capture.');
    }

    const width = this.videoElement.videoWidth || 640;
    const height = this.videoElement.videoHeight || 480;

    this.canvas.width = width;
    this.canvas.height = height;
    this.ctx.drawImage(this.videoElement, 0, 0, width, height);

    const dataUrl = this.canvas.toDataURL('image/jpeg', quality);
    const base64 = dataUrl.split(',')[1];

    return new Promise((resolve, reject) => {
      this.canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve({ blob, base64, dataUrl, width, height });
          } else {
            reject(new Error('Failed to encode canvas frame to JPEG blob.'));
          }
        },
        'image/jpeg',
        quality
      );
    });
  }

  /**
   * Stops all active media tracks and clears video source
   */
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        track.stop();
      });
      this.stream = null;
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
    this.activeTrack = null;
  }
}
