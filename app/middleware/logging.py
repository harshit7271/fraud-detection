import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import record_request_metrics

logger = logging.getLogger("app.middleware.access")
UUID_PATTERN = re.compile(r"/[0-9a-fA-F-]{36}")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware providing:
    1. Distributed request tracing with X-Correlation-ID / X-Request-ID propagation.
    2. Zero-biometric structured JSON access logging.
    3. Low-latency Prometheus HTTP metric instrumentation with normalized path templates.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 1. Correlation & Request ID
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

        # 2. Extract tenant hint safely from headers (without logging secrets)
        tenant_key = request.headers.get("X-Tenant-Key")
        tenant_id = request.headers.get("X-Tenant-Id") or "anonymous"
        if tenant_key:
            if "enterprise-a" in tenant_key or "alorica" in tenant_key:
                tenant_id = "enterprise-a"
            elif "enterprise-b" in tenant_key or "sagility" in tenant_key:
                tenant_id = "enterprise-b"
            elif "enterprise-c" in tenant_key or "mastek" in tenant_key:
                tenant_id = "enterprise-c"
            elif not tenant_id or tenant_id == "anonymous":
                tenant_id = "tenant-auth"

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            raise
        finally:
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000, 2)

            # Metric recording with normalized path to prevent label cardinality explosion
            endpoint_path = request.url.path
            normalized_path = UUID_PATTERN.sub("/{id}", endpoint_path)

            record_request_metrics(
                method=request.method,
                endpoint=normalized_path,
                status_code=status_code,
                duration=duration_s,
                tenant_id=tenant_id,
            )

            # Structured JSON access record (guaranteed biometric-free)
            log_record = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": endpoint_path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "tenant_id": tenant_id,
                "client_ip": request.client.host if request.client else "unknown",
            }
            logger.info(json.dumps(log_record))

        # Attach correlation ID and request ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id
        return response
