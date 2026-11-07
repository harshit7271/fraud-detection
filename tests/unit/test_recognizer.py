import numpy as np
import pytest

from app.core.exceptions import InvalidImageError, ModelLoadError, VisionError
from app.schemas.vision import (
    FaceEmbedding,
    IdentityStatus,
)
from app.vision.detector import FaceDetector
from app.vision.recognizer import FaceRecognizer
from tests.unit.test_detector import create_synthetic_face


@pytest.fixture
def recognizer() -> FaceRecognizer:
    return FaceRecognizer()


@pytest.fixture
def detector() -> FaceDetector:
    return FaceDetector(score_threshold=0.30, min_face_size=30)


@pytest.mark.unit
def test_recognizer_invalid_model_path() -> None:
    with pytest.raises(ModelLoadError, match="not found at path"):
        FaceRecognizer(model_path="non_existent_sface.onnx")


@pytest.mark.unit
def test_face_alignment(detector: FaceDetector, recognizer: FaceRecognizer) -> None:
    img = create_synthetic_face(320, 240)
    det_res = detector.detect(img)
    assert det_res.count >= 1

    face = det_res.faces[0]
    aligned = recognizer.align_face(img, face)
    assert isinstance(aligned, np.ndarray)
    assert aligned.shape == (112, 112, 3)
    assert aligned.dtype == np.uint8


@pytest.mark.unit
def test_face_alignment_invalid_detection(recognizer: FaceRecognizer) -> None:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    from app.schemas.vision import BoundingBox, FaceDetection, Landmarks, Point

    dummy_face = FaceDetection(
        bbox=BoundingBox(x=0, y=0, width=50, height=50),
        landmarks=Landmarks(
            right_eye=Point(x=10, y=10),
            left_eye=Point(x=30, y=10),
            nose_tip=Point(x=20, y=25),
            right_mouth_corner=Point(x=15, y=35),
            left_mouth_corner=Point(x=25, y=35),
        ),
        confidence=0.9,
        raw_face=[],  # Missing required raw landmarks
    )
    with pytest.raises(VisionError, match="lacks valid raw landmark"):
        recognizer.align_face(img, dummy_face)


@pytest.mark.unit
def test_extract_embedding(detector: FaceDetector, recognizer: FaceRecognizer) -> None:
    img = create_synthetic_face(320, 240)
    det_res = detector.detect(img)
    face = det_res.faces[0]

    embedding = recognizer.extract_embedding(img, face)
    assert isinstance(embedding, FaceEmbedding)
    assert embedding.dimension == 128
    assert len(embedding.vector) == 128

    arr = embedding.to_numpy()
    assert arr.shape == (128,)
    assert arr.dtype == np.float32

    # Verify L2 normalization
    norm = np.linalg.norm(arr)
    assert pytest.approx(norm, abs=1e-4) == 1.0


@pytest.mark.unit
def test_extract_from_aligned_invalid(recognizer: FaceRecognizer) -> None:
    with pytest.raises(InvalidImageError, match="must be a 112x112x3"):
        recognizer.extract_from_aligned(np.zeros((100, 100, 3), dtype=np.uint8))


@pytest.mark.unit
def test_embedding_serialization_roundtrip() -> None:
    original_vector = [float(i) * 0.01 for i in range(128)]
    emb = FaceEmbedding(vector=original_vector)

    raw_bytes = emb.to_bytes()
    assert len(raw_bytes) == 512

    restored = FaceEmbedding.from_bytes(raw_bytes)
    assert restored.dimension == 128
    assert np.allclose(emb.vector, restored.vector, atol=1e-6)

    # Invalid byte length
    with pytest.raises(ValueError, match="Expected exactly 512 bytes"):
        FaceEmbedding.from_bytes(b"short_bytes")


@pytest.mark.unit
def test_compute_similarity_known_vectors(recognizer: FaceRecognizer) -> None:
    # Identical vectors
    v1 = np.ones(128, dtype=np.float32)
    v1 = v1 / np.linalg.norm(v1)
    sim_self = recognizer.compute_similarity(v1, v1)
    assert pytest.approx(sim_self, abs=1e-4) == 1.0

    # Opposite vectors
    sim_opp = recognizer.compute_similarity(v1, -v1)
    assert pytest.approx(sim_opp, abs=1e-4) == -1.0

    # Orthogonal vectors
    v_ortho1 = np.zeros(128, dtype=np.float32)
    v_ortho1[0] = 1.0
    v_ortho2 = np.zeros(128, dtype=np.float32)
    v_ortho2[1] = 1.0
    sim_ortho = recognizer.compute_similarity(v_ortho1, v_ortho2)
    assert pytest.approx(sim_ortho, abs=1e-4) == 0.0


@pytest.mark.unit
def test_verify_identity_boundaries(recognizer: FaceRecognizer) -> None:
    ref = np.zeros(128, dtype=np.float32)
    ref[0] = 1.0  # Unit vector along axis 0

    # 1. Definite Match: Target identical to reference
    target_match = ref.copy()
    res_match = recognizer.verify(
        target_embedding=target_match,
        reference_embedding=ref,
        match_threshold=0.40,
        uncertain_threshold=0.25,
    )
    assert res_match.status == IdentityStatus.MATCH
    assert res_match.is_match is True
    assert res_match.is_uncertain is False
    assert res_match.is_mismatch is False
    assert res_match.similarity_score == 1.0

    # 2. Uncertain: Cosine ~ 0.30
    # Construct vector with dot product 0.30 with ref
    target_uncertain = np.zeros(128, dtype=np.float32)
    target_uncertain[0] = 0.30
    target_uncertain[1] = np.sqrt(1.0 - 0.30**2)
    res_uncertain = recognizer.verify(
        target_embedding=target_uncertain,
        reference_embedding=ref,
        match_threshold=0.40,
        uncertain_threshold=0.25,
    )
    assert res_uncertain.status == IdentityStatus.UNCERTAIN
    assert res_uncertain.is_uncertain is True
    assert res_uncertain.is_match is False
    assert res_uncertain.is_mismatch is False
    assert pytest.approx(res_uncertain.similarity_score, abs=1e-3) == 0.30

    # 3. Mismatch: Cosine ~ 0.10 (below uncertain_threshold)
    target_mismatch = np.zeros(128, dtype=np.float32)
    target_mismatch[0] = 0.10
    target_mismatch[1] = np.sqrt(1.0 - 0.10**2)
    res_mismatch = recognizer.verify(
        target_embedding=target_mismatch,
        reference_embedding=ref,
        match_threshold=0.40,
        uncertain_threshold=0.25,
    )
    assert res_mismatch.status == IdentityStatus.MISMATCH
    assert res_mismatch.is_mismatch is True
    assert res_mismatch.is_match is False
    assert res_mismatch.is_uncertain is False
    assert pytest.approx(res_mismatch.similarity_score, abs=1e-3) == 0.10


@pytest.mark.unit
def test_verify_invalid_thresholds(recognizer: FaceRecognizer) -> None:
    ref = np.ones(128, dtype=np.float32)
    with pytest.raises(ValueError, match="cannot be greater than match_threshold"):
        recognizer.verify(ref, ref, match_threshold=0.30, uncertain_threshold=0.40)


@pytest.mark.unit
def test_compute_similarity_invalid_dimension(recognizer: FaceRecognizer) -> None:
    bad_dim = np.ones(64, dtype=np.float32)
    valid_dim = np.ones(128, dtype=np.float32)
    with pytest.raises(ValueError, match="must be 128-dimensional"):
        recognizer.compute_similarity(bad_dim, valid_dim)
