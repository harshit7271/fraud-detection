
# PROJECT: ENTERPRISE AI INTERVIEW
# FACE FRAUD DETECTION MICROSERVICE

## 1. ROLE AND RESPONSIBILITY

Act as a Senior Python Backend Engineer, Computer Vision
Engineer, AI/ML Architect, and DevOps Engineer.

You are responsible for designing and implementing a
production-oriented, scalable, secure, maintainable Face
Fraud Detection API for Blink Cloud Technologies.

This is an enterprise software project, not a tutorial,
academic prototype, or simple OpenCV demonstration.

Your implementation must follow professional software
engineering standards.

Do not sacrifice architecture, security, accuracy,
testability, or maintainability for faster implementation.

## 2. BUSINESS CONTEXT

Blink Cloud Technologies operates an AI-powered interview
platform.

The platform conducts video interviews with candidates.

Before an interview begins, the candidate captures a selfie.
During the interview, the platform monitors the candidate
through a webcam/video feed.

We need an independent Face Fraud Detection Microservice
that can be integrated into the existing interview platform.

The initial enterprise customers include:

- Alorica
- Sagility
- Mastek

The system must support multiple enterprise tenants using
one shared application and configurable tenant policies.

Do not hardcode company-specific business logic.

## 3. CORE OBJECTIVE

Build a standalone REST API that detects and records
suspicious identity and face-presence events during
AI-powered interviews.

The system must support:

1. Candidate selfie registration.
2. Face detection.
3. Face identity verification.
4. Multiple-face detection.
5. No-face detection.
6. Face tracking.
7. Image quality assessment.
8. Temporal fraud event detection.
9. Risk scoring.
10. Structured fraud reporting.

The system must distinguish suspicious signals from
confirmed fraud.

Never automatically classify a candidate as fraudulent
based solely on a single low-confidence frame.

## 4. MANDATORY TECHNOLOGY STACK

Language:
- Python 3.12+

Backend:
- FastAPI
- Uvicorn
- Pydantic v2
- SQLAlchemy 2.x
- Alembic

Computer Vision:
- OpenCV
- NumPy
- YuNet face detector
- SFace face recognition

Data:
- PostgreSQL
- Redis

Background Processing:
- Celery
- Redis or RabbitMQ as broker

Testing:
- Pytest
- HTTPX
- Locust

Infrastructure:
- Docker
- Docker Compose
- Kubernetes-ready architecture

Observability:
- Python structured logging
- Prometheus
- Grafana
- Sentry

Code Quality:
- Ruff
- Mypy
- Pytest coverage

Use stable, mutually compatible dependencies.
Pin dependencies and document model versions.

Verify model weights, licenses, and commercial-use
permissions before including them.

## 5. COMPUTER VISION REQUIREMENTS

### A. Face Detection

Use OpenCV FaceDetectorYN with YuNet.

Implement:

- Face bounding boxes.
- Facial landmarks.
- Face count.
- Confidence scores.
- Minimum face-size validation.
- Detection quality handling.

Handle:

- No face.
- One face.
- Multiple faces.
- Partially visible faces.
- Poor lighting.
- Blurry images.
- Different resolutions.

### B. Face Recognition

Use OpenCV FaceRecognizerSF with SFace.

Implement:

- Face alignment.
- Feature extraction.
- Embedding generation.
- Cosine similarity or supported comparison.
- Reference embedding comparison.
- Configurable identity thresholds.

Never hardcode an arbitrary production threshold.

Create an evaluation script to calibrate thresholds
using representative, labeled interview data.

Support uncertain and inconclusive results.

### C. Face Tracking

Implement lightweight tracking across consecutive frames.

Prevent:

- Duplicate events.
- Repeated unnecessary identity comparisons.
- Incorrect identity switching.
- False alerts from intermittent detections.

Maintain track IDs and temporal information.

### D. Image Quality

Create a dedicated quality assessment module.

Evaluate:

- Blur.
- Brightness.
- Contrast.
- Face size.
- Face visibility.
- Occlusion.

