import uuid

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.crypto import BiometricCipher
from app.db.base import Base
from app.db.models.tenant import Tenant
from app.db.repositories.session_repo import SessionRepository
from app.schemas.vision import FaceEmbedding


@pytest.fixture
async def async_db_session() -> AsyncSession:
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.integration
async def test_session_repository_crud_and_tenant_isolation(async_db_session: AsyncSession) -> None:
    repo = SessionRepository(async_db_session)
    cipher = BiometricCipher()

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    session_id = uuid.uuid4()

    # 1. Create Tenant A
    tenant_a = Tenant(
        id=tenant_a_id,
        slug="enterprise-a-test",
        name="Enterprise A",
        api_key_hash="hash_123",
    )
    async_db_session.add(tenant_a)
    await async_db_session.flush()

    # 2. Create Interview Session under Tenant A
    created_session = await repo.create_session(
        session_id=session_id,
        tenant_id=tenant_a_id,
        candidate_id="cand_101",
        interview_id="int_505",
        consent_recorded=True,
    )
    assert created_session.id == session_id
    assert created_session.status == "INITIALIZED"

    # 3. Encrypt and store ReferenceFace representation
    original_embedding = FaceEmbedding(vector=[float(i) * 0.005 for i in range(128)])
    raw_emb_bytes = original_embedding.to_bytes()
    encrypted_data = cipher.encrypt(raw_emb_bytes)

    stored_ref = await repo.store_reference_face(
        session_id=session_id,
        tenant_id=tenant_a_id,
        encrypted_embedding=encrypted_data.ciphertext,
        encryption_iv=encrypted_data.iv,
        key_version=encrypted_data.key_version,
        quality_score=0.95,
        bbox_metadata={"x": 100, "y": 100, "width": 200, "height": 200},
    )
    assert stored_ref.session_id == session_id

    # 4. Decrypt and verify exact biometric floating-point roundtrip
    retrieved_ref = await repo.get_reference_face(session_id, tenant_a_id)
    assert retrieved_ref is not None
    decrypted_bytes = cipher.decrypt(retrieved_ref.encrypted_embedding, retrieved_ref.encryption_iv)
    restored_embedding = FaceEmbedding.from_bytes(decrypted_bytes)
    assert np.allclose(restored_embedding.vector, original_embedding.vector, atol=1e-6)

    # 5. Record Fraud Event
    event = await repo.record_fraud_event(
        session_id=session_id,
        tenant_id=tenant_a_id,
        event_type="MULTIPLE_FACES",
        timestamp_ms=1730000000,
        duration_ms=2500,
        confidence=0.98,
        severity="HIGH",
        evidence_metadata={"faces": 2},
    )
    assert event.event_type == "MULTIPLE_FACES"

    events = await repo.list_fraud_events(session_id, tenant_a_id)
    assert len(events) == 1

    # 6. Verify Tenant Isolation (Tenant B querying Tenant A's session returns None)
    isolated_session = await repo.get_session(session_id, tenant_b_id)
    assert isolated_session is None

    isolated_ref = await repo.get_reference_face(session_id, tenant_b_id)
    assert isolated_ref is None

    isolated_events = await repo.list_fraud_events(session_id, tenant_b_id)
    assert len(isolated_events) == 0
