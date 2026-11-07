# Pre-trained Computer Vision Model Weights

This directory holds the ONNX model weights used by the Face Fraud Detection Microservice.

## Models

### 1. YuNet Face Detector (`face_detection_yunet_2023mar.onnx`)
- **Origin**: OpenCV Zoo (`opencv/opencv_zoo`)
- **Version**: March 2023 release
- **Architecture**: Lightweight CNN with Feature Pyramid Network (FPN) and single-stage anchor-free detection
- **Input**: `[1, 3, H, W]` RGB image normalized to $[0, 255]$
- **Output**:
  - Bounding box: `[x, y, w, h]`
  - Confidence score: $[0.0, 1.0]$
  - 5 Facial Landmarks: Right eye, left eye, nose tip, right mouth corner, left mouth corner
- **License**: Apache 2.0 (Permissive, commercial use permitted)

### 2. SFace Face Recognizer (`face_recognition_sface_2021dec.onnx`)
- **Origin**: OpenCV Zoo (`opencv/opencv_zoo`)
- **Version**: December 2021 release
- **Architecture**: Lightweight sphere-face feature extractor
- **Input**: `[1, 3, 112, 112]` aligned BGR/RGB face crop produced by `FaceRecognizerSF.alignCrop`
- **Output**: 128-dimensional L2-normalized feature vector (`np.ndarray` of shape `(128,)`, dtype `float32`)
- **Distance Metric**: Cosine similarity (`FaceRecognizerSF.FR_COSINE`)
- **License**: Apache 2.0 (Permissive, commercial use permitted)

## Downloading Weights
Run the automated downloader script:
```bash
python scripts/download_models.py
```