Poor image quality must not automatically become
an identity fraud event.

### E. Liveness / Presentation Attack Detection

Create an independent module interface for future
presentation-attack detection.

Do not claim that ordinary face detection or
face recognition proves liveness.

Do not implement fake liveness detection.

Return NOT_EVALUATED until a validated model or
approved challenge mechanism is integrated.

## 6. PRIMARY API DESIGN

Expose two primary business APIs.

### API 1: Register Interview Session

POST /api/v1/fraud/sessions

Responsibilities:

- Authenticate tenant.
- Validate candidate and interview IDs.
- Validate consent.
- Validate selfie file.
- Detect exactly one usable face.
- Evaluate image quality.
- Generate reference embedding.
- Securely store reference representation.
- Initialize interview monitoring session.

Return:

- session_id
- status
- registration result
- appropriate error details

### API 2: Analyze Interview Frames

POST /api/v1/fraud/sessions/{session_id}/analyze

Responsibilities:

- Authenticate request.
- Validate session and tenant ownership.
- Validate timestamps and frame payloads.
- Decode frames safely.
- Apply frame sampling limits.
- Detect faces.
- Track faces.
- Compare identities.
- Generate suspicious events.
- Update risk assessment.
- Persist results.

Support batched frame processing.

Do not accept an unlimited video file or unlimited
Base64 payload in a normal API request.

Use strict upload limits and configurable batch sizes.

Return structured processing results.

Design the service so that the API contract can later
support streaming or object-storage-based video ingestion.

Additional operational endpoints such as health,
readiness, metrics, and internal session management
are allowed. Keep the two business APIs as the
primary integration interface.

## 7. FRAUD EVENT ENGINE

Implement independent event types:

- MULTIPLE_FACES
- NO_FACE_DETECTED
- IDENTITY_MISMATCH
- FACE_ABSENT
- LOW_IMAGE_QUALITY
- FACE_OCCLUSION
- VIDEO_FEED_INTERRUPTED
- PRESENTATION_ATTACK_SUSPECTED

Every event should include:

- event_id
- session_id
- tenant_id
- event_type
- timestamp
- duration_ms where applicable
- confidence
- severity
- evidence reference where available
- processing metadata

Implement temporal confirmation.

A single detection should not necessarily create
a confirmed suspicious event.

Use configurable duration, persistence, and
cooldown rules.

Keep detection confidence separate from risk score.

## 8. RISK SCORING

Create a configurable scoring engine.

Do not hardcode business-specific risk rules.

Support tenant-specific configuration for:

- Identity mismatch thresholds.
- Multiple-face duration.
- Face absence duration.
- Event weights.
- Risk bands.
- Event cooldowns.

Generate:

- risk_score
- risk_level
- fraud_status
- fraud_events
- recommendation

Possible recommendations:

- NO_ACTION
- CONTINUE_MONITORING
- REVIEW_REQUIRED
- ESCALATE

These recommendations are risk-assessment outputs,
not automatic hiring decisions.

Store event-level evidence and scoring explanations.

## 9. MULTI-TENANT ARCHITECTURE

Support:

- Alorica
- Sagility
- Mastek
- Future enterprise tenants

Use tenant_id for all tenant-owned records.

Implement strict tenant-level authorization.

Create configurable tenant policies.

Never trust tenant_id supplied in a request without
validating it against the authenticated identity.

Prevent cross-tenant data access.

Support independent rate limits and configurable
retention policies.

## 10. DATABASE DESIGN

Use PostgreSQL and SQLAlchemy 2.x.

Design normalized, maintainable database models.

Include:

- tenants
- tenant_configs
- interview_sessions
- reference_faces
- fraud_events
- fraud_reports
- processing_jobs
- audit_logs

Use UUID identifiers where appropriate.

Include:

- Created timestamps.
- Updated timestamps.
- Proper indexes.
- Foreign keys.
- Unique constraints.
- Appropriate cascading behavior.
- Tenant-scoped queries.

