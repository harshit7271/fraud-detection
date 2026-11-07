import pytest

from app.schemas.vision import (
    BoundingBox,
    FaceDetection,
    IdentityStatus,
    Landmarks,
    Point,
)
from app.vision.tracker import FaceTracker, compute_iou


def make_detection(x: int, y: int, w: int, h: int, conf: float = 0.95) -> FaceDetection:
    return FaceDetection(
        bbox=BoundingBox(x=x, y=y, width=w, height=h),
        landmarks=Landmarks(
            right_eye=Point(x=x + 10, y=y + 10),
            left_eye=Point(x=x + 30, y=y + 10),
            nose_tip=Point(x=x + 20, y=y + 20),
            right_mouth_corner=Point(x=x + 15, y=y + 30),
            left_mouth_corner=Point(x=x + 25, y=y + 30),
        ),
        confidence=conf,
        raw_face=[],
    )


@pytest.mark.unit
def test_compute_iou() -> None:
    box1 = BoundingBox(x=10, y=10, width=40, height=40)  # Area = 1600
    box2 = BoundingBox(x=10, y=10, width=40, height=40)  # Exact match
    assert compute_iou(box1, box2) == 1.0

    # Non-overlapping
    box3 = BoundingBox(x=100, y=100, width=40, height=40)
    assert compute_iou(box1, box3) == 0.0

    # Partial overlap
    box4 = BoundingBox(x=30, y=10, width=40, height=40)  # Overlap x in [30, 50], y in [10, 50] -> 20x40 = 800
    iou = compute_iou(box1, box4)
    # union = 1600 + 1600 - 800 = 2400. iou = 800 / 2400 = 0.3333
    assert pytest.approx(iou, abs=1e-3) == 0.3333


@pytest.mark.unit
def test_tracker_maintains_track_id() -> None:
    tracker = FaceTracker(iou_threshold=0.30)

    # Frame 1 at t=1000ms
    det1 = make_detection(100, 100, 60, 60)
    tracks_f1 = tracker.update([det1], timestamp_ms=1000)
    assert len(tracks_f1) == 1
    t1_id = tracks_f1[0].track_id
    assert tracks_f1[0].frames_tracked == 1

    # Frame 2 at t=1500ms (face moved slightly to 105, 102)
    det2 = make_detection(105, 102, 60, 60)
    tracks_f2 = tracker.update([det2], timestamp_ms=1500)
    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == t1_id
    assert tracks_f2[0].frames_tracked == 2


@pytest.mark.unit
def test_tracker_multiple_distinct_faces() -> None:
    tracker = FaceTracker()

    # Frame with 2 separate faces
    det_a = make_detection(50, 50, 60, 60)
    det_b = make_detection(300, 50, 60, 60)

    tracks = tracker.update([det_a, det_b], timestamp_ms=1000)
    assert len(tracks) == 2
    assert tracks[0].track_id != tracks[1].track_id
    assert tracker.active_track_count == 2


@pytest.mark.unit
def test_tracker_ages_out_stale_tracks() -> None:
    tracker = FaceTracker(max_missed_frames=2, max_time_gap_ms=2000)

    # Frame 1: Detection present
    tracker.update([make_detection(100, 100, 50, 50)], timestamp_ms=1000)
    assert tracker.active_track_count == 1

    # Frame 2: Missed
    tracker.update([], timestamp_ms=1500)
    assert tracker.active_track_count == 1

    # Frame 3: Missed
    tracker.update([], timestamp_ms=2000)
    assert tracker.active_track_count == 1

    # Frame 4: Missed (exceeds max_missed_frames=2)
    tracker.update([], timestamp_ms=2500)
    assert tracker.active_track_count == 0


@pytest.mark.unit
def test_tracker_caching_identity_flag() -> None:
    tracker = FaceTracker()
    det = make_detection(100, 100, 60, 60)
    tracks = tracker.update([det], timestamp_ms=1000)
    track = tracks[0]

    assert track.is_identity_cached is False
    track.verified_identity_status = IdentityStatus.MATCH
    assert track.is_identity_cached is True
