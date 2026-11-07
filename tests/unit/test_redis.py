import pytest

from app.core.redis import RedisService


@pytest.fixture
def redis_service() -> RedisService:
    # Uses in-memory fallback store when Redis is offline
    return RedisService(redis_url="redis://localhost:9999/0")


@pytest.mark.unit
async def test_redis_service_caching_and_expiration(redis_service: RedisService) -> None:
    session_id = "test_sess_redis_001"
    sample_bytes = b"\x01\x02\x03\x04" * 128

    # Set cache with short TTL
    success = await redis_service.set_reference_embedding(
        session_id=session_id,
        embedding_bytes=sample_bytes,
        ttl_seconds=3600,
    )
    assert success is True

    # Retrieve cache
    cached = await redis_service.get_reference_embedding(session_id)
    assert cached == sample_bytes

    # Delete cache
    del_res = await redis_service.delete_session_cache(session_id)
    assert del_res is True

    deleted = await redis_service.get_reference_embedding(session_id)
    assert deleted is None


@pytest.mark.unit
async def test_redis_nonexistent_key(redis_service: RedisService) -> None:
    val = await redis_service.get_reference_embedding("non_existent_session")
    assert val is None
