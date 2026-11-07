---
title: "FaceGuard AI - Proctoring Fraud Detection"
emoji: "🛡️"
colorFrom: "indigo"
colorTo: "gray"
sdk: gradio
sdk_version: "5.20.0"
python_version: "3.12"
app_file: app.py
pinned: false
---

# FACEGUARD AI — Enterprise Face Fraud Detection Platform

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-YuNet%20%7C%20SFace-5C3EE8.svg)](https://opencv.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20Async-D71F00.svg)](https://www.sqlalchemy.org/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-Enterprise%20Light-38B2AC.svg)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-79%20Passed-emerald.svg)]()

**FACEGUARD AI** is a production-grade, enterprise microservice and proctoring dashboard for real-time facial fraud detection during remote candidate interviews, online examinations, and identity verification workflows. 

Engineered with a **zero-trust biometric security architecture**, **multi-tenant isolation**, and **temporal debounce state machines**, the platform eliminates false alarms from minor head turns while catching sustained impersonation, multiple concurrent attendees, prolonged face absences, and deliberate hand/mask occlusions.

---

## Table of Contents
1. [Core Features](#1-core-features)
2. [Microservice Architecture & Data Flow](#2-microservice-architecture--data-flow)
3. [Database Architecture & Data Model (Full Specification)](#3-database-architecture--data-model-full-specification)
   - [Data Domains & Tables](#data-domains--tables)
   - [Zero-Trust Biometrics & Cryptographic Protection](#zero-trust-biometrics--cryptographic-protection)
   - [Hot Path vs. Cold Path Storage](#hot-path-vs-cold-path-storage)
   - [Scalability, Sharding & Connection Pooling](#scalability-sharding--connection-pooling)
   - [Database Connection & Environment Configuration](#database-connection--environment-configuration)
4. [Computer Vision & Fraud Detection Pipeline](#4-computer-vision--fraud-detection-pipeline)
5. [Enterprise Light Mode Dashboard (Frontend UI)](#5-enterprise-light-mode-dashboard-frontend-ui)
6. [API Endpoints Reference](#6-api-endpoints-reference)
7. [Installation & Quickstart Guide](#7-installation--quickstart-guide)
8. [Testing & Quality Verification](#8-testing--quality-verification)

---

## 1. Core Features

* **High-Accuracy Edge Face Detection**: Powered by OpenCV ONNX YuNet for sub-25ms inference per frame.
* **128-Dimensional Biometric Cosine Comparison**: Uses normalized SFace embeddings to continuously compare live interview video frames against the baseline enrolled selfie.
* **Hand / Object Occlusion Pre-Screening**: Dynamic geometric checks ($V_{\text{dist}} \ge 0.35 \times D_{\text{eyes}}$ and landmark vertical monotonicity) reject covered faces immediately at enrollment and flag them during proctoring.
* **Temporal Debounce Engine**: Filters transient camera glitches and momentary eye blinks using customizable debounce windows ($2000\text{ms}$ multi-face, $3000\text{ms}$ face absence).
* **Zero-Trust Biometrics**: Raw candidate images are discarded from persistent storage; only **AES-256-GCM encrypted feature embeddings** are retained at rest.
* **Strict Multi-Tenant Boundaries**: Every API transaction and database query enforces tenant separation with hashed API keys and tenant-specific risk weights.
* **Executive Light Enterprise Dashboard**: Zero-framework, pure HTML5/ES6/Tailwind web interface featuring live video proctoring HUD, violation counters, real-time warning alerts, and publication-quality Matplotlib telemetry diagrams.

---

## 2. Microservice Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Client["Client Browser / Proctor Room"]
        CAM["Webcam (HTML5 MediaDevices)"] --> CANVAS["Canvas Frame Sampler (1-2 FPS)"]
        CANVAS --> POST["POST /api/v1/fraud/sessions/{id}/analyze"]
    end

    subgraph Service["FastAPI Microservice Engine"]
        POST --> AUTH["Tenant Auth Middleware (X-Tenant-Key)"]
        AUTH --> CV["YuNet Detector & SFace Recognizer"]
        CV --> OCC["Occlusion & Quality Validator"]
        OCC --> TRACKER["FaceTracker (Temporal IoU)"]
        TRACKER --> DEBOUNCE["Temporal Event Engine"]
        DEBOUNCE --> SCORE["Risk Scoring Engine (0 - 100)"]
    end

    subgraph DataStorage["Tiered Persistence Layer"]
        TRACKER -.-> HOT["Hot Path: In-Memory / Redis Debounce Window"]
        SCORE --> COLD["Cold Path: SessionRepository (Asyncpg)"]
        COLD --> PG[("PostgreSQL 16+ Database Pool")]
        COLD --> CRYPTO["AES-256-GCM Biometric Vault"]
    end
```

---

## 3. Database Architecture & Data Model (Full Specification)

FACEGUARD AI decouples high-frequency visual frame processing from persistent relational auditing. Below is the comprehensive architectural log of how the database manages data, enforces security, and scales in high-load production environments.

### Data Domains & Tables

The schema is divided into 6 distinct functional tables managed by SQLAlchemy 2.0 Async ORM:

```
+----------------------------------------------------------------------------------------------------+
|                                    FACEGUARD AI DATA DOMAINS                                       |
+----------------------------------------------------------------------------------------------------+
| 1. tenants            -> Multi-tenant boundary, organization name, API key hash digest             |
| 2. tenant_configs     -> Custom debounce durations, cosine tolerances, retention policies          |
| 3. interview_sessions -> Session lifecycle state, candidate ID, interview ID, consent record       |
| 4. reference_faces    -> Encrypted 128-d face embedding vector, IV, key version, baseline quality  |
| 5. fraud_events       -> Chronological time-series stream of confirmed proctoring violations       |
| 6. fraud_reports      -> Aggregated 0-100 risk score, risk level, system action recommendation     |
| 7. audit_logs         -> Immutable SOC-2/GDPR compliance trail of auditor/admin actions            |
| 8. processing_jobs    -> Celery asynchronous batch queue tracking for bulk video analysis          |
+----------------------------------------------------------------------------------------------------+
```

#### Detailed Table Specifications

1. **`tenants`**:
   - `id` (`UUID`, PK): Global unique tenant identifier.
   - `slug` (`VARCHAR(64)`, Unique, Indexed): Client handle (e.g. `alorica`, `sagility`, `mastek`).
   - `name` (`VARCHAR(255)`): Official enterprise organization name.
   - `api_key_hash` (`VARCHAR(255)`): Salted SHA-256 digest of client secret.
   - `is_active` (`BOOLEAN`): Administrative kill-switch.
   - `created_at`, `updated_at`: UTC timestamps.

2. **`tenant_configs`**:
   - `id` (`UUID`, PK) & `tenant_id` (`UUID`, FK with cascade delete).
   - `face_match_threshold` (`FLOAT`, default `0.38`): Cosine distance cutoff for identity verification.
   - `face_uncertain_threshold` (`FLOAT`, default `0.25`): Warning buffer for variable lighting.
   - `multiple_faces_debounce_ms` (`INTEGER`, default `2000`): Debounce period before triggering multi-face violation.
   - `face_absence_debounce_ms` (`INTEGER`, default `3000`): Grace period for candidate head movements.
   - `event_weights` (`JSON`): Weight assigned to each violation type in risk scoring.
   - `risk_bands` (`JSON`): Cutoffs for `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` categories.
   - `biometric_retention_days` (`INTEGER`, default `30`): Automatic data retention expiration.

3. **`interview_sessions`**:
   - `id` (`UUID`, PK): Session identifier returned to client.
   - `tenant_id` (`UUID`, FK): Enforces tenant boundary isolation.
   - `candidate_id` (`VARCHAR(128)`, Indexed): External candidate identifier.
   - `interview_id` (`VARCHAR(128)`, Indexed): External interview room or requisition identifier.
   - `status` (`VARCHAR(32)`): Lifecycle status (`INITIALIZED`, `ACTIVE`, `COMPLETED`, `FLAGGED`).
   - `consent_recorded` (`BOOLEAN`): Explicit biometric consent record (GDPR/BIPA mandatory).
   - `started_at`, `ended_at` (`TIMESTAMPTZ`): Interview duration timestamps.

4. **`reference_faces`**:
   - `id` (`UUID`, PK), `tenant_id` (`UUID`, FK), `session_id` (`UUID`, FK, Unique).
   - `encrypted_embedding` (`BYTEA`): 128-dimensional OpenCV SFace vector encrypted via AES-256-GCM.
   - `encryption_iv` (`BYTEA`): Cryptographic 96-bit initialization vector.
   - `key_version` (`VARCHAR(32)`): Key rotation index (`v1-2026`).
   - `quality_score` (`FLOAT`): Baseline sharpness variance score.
   - `bbox_metadata` (`JSON`): Facial bounding box, pitch/yaw pose angles, and landmark geometry.

5. **`fraud_events`**:
   - `id` (`UUID`, PK), `tenant_id` (`UUID`, FK), `session_id` (`UUID`, FK, Indexed).
   - `event_type` (`VARCHAR(64)`, Indexed): Violation category (`IDENTITY_MISMATCH`, `MULTIPLE_FACES`, `FACE_ABSENT`, `FACE_OCCLUSION`).
   - `timestamp_ms` (`BIGINT`): Exact millisecond elapsed time from proctoring start.
   - `duration_ms` (`INTEGER`): Duration anomaly persisted beyond debounce threshold.
   - `confidence` (`FLOAT`): Computer vision model certainty ($0.0 - 1.0$).
   - `severity` (`VARCHAR(16)`): Anomaly severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - `evidence_metadata` (`JSON`): Bounding boxes, similarity distances, and frame coordinates.

6. **`fraud_reports`**:
   - `id` (`UUID`, PK), `tenant_id` (`UUID`, FK), `session_id` (`UUID`, FK, Unique).
   - `risk_score` (`FLOAT`): Final aggregated risk score ($0.0 - 100.0$).
   - `risk_level` (`VARCHAR(32)`): Categorical risk band (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - `fraud_status` (`VARCHAR(32)`): Session verdict (`CLEARED`, `SUSPICIOUS`, `CONFIRMED_FRAUD`).
   - `recommendation` (`VARCHAR(32)`): Action recommendation (`NO_ACTION`, `CONTINUE_MONITORING`, `REVIEW_REQUIRED`, `ESCALATE`).
   - `summary_breakdown` (`JSON`): Statistical breakdown of violation frequencies and durations.

7. **`audit_logs`**:
   - `id` (`UUID`, PK), `tenant_id` (`UUID`, FK), `actor` (`VARCHAR(128)`), `action` (`VARCHAR(64)`), `resource_type` (`VARCHAR(64)`), `resource_id` (`VARCHAR(128)`), `ip_address` (`VARCHAR(45)`), `timestamp` (`TIMESTAMPTZ`).

8. **`processing_jobs`**:
   - `id` (`UUID`, PK), `tenant_id` (`UUID`, FK), `session_id` (`UUID`, FK), `celery_task_id` (`VARCHAR(255)`), `status` (`VARCHAR(32)`), `frames_count` (`INTEGER`), `processing_time_ms` (`INTEGER`), `result_payload` (`JSON`).

---

### Zero-Trust Biometrics & Cryptographic Protection

1. **No Raw Image Storage**:
   Raw selfie images and video frames are decoded in RAM, validated for landmarks and sharpness, embedded into mathematical vectors, and immediately purged from memory.
2. **Authenticated Encryption at Rest (AES-256-GCM)**:
   Facial embeddings are converted to IEEE-754 binary arrays and encrypted using AES-256 in Galois/Counter Mode (GCM). This guarantees both **confidentiality** and **authenticity**. Even if the database is compromised, the embeddings cannot be viewed, manipulated, or reverse-engineered into facial imagery.
3. **Key Rotation (`key_version`)**:
   Every biometric record tracks its active cipher key version (`v1-2026`), allowing zero-downtime key rotation policies required by corporate SOC-2 Type II standards.

---

### Hot Path vs. Cold Path Storage

To sustain hundreds of live candidate video streams without overwhelming the database:

* **Hot Path (Real-Time In-Memory & Redis)**:
  * Frame sampling at 1-2 FPS.
  * In-memory `FaceTracker` tracks bounding boxes across frames via Intersection-over-Union (IoU).
  * Transient interruptions under the debounce threshold (e.g., a 400ms sneeze or head scratch) are evaluated and discarded in memory with zero database disk I/O.
* **Cold Path (Scalable Async Persistence)**:
  * Only when a violation is sustained past the debounce threshold does the `TemporalEventEngine` commit an event.
  * Writes are dispatched through non-blocking `SessionRepository` using async SQLAlchemy 2.0 and `asyncpg`.

---

### Scalability, Sharding & Connection Pooling

* **Connection Pool Optimization**:
  * Default pool size: 10 connections (`pool_size=10`).
  * Max overflow: 20 connections (`max_overflow=20`).
  * Connection health check: `pool_pre_ping=True` drops stale connections automatically before query dispatch.
* **Tenant Partitioning**:
  * All queries enforce composite keys `(tenant_id, session_id)` or `(tenant_id, candidate_id)`.
  * Allows table partitioning on `tenant_id` when transaction volume reaches millions of events per month.
* **Biometric Retention Expiry**:
  * Automated scheduled tasks use `tenant_configs.biometric_retention_days` to nullify `encrypted_embedding` records post-interview, mitigating permanent biometric liability.

---

### Database Connection & Environment Configuration

Database configuration is centralized in `app/core/config.py` and can be overridden via `.env`:

```env
# Database Settings
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=face_fraud_db
DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5432/face_fraud_db
SYNC_DATABASE_URL=postgresql://postgres:postgres_password@localhost:5432/face_fraud_db

# Biometric Master Encryption
BIOMETRIC_MASTER_KEY=MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=
BIOMETRIC_KEY_VERSION=v1-2026
```

> [!NOTE]
> On local development machines with standalone PostgreSQL instances listening on alternate ports (e.g., port `5433`), simply point `POSTGRES_PORT=5433` in `.env`. When running via `docker-compose up`, PostgreSQL automatically launches on standard port `5432`.

---

## 4. Computer Vision & Fraud Detection Pipeline

```mermaid
flowchart LR
    A["Input Frame (JPEG)"] --> B["OpenCV YuNet ONNX"]
    B --> C{"Face Count?"}
    C -- "0 Faces (>3s)" --> D["Confirmed FACE_ABSENT"]
    C -- ">1 Faces (>2s)" --> E["Confirmed MULTIPLE_FACES"]
    C -- "1 Face" --> F["Landmark Monotonicity & Occlusion Check"]
    F -- "Occluded" --> G["Confirmed FACE_OCCLUSION"]
    F -- "Unoccluded" --> H["SFace Feature Extractor (128-d)"]
    H --> I["Cosine Distance Calculation"]
    I -- "Distance < Threshold" --> J["Confirmed IDENTITY_MISMATCH"]
    I -- "Distance >= Threshold" --> K["Identity Verified (Compliant)"]
```

* **YuNet Detection**: Dynamic scale face bounding box coordinates, confidence score, and 5 facial landmarks (eyes, nose tip, mouth corners).
* **SFace 128-d Recognition**: Extracts normalized feature embeddings. Compares candidate frames against baseline using Cosine Distance:
  $$\text{Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
* **Geometric Occlusion Filter**: Checks whether eyes, nose, and mouth appear in strict vertical sequence ($y_{\text{eyes}} < y_{\text{nose}} < y_{\text{mouth}}$) and maintains eye-to-mouth ratio ($V_{\text{dist}} \ge 0.35 \times D_{\text{eyes}}$). Blocks users from proctoring while covering mouth, nose, or forehead.

---

## 5. Enterprise Light Mode Dashboard (Frontend UI)

The web dashboard is delivered without heavy frontend frameworks (no React, Next.js, or Vue), providing instant load times, zero compilation steps, and seamless native browser debugging:

```
frontend/
├── index.html                   # Overview Executive Dashboard & Metrics
├── assets/logo.svg              # FACEGUARD AI Vector Shield Mark
├── css/styles.css               # Enterprise Light Design Tokens & Styling
├── js/
│   ├── api.js                   # Centralized ApiClient with timeouts & headers
│   ├── camera.js                # HTML5 MediaDevices & Canvas frame extraction
│   ├── components.js            # Light sidebar, system status & toast alerts
│   ├── config.js                # Tenant configurations & localStorage store
│   ├── dashboard.js             # Overview analytics & recent sessions table
│   ├── history.js               # Filterable & searchable audit table
│   ├── monitoring.js            # Real-time proctoring HUD & live canvas engine
│   ├── registration.js          # Selfie capture, validation & dynamic ID gen
│   ├── session-details.js       # Forensic breakdown & Matplotlib chart preview
│   └── settings.js              # Sampling interval & camera switcher
└── pages/
    ├── history.html             # Audit History Page
    ├── monitor.html             # Live Proctoring Room
    ├── register.html            # Candidate Baseline Enrollment
    ├── session-details.html     # Forensic Deep-Dive View
    └── settings.html            # Configuration & Settings
```

### Key UI Features

* **High-Contrast Light Theme**: Slate-50 background (`#f8fafc`), clean white cards (`#ffffff`), Slate-900 typography (`#0f172a`), and Indigo accents (`#4f46e5`).
* **Instant ID Randomization**: Registration page automatically generates fresh, distinct Candidate IDs and Interview IDs, with a "🎲 Generate New IDs" button to prevent duplicate test entries.
* **Visible Session UUIDs & Candidate IDs**: Clean font-mono styling ensures UUIDs, Candidate IDs, and violation badges remain 100% visible across all displays without needing hover cursors.
* **Real-Time Proctoring HUD**: Overlays bounding boxes, facial landmark tracking, and real-time cosine distance directly onto the live webcam video feed.
* **Live Violation Counters**: Displays incrementing counters for `Identity Mismatch`, `Multiple Faces`, `Face Absent`, and `Face Occlusion`.
* **High-Visibility Anomaly Banner**: Alerts the proctor immediately with a prominent warning banner when sustained anomalies occur.
* **Unified Risk Score Capsules**: Complete, rounded status capsules displaying exact numerical risk scores alongside color-coded severity pills (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
* **10-Item Data Pagination**: Built-in, responsive pagination across Confirmed Fraud Events, Recent Proctoring Sessions, and Session History, with range indicators (`Showing X to Y of Z`), dynamic page counters (`Page 1 of N`), and interactive Previous/Next navigators.
* **Executive Telemetry Diagram**: Generates clean, publication-grade Matplotlib multi-panel graphics matching the enterprise light theme.

---

## 6. API Endpoints Reference

### Candidate Registration & Pre-Validation
* `POST /api/v1/fraud/sessions/validate-selfie`: Runs pre-enrollment quality and occlusion checks on uploaded selfie image.
* `POST /api/v1/fraud/sessions`: Registers candidate baseline, encrypts 128-d facial embedding, and returns session UUID.

### Live Proctoring & Analysis
* `POST /api/v1/fraud/sessions/{session_id}/analyze`: Ingests video frames from live canvas, checks for multi-face/mismatch/absence/occlusion, and returns instant proctoring telemetry.
* `GET /api/v1/fraud/sessions`: Lists all interview sessions belonging to the authenticated tenant.
* `GET /api/v1/fraud/sessions/{session_id}`: Retrieves real-time session metadata and status.
* `GET /api/v1/fraud/sessions/{session_id}/report`: Compiles complete forensic fraud report and audit summary.
* `GET /api/v1/fraud/sessions/{session_id}/events`: Retrieves chronological list of confirmed fraud events.
* `GET /api/v1/fraud/sessions/{session_id}/analytics/chart`: Generates 4-panel Matplotlib PNG telemetry diagram.

### System Observability
* `GET /healthz`: Kubernetes liveness probe.
* `GET /readyz`: Readiness probe verifying OpenCV ONNX model weights in memory.

---

## 7. Installation & Quickstart Guide

### Prerequisites
* Python 3.12+
* Web browser with webcam access (Chrome, Edge, Firefox, or Safari)
* PostgreSQL 16+ (Optional for local test runner; required for production persistence)

### 1. Clone & Set Up Virtual Environment

```bash
cd C:\Projects\fraud-detection-opencv

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt
```

### 2. Verify Pre-Trained Model Weights

The OpenCV YuNet detector and SFace recognizer ONNX files reside in `models/weights/`:
* `models/weights/face_detection_yunet_2023mar.onnx`
* `models/weights/face_recognition_sface_2021dec.onnx`

### 3. Launch the Application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser and navigate to:
**[http://localhost:8000](http://localhost:8000)**

---

## 8. Testing & Quality Verification

Run the full pytest suite covering computer vision pipelines, multi-tenant isolation, debounce state machines, and API endpoints:

```bash
pytest tests/ -v
```

**Test Suite Coverage Summary:**
* `tests/test_vision.py` — YuNet detection, SFace embeddings, cosine distance math.
* `tests/test_quality_and_occlusion.py` — Laplacian sharpness, luminance, landmark monotonicity.
* `tests/test_event_engine.py` — Temporal debouncing for multi-face and absence events.
* `tests/test_session_service.py` — Lifecycle transitions, biometric consent validation.
* `tests/test_multitenant_auth.py` — Tenant key hashing, tenant cross-discovery prevention.
* `tests/test_api_endpoints.py` — End-to-end FastAPI endpoint validation.
* `tests/test_ui_and_analytics.py` — Static UI page mounting, Matplotlib light theme generation.

```text
79 passed, 0 failed in 36.77s (100% Passing)
```

---

## License & Security Compliance
Licensed under the Apache 2.0 Enterprise License. Built in strict alignment with NIST FRVT guidelines, ISO/IEC 30107-3 presentation attack detection standards, and GDPR Article 9 biometric data processing mandates.
