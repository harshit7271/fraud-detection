from dataclasses import dataclass

from app.schemas.vision import (
    BoundingBox,
    FaceDetection,
    FaceEmbedding,
    IdentityStatus,
    Landmarks,
)


def compute_iou(box_a: BoundingBox, box_b: BoundingBox) -> float:
    """Computes Intersection-over-Union (IoU) between two bounding boxes."""
    x_left = max(box_a.x, box_b.x)
    y_top = max(box_a.y, box_b.y)
    x_right = min(box_a.x2, box_b.x2)
    y_bottom = min(box_a.y2, box_b.y2)

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    area_a = box_a.area
    area_b = box_b.area
    union_area = area_a + area_b - intersection_area

    if union_area <= 0:
        return 0.0

    return float(intersection_area / union_area)


@dataclass
class TrackedFace:
    track_id: int
    bbox: BoundingBox
    landmarks: Landmarks
    confidence: float
    raw_face: list[float]
    first_seen_timestamp_ms: int
    last_seen_timestamp_ms: int
    embedding: FaceEmbedding | None = None
    verified_identity_status: IdentityStatus | None = None
    similarity_score: float | None = None
    frames_tracked: int = 1
    missed_frames: int = 0

    @property
    def is_identity_cached(self) -> bool:
        """Returns True if this face track has already had its identity confirmed."""
        return self.verified_identity_status is not None


class FaceTracker:
    """
    Lightweight temporal face tracker that associates detections across consecutive frames
    using bounding-box Intersection-over-Union (IoU) and spatial proximity.
    Prevents duplicate alerts, false switches, and redundant identity recalculations.
    """

    def __init__(
        self,
        iou_threshold: float = 0.35,
        max_missed_frames: int = 5,
        max_time_gap_ms: int = 3000,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self.max_time_gap_ms = max_time_gap_ms

        self._next_track_id: int = 1
        self._tracks: dict[int, TrackedFace] = {}

    @property
    def active_track_count(self) -> int:
        return len(self._tracks)

    def reset(self) -> None:
        """Resets tracker state between different interview sessions."""
        self._tracks.clear()
        self._next_track_id = 1

    def update(
        self,
        detections: list[FaceDetection],
        timestamp_ms: int,
    ) -> list[TrackedFace]:
        """
        Updates active tracks with detections from the current frame.
        Associates detections with active tracks, creates new tracks for unassigned detections,
        and ages out expired tracks.
        """
        # Purge stale tracks exceeding max time gap
        expired_ids = [
            t_id
            for t_id, track in self._tracks.items()
            if (timestamp_ms - track.last_seen_timestamp_ms) > self.max_time_gap_ms
            or track.missed_frames >= self.max_missed_frames
        ]
        for t_id in expired_ids:
            del self._tracks[t_id]

        active_track_ids = list(self._tracks.keys())
        assigned_tracks: set[int] = set()
        matched_results: list[TrackedFace] = []

        # Greedy IoU assignment between incoming detections and existing tracks
        for detection in detections:
            best_iou = 0.0
            best_track_id: int | None = None

            for t_id in active_track_ids:
                if t_id in assigned_tracks:
                    continue
                track = self._tracks[t_id]
                iou = compute_iou(detection.bbox, track.bbox)
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_track_id = t_id

            if best_track_id is not None:
                # Match found: update existing track
                track = self._tracks[best_track_id]
                track.bbox = detection.bbox
                track.landmarks = detection.landmarks
                track.confidence = detection.confidence
                track.raw_face = detection.raw_face
                track.last_seen_timestamp_ms = timestamp_ms
                track.frames_tracked += 1
                track.missed_frames = 0

                assigned_tracks.add(best_track_id)
                matched_results.append(track)
            else:
                # New face detected: initialize a new track
                new_track_id = self._next_track_id
                self._next_track_id += 1

                new_track = TrackedFace(
                    track_id=new_track_id,
                    bbox=detection.bbox,
                    landmarks=detection.landmarks,
                    confidence=detection.confidence,
                    raw_face=detection.raw_face,
                    first_seen_timestamp_ms=timestamp_ms,
                    last_seen_timestamp_ms=timestamp_ms,
                    frames_tracked=1,
                    missed_frames=0,
                )
                self._tracks[new_track_id] = new_track
                matched_results.append(new_track)

        # Increment missed_frames for tracks that received no detection this frame
        for t_id in active_track_ids:
            if t_id not in assigned_tracks:
                self._tracks[t_id].missed_frames += 1

        return matched_results
