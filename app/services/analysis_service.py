import time

from app.core.exceptions import InvalidImageError
from app.core.metrics import (
    CV_INFERENCE_DURATION_SECONDS,
    record_frames_processed,
    record_fraud_event,
)
from app.schemas.frame import (
    AnalyzeFramesRequest,
    AnalyzeFramesResponse,
    FrameAnalysisResult,
    FrameDetectionDetail,
)
from app.schemas.fraud import FraudEvent
from app.schemas.vision import IdentityMatchResult, IdentityStatus
from app.services.session_service import SessionService, get_session_service
from app.vision.detector import FaceDetector
from app.vision.liveness import HybridLivenessDetector, ILivenessDetector
from app.vision.quality import QualityAssessor
from app.vision.recognizer import FaceRecognizer
from app.vision.utils import decode_base64_image


class AnalysisService:
    """
    Orchestrates the frame analysis pipeline: decoding, quality assessment,
    face detection, multi-frame tracking, identity comparison against reference,
    and temporal fraud confirmation.
    """

    def __init__(
        self,
        session_service: SessionService | None = None,
        detector: FaceDetector | None = None,
        recognizer: FaceRecognizer | None = None,
        quality_assessor: QualityAssessor | None = None,
        liveness_detector: ILivenessDetector | None = None,
    ) -> None:
        self.session_service = session_service or get_session_service()
        self.detector = detector or FaceDetector()
        self.recognizer = recognizer or FaceRecognizer()
        self.quality_assessor = quality_assessor or QualityAssessor()
        self.liveness_detector = liveness_detector or HybridLivenessDetector()

    def analyze_batch(
        self,
        session_id: str,
        tenant_id: str,
        request: AnalyzeFramesRequest,
    ) -> AnalyzeFramesResponse:
        session = self.session_service.get_session(session_id, tenant_id)

        frame_results: list[FrameAnalysisResult] = []
        newly_confirmed_events: list[FraudEvent] = []

        for frame_item in request.frames:
            # 1. Decode frame
            try:
                image = decode_base64_image(frame_item.image_base64)
            except Exception as e:
                raise InvalidImageError(f"Failed to decode frame {frame_item.frame_id}: {e}") from e

            # 2. Face Detection
            t_det0 = time.perf_counter()
            detection_res = self.detector.detect(image)
            CV_INFERENCE_DURATION_SECONDS.labels(stage="detection").observe(time.perf_counter() - t_det0)

            # 3. Multi-Frame Tracking
            t_trk0 = time.perf_counter()
            tracked_faces = session.tracker.update(
                detections=detection_res.faces,
                timestamp_ms=frame_item.timestamp_ms,
            )
            CV_INFERENCE_DURATION_SECONDS.labels(stage="tracking").observe(time.perf_counter() - t_trk0)

            # 4. Quality Assessment
            t_qty0 = time.perf_counter()
            primary_face = detection_res.primary_face
            quality = self.quality_assessor.evaluate(image, primary_face)
            CV_INFERENCE_DURATION_SECONDS.labels(stage="quality").observe(time.perf_counter() - t_qty0)

            # 5. Identity Verification
            detection_details: list[FrameDetectionDetail] = []
            primary_identity_status: IdentityStatus | None = None
            primary_similarity_score: float | None = None

            if quality.is_acceptable and tracked_faces:
                for tracked in tracked_faces:
                    # Identity caching optimization: if already verified on steady track, re-use
                    if tracked.is_identity_cached and tracked.similarity_score is not None:
                        match_res = IdentityMatchResult(
                            status=tracked.verified_identity_status or IdentityStatus.UNCERTAIN,
                            similarity_score=tracked.similarity_score,
                            match_threshold=self.recognizer.default_match_threshold,
                            uncertain_threshold=self.recognizer.default_uncertain_threshold,
                        )
                    else:
                        # Extract and compare embedding against reference face
                        try:
                            t_rec0 = time.perf_counter()
                            # Reconstruct FaceDetection object for recognition
                            from app.schemas.vision import FaceDetection
                            det_obj = FaceDetection(
                                bbox=tracked.bbox,
                                landmarks=tracked.landmarks,
                                confidence=tracked.confidence,
                                raw_face=tracked.raw_face,
                            )
                            cur_emb = self.recognizer.extract_embedding(image, det_obj)
                            match_res = self.recognizer.verify(
                                target_embedding=cur_emb,
                                reference_embedding=session.reference_embedding,
                            )
                            CV_INFERENCE_DURATION_SECONDS.labels(stage="recognition_embedding").observe(
                                time.perf_counter() - t_rec0
                            )

                            # Cache verified status on the track
                            tracked.embedding = cur_emb
                            tracked.verified_identity_status = match_res.status
                            tracked.similarity_score = match_res.similarity_score
                        except Exception:
                            match_res = None

                    if match_res and primary_identity_status is None:
                        primary_identity_status = match_res.status
                        primary_similarity_score = match_res.similarity_score

                    detection_details.append(
                        FrameDetectionDetail(
                            track_id=tracked.track_id,
                            bbox=tracked.bbox,
                            detection_confidence=tracked.confidence,
                            identity_match=match_res,
                        )
                    )
            else:
                for tracked in tracked_faces:
                    tracked.verified_identity_status = None
                    tracked.similarity_score = None
                    detection_details.append(
                        FrameDetectionDetail(
                            track_id=tracked.track_id,
                            bbox=tracked.bbox,
                            detection_confidence=tracked.confidence,
                            identity_match=None,
                        )
                    )

            # 6. Temporal Event Evaluation
            primary_liveness = None
            if primary_face is not None:
                primary_liveness = self.liveness_detector.evaluate_liveness(
                    image=image,
                    face=primary_face,
                )

            events = session.event_engine.process_observation(
                timestamp_ms=frame_item.timestamp_ms,
                tracked_faces=tracked_faces,
                quality=quality,
                primary_identity_status=primary_identity_status,
                identity_similarity_score=primary_similarity_score,
                liveness=primary_liveness,
            )

            if events:
                newly_confirmed_events.extend(events)
                session.confirmed_events.extend(events)
                self.session_service.save_session_state(session.session_id)

            frame_results.append(
                FrameAnalysisResult(
                    frame_id=frame_item.frame_id,
                    timestamp_ms=frame_item.timestamp_ms,
                    faces_detected=len(tracked_faces),
                    quality=quality,
                    liveness=primary_liveness,
                    detections=detection_details,
                )
            )

        # 7. Compute updated session risk assessment
        latest_risk = session.latest_risk

        # 8. Record Prometheus pipeline metrics
        record_frames_processed(tenant_id, len(frame_results))
        for evt in newly_confirmed_events:
            record_fraud_event(tenant_id, evt.event_type.value, evt.severity.value)

        return AnalyzeFramesResponse(
            session_id=session.session_id,
            batch_id=request.batch_id,
            frames_processed=len(frame_results),
            frame_results=frame_results,
            confirmed_events=newly_confirmed_events,
            current_risk=latest_risk,
        )


analysis_service = AnalysisService()


def get_analysis_service() -> AnalysisService:
    return analysis_service
