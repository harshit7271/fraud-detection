/**
 * FACEGUARD AI - Camera Lifecycle & Frame Capture Manager
 * Safe handling of MediaDevices API, device enumeration, canvas rendering, and track cleanup.
 */
export class CameraManager {
  constructor() {
    this.stream = null;
    this.videoElement = null;
    this.activeTrack = null;
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
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
        .map((d, index) => ({
          deviceId: d.deviceId,
          label: d.label || `Camera ${index + 1}`,
        }));
    } catch (err) {
      console.warn('Unable to enumerate video devices:', err);
      return [];
    }
  }

  /**
   * Starts camera stream attached to provided HTMLVideoElement
   */
  async start(videoElement, deviceId = null) {
    this.stop(); // Stop any existing stream
    this.videoElement = videoElement;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('MediaDevices API is not supported in this browser environment.');
    }

    const constraints = {
      audio: false,
      video: {
        width: { ideal: 1280, max: 1920 },
        height: { ideal: 720, max: 1080 },
        facingMode: 'user',
      },
    };

    if (deviceId) {
      constraints.video.deviceId = { exact: deviceId };
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;
      await this.videoElement.play();
      this.activeTrack = this.stream.getVideoTracks()[0] || null;

      return {
        width: this.videoElement.videoWidth || 640,
        height: this.videoElement.videoHeight || 480,
        label: this.activeTrack ? this.activeTrack.label : 'Active Camera',
      };
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        throw new Error('Camera access permission was denied. Please allow camera permissions in browser settings.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        throw new Error('No video camera device was found on this system.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        throw new Error('Camera is already in use by another application or operating system process.');
      }
      throw new Error(`Failed to initialize camera stream: ${err.message}`);
    }
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