Never store raw biometric information unnecessarily.

Encrypt sensitive reference representations.

Do not log raw images, embeddings, API keys, or
sensitive candidate information.

Use Alembic migrations.

## 11. ASYNCHRONOUS PROCESSING

Keep FastAPI request handling separate from
computationally expensive CV operations.

Use Celery workers for scalable background processing.

Use Redis or RabbitMQ as a broker.

Implement:

- Job status tracking.
- Retry policies.
- Idempotency.
- Failure handling.
- Queue monitoring.
- Backpressure.
- Graceful shutdown.

Load CV models once per worker process.

Do not load models on every API request.

Do not store shared session state in local process memory.

The application must support multiple API instances
and multiple CV worker instances.

## 12. SECURITY

Implement:

- OAuth2 client credentials or secure API-key
  authentication.
- Tenant authorization.
- HTTPS/TLS deployment.
- Request validation.
- Upload size limits.
- MIME and image decoding validation.
- Rate limiting.
- Secure secret management.
- Encryption at rest.
- Audit logging.
- CORS restrictions.
- Safe error handling.

Never expose internal stack traces to API clients.

Never allow one tenant to access another tenant's
sessions, events, or reference embeddings.

Implement configurable biometric-data retention
and deletion.

Ensure consent, purpose limitation, and applicable
privacy requirements are documented.

## 13. PERFORMANCE AND SCALABILITY

Design for enterprise-scale concurrent interviews.

Do not assume a fixed processing capacity.

Benchmark actual throughput before making capacity
claims.

Implement:

- Stateless FastAPI instances.
- Separate CV workers.
- Configurable frame sampling.
- Batch processing.
- Redis caching where appropriate.
- PostgreSQL connection pooling.
- Queue-based workload distribution.
- Horizontal scaling.
- Per-tenant rate limiting.
- CPU and memory monitoring.

Start with CPU-based inference.

Keep model execution abstracted so GPU acceleration
can be introduced later without rewriting the API.

Avoid unbounded queues and memory growth.

## 14. OBSERVABILITY

Implement structured JSON logging.

Include:

- Request ID.
- Correlation ID.
- Tenant ID.
- Session ID.
- Processing job ID.
- Model version.
- Processing duration.
- Event counts.
- Error codes.

Never include biometric images or embeddings in logs.

Expose:

- Liveness endpoint.
- Readiness endpoint.
- Prometheus metrics.

Monitor:

- Request latency.
- Processing latency.
- Frames processed.
- Frames per second.
- Queue depth.
- Worker failures.
- API error rate.
- CPU and memory.
- Database connections.

Integrate Sentry for exception tracking.

## 15. TESTING REQUIREMENTS

Use Pytest and HTTPX.

Create:

### Unit Tests

- Face detection.
- Face recognition.
- Similarity comparison.
- Image validation.
- Tracking.
- Fraud event generation.
- Risk scoring.
- Tenant configuration.

### Integration Tests

- Session creation.
- Selfie registration.
- Frame analysis.
- Database persistence.
- Redis integration.
- Background task processing.
- Tenant authorization.

### Security Tests

- Invalid authentication.
- Cross-tenant access.
- Invalid image payload.
- Oversized uploads.
- Malformed requests.
- Duplicate requests.
- Unauthorized session access.

### Performance Tests

Use Locust.

Benchmark:
- 10 concurrent sessions.
- 50 concurrent sessions.
- 100 concurrent sessions.
- 250 concurrent sessions.
- 500 concurrent sessions.

Measure:
- p50 latency.
- p95 latency.
- p99 latency.
- Requests per second.
- Frames per second.
- CPU usage.
- Memory usage.
- Queue latency.
- Error rate.

These are benchmark scenarios, not guaranteed capacity.

## 16. MODEL EVALUATION

Create scripts for:

- Detection evaluation.
- Face verification evaluation.
- Threshold calibration.
- False acceptance rate.
- False rejection rate.
- ROC analysis.
- Event-level precision and recall.
- False-positive analysis.

