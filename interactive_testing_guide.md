# Practical System Testing & Execution Guide

This guide details how the Computer Vision pipeline and REST API endpoints execute practical scenarios, and provides instructions for running them yourself.

---

## 1. Computer Vision Practical Pipeline (`scripts/demo_cv_practical.py`)

Run this command in your terminal:
```powershell
.\.venv\Scripts\python scripts/demo_cv_practical.py
```

### What It Executes & Verifies
1. **Pretrained Model Initialization**:
   - Loads OpenCV's `FaceDetectorYN` (YuNet) and `FaceRecognizerSF` (SFace).
   - Initializes `QualityAssessor` and `FaceTracker`.
2. **Quality Assessment**:
   - Evaluates Laplacian blur variance ($115.67 \ge 60.0$).
   - Evaluates mean luminance ($207.4$) and contrast ($15.7$).
3. **Face Detection & Landmark Extraction**:
   - Detects single face bounding box `[x=235, y=118, w=185, h=254]` with $61.1\%$ confidence.
   - Computes 5 facial keypoints: Right Eye, Left Eye, Nose Tip, Right Mouth, Left Mouth.
   - Generates annotated visual in [demo_output/01_selfie_detection.jpg](file:///C:/Projects/fraud-detection-opencv/demo_output/01_selfie_detection.jpg).
4. **Face Alignment & Embedding Extraction**:
   - Aligns face chip to standard $112 \times 112$ RGB matrix via landmark geometry.
   - Generates annotated visual in [demo_output/02_aligned_112x112_face_chip.jpg](file:///C:/Projects/fraud-detection-opencv/demo_output/02_aligned_112x112_face_chip.jpg).
   - Computes 128-dimensional L2 unit-normalized feature vector ($\|\vec{v}\|_2 = 1.000000$).
5. **Identity Verification & Cosine Similarity**:
   - **Self-Match**: Candidate compared against themselves yields Cosine Similarity $= 1.0000 \to$ `MATCH`.
   - **Different Face**: Compared against alternate geometry yields Cosine Similarity $= 0.7557 < 0.85 \to$ `UNCERTAIN` / `MISMATCH`.
6. **Multiple Face Detection**:
   - Evaluates multi-face frame and detects exactly 2 faces.
   - Generates annotated visual in [demo_output/03_multiple_faces_detection.jpg](file:///C:/Projects/fraud-detection-opencv/demo_output/03_multiple_faces_detection.jpg).
7. **Multi-Frame Tracking**:
   - Tracks a moving face across consecutive timestamps ($t=0$ms, $t=500$ms, $t=1000$ms).
   - Maintains continuous **`Track ID: 1`**, preventing identity flickering.

---

## 2. REST API Lifecycle Practical (`scripts/demo_api_practical.py`)

Run this command in your terminal:
```powershell
.\.venv\Scripts\python scripts/demo_api_practical.py
```

### What It Executes & Verifies
1. **Health & Readiness Endpoints**:
   - `GET /healthz` $\to$ Returns HTTP 200 with service version and UTC timestamp.
   - `GET /readyz` $\to$ Returns HTTP 200 verifying YuNet and SFace weights are loaded on disk.
2. **Session Registration (`POST /api/v1/fraud/sessions`)**:
   - Submits candidate ID, interview ID, biometric consent, and selfie via `multipart/form-data`.
   - Authenticated with `X-Tenant-Key: alorica-live-key-2026`.
   - Returns HTTP 201 `CREATED` with unique `session_id` and reference bounding box metadata.
3. **Normal Frame Analysis (`POST /api/v1/fraud/sessions/{id}/analyze`)**:
   - Submits Frame Batch 1 (Candidate participating normally).
   - Returns HTTP 200: `faces_detected=1`, `identity_match="MATCH"`, `risk_score=0.0 (LOW)`, `recommendation="NO_ACTION"`.
4. **Sustained Absence Event**:
   - Submits Frame Batch 2 (Candidate stepped away from camera for 3.5s).
   - Debounce triggers at $3.0$s $\to$ Confirms `FACE_ABSENT` event (`severity=MEDIUM`, `duration=3500ms`).
   - Risk score increments to $20.0$.
5. **Multiple Faces Event**:
   - Submits Frame Batch 3 (Second person enters frame for 2.2s).
   - Debounce triggers at $2.0$s $\to$ Confirms `MULTIPLE_FACES` event (`severity=HIGH`, `faces_found=2`).
   - Risk score increments to $50.0$ (`HIGH`) $\to$ Recommendation updates to `REVIEW_REQUIRED`.
6. **Consolidated Fraud Report (`GET /api/v1/fraud/sessions/{id}/report`)**:
   - Retrieves full session summary with itemized scoring explanation:
     - `FACE_ABSENT`: 1 event contributed 20.0 pts.
     - `MULTIPLE_FACES`: 1 event contributed 30.0 pts.
     - Final Recommendation: `REVIEW_REQUIRED`.
7. **Multi-Tenant Boundary Isolation**:
   - Attempts to access Alorica's session using Sagility credentials (`X-Tenant-Key: sagility-live-key-2026`).
   - System returns HTTP 404 `SESSION_NOT_FOUND`, enforcing strict tenant segregation.

---

## 3. How to Run the Live Server Yourself

### Start Uvicorn Server
Open a terminal in `C:\Projects\fraud-detection-opencv` and run:
```powershell
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive Swagger UI will be live at:
👉 **http://127.0.0.1:8000/docs**

### Sample `curl` Commands

#### 1. Check Service Health
```bash
curl -X GET http://127.0.0.1:8000/healthz
```

#### 2. Check Service Readiness
```bash
curl -X GET http://127.0.0.1:8000/readyz
```

#### 3. Register Candidate Selfie
```bash
curl -X POST http://127.0.0.1:8000/api/v1/fraud/sessions \
  -H "X-Tenant-Key: alorica-live-key-2026" \
  -F "candidate_id=cand_001" \
  -F "interview_id=int_101" \
  -F "consent=true" \
  -F "selfie_file=@demo_output/01_selfie_detection.jpg"
```
