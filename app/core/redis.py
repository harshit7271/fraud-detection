from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger("app.core.redis")


class RedisService:
    """
    Manages active interview session caching, reference biometric representation caching,
    and ephemeral proctoring state in Redis with automatic TTL expiration.
    Falls back gracefully to an in-memory cache if standalone Redis is unreachable.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.REDIS_URL
        self._client: aioredis.Redis[bytes] | None = None
        self._fallback_memory_store: dict[str, tuple[bytes, float]] = {}

    async def get_client(self) -> aioredis.Redis[bytes]:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # Byte mode for biometric vectors
                socket_connect_timeout=2.0,
            )
        return self._client

    async def set_reference_embedding(
        self,
        session_id: str,
        embedding_bytes: bytes,
        ttl_seconds: int = 7200,  # 2 hours standard interview window
    ) -> bool:
        key = f"fraud:session:{session_id}:ref_face"
        try:
            client = await self.get_client()
            await client.set(key, embedding_bytes, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.warning(f"Redis cache write failed, using local memory fallback: {e}")
            import time
            self._fallback_memory_store[key] = (embedding_bytes, time.time() + ttl_seconds)
            return True

    async def get_reference_embedding(self, session_id: str) -> bytes | None:
        key = f"fraud:session:{session_id}:ref_face"
        try:
            client = await self.get_client()
            val = await client.get(key)
            if val is not None:
                return bytes(val)
        except Exception as e:
            logger.debug(f"Redis cache read failed, checking fallback: {e}")

        # Check memory store fallback
        import time
        if key in self._fallback_memory_store:
            data, expiry = self._fallback_memory_store[key]
            if time.time() < expiry:
                return data
            else:
                del self._fallback_memory_store[key]
        return None

    async def delete_session_cache(self, session_id: str) -> bool:
        key = f"fraud:session:{session_id}:ref_face"
        try:
            client = await self.get_client()
            await client.delete(key)
        except Exception:
            pass

        self._fallback_memory_store.pop(key, None)
        return True

    async def set_job_status(
        self,
        job_id: str,
        data: dict[str, Any],
        ttl_seconds: int = 86400,  # 24 hours
    ) -> bool:
        key = f"fraud:job:{job_id}"
        payload = json.dumps(data, default=str).encode("utf-8")
        try:
            client = await self.get_client()
            await client.set(key, payload, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.warning(f"Redis job write failed, fallback used: {e}")
            import time
            self._fallback_memory_store[key] = (payload, time.time() + ttl_seconds)
            return True

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        key = f"fraud:job:{job_id}"
        try:
            client = await self.get_client()
            raw = await client.get(key)
            if raw is not None:
                return json.loads(raw.decode("utf-8"))  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Redis job read failed, fallback used: {e}")

        import time
        if key in self._fallback_memory_store:
            data, expiry = self._fallback_memory_store[key]
            if time.time() < expiry:
                return json.loads(data.decode("utf-8"))  # type: ignore[no-any-return]
            else:
                del self._fallback_memory_store[key]
        return None

    async def ping(self) -> bool:
        """Pings Redis to test connectivity."""
        try:
            client = await self.get_client()
            return bool(await client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


redis_service = RedisService()


def get_redis_service() -> RedisService:
    return redis_service