Evaluate across lighting, pose, camera quality,
occlusion, and demographic groups.

Document limitations and model versions.

Never claim production accuracy without measured
evaluation results.

## 17. PROJECT STRUCTURE

Use a modular structure:

app/
    main.py
    api/
        v1/
    core/
    schemas/
    services/
    vision/
    workers/
    db/
    middleware/

models/
tests/
    unit/
    integration/
    performance/
    security/

scripts/
migrations/
docker/
docs/

Include:

- requirements.txt
- pyproject.toml
- .env.example
- Dockerfile
- docker-compose.yml
- alembic.ini
- README.md
- pytest.ini

Keep routes, CV algorithms, database operations,
business logic, and configuration separate.

## 18. CODE QUALITY

Mandatory rules:

- Use type hints.
- Use Pydantic schemas.
- Use dependency injection.
- Follow clean architecture principles.
- Use async database operations where appropriate.
- Avoid unnecessary global state.
- Avoid circular imports.
- Avoid giant functions.
- Avoid monolithic files.
- Use custom exception classes.
- Use centralized configuration.
- Use environment variables for secrets.
- Use meaningful names.
- Document public interfaces.
- Write tests for important functionality.

Do not use placeholder implementations for
core fraud detection functionality.

## 19. DOCUMENTATION

Create:

1. README.md
2. ARCHITECTURE.md
3. API_SPECIFICATION.md
4. DATABASE_SCHEMA.md
5. DEPLOYMENT.md
6. SECURITY.md
7. MODEL_EVALUATION.md
8. LOAD_TEST_REPORT.md

Document all assumptions and limitations.

Include API request and response examples.

Provide local setup instructions.

Provide Docker deployment instructions.

## 20. DEVELOPMENT APPROACH

Do not generate the entire project blindly in one step.

Follow these stages:

PHASE 1:
Analyze requirements and propose the architecture.

PHASE 2:
Create project structure and dependencies.

PHASE 3:
Implement and test OpenCV face detection.

PHASE 4:
Implement and test SFace verification.

PHASE 5:
Implement tracking and fraud event engine.

PHASE 6:
Implement FastAPI endpoints.

PHASE 7:
Implement PostgreSQL and Redis.

PHASE 8:
Implement Celery workers.

PHASE 9:
Implement authentication and multi-tenancy.

PHASE 10:
Implement testing, monitoring, and performance
optimization.

PHASE 11:
Implement Docker and deployment documentation.

At the end of every phase:

1. Explain what was implemented.
2. List files created or modified.
3. Run relevant tests.
4. Show actual test results.
5. Identify remaining issues.
6. Explain the next phase.

Do not silently skip failed tests.

Do not claim a feature works without implementing
and testing it.

Before changing existing files, inspect them first.

Do not overwrite existing code without understanding
its purpose.

If an important architectural decision is unclear,
explain the options and recommend one.

## 21. DEFINITION OF DONE

The initial production-oriented MVP is complete when:

- A candidate can register a selfie.
- A reference face representation is securely stored.
- Interview frames can be analyzed in batches.
- Multiple faces can be detected.
- Identity mismatches can be evaluated.
- Face absence can be tracked.
- Fraud events are persisted.
- Risk reports are generated.
- Multiple tenants are isolated.
- Both primary APIs are documented.
- Authentication works.
- Automated tests pass.
- Docker deployment works.
- Load-test results are documented.
- Security and privacy limitations are documented.

Do not label the system enterprise-production-ready
until its real-world accuracy, security, load,
reliability, and deployment requirements have been
validated.

## FINAL INSTRUCTION

Begin with PHASE 1 only.

Do not start generating the entire codebase immediately.

First produce:

1. System architecture.
2. Component responsibilities.
3. Database architecture.
4. API contracts.
5. Computer vision pipeline.
6. Processing and scaling architecture.
7. Security architecture.
8. Development plan.
9. Technical risks and mitigation strategies.

Wait for architectural review before proceeding
to implementation.
