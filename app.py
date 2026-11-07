"""
FACEGUARD AI — Production Biometric Fraud Detection Microservice
Pure FastAPI REST API Backend running on Hugging Face Spaces free tier.
Zero UI / Zero Gradio Frontend — Dedicated backend engine for Vercel/Web clients.
"""

from typing import Any

import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware import Middleware

from app.api.v1.endpoints.health import health_check, readiness_check
from app.api.v1.endpoints.metrics import prometheus_metrics
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging import StructuredLoggingMiddleware

# Initialize production configuration
settings = get_settings()

# Build dedicated backend FastAPI application (Zero frontend UI)
api_app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise biometric face fraud detection and proctoring microservice.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for Vercel and all external frontend domains
api_app.add_middleware(StructuredLoggingMiddleware)
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register enterprise exception handlers
register_exception_handlers(api_app)


# Root JSON endpoint for pure backend microservice
@api_app.get("/", response_class=JSONResponse, tags=["Service"])
def service_root() -> JSONResponse:
    """Returns microservice health, version, and operational endpoint directory."""
    return JSONResponse(
        content={
            "service": settings.APP_NAME,
            "status": "online",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "endpoints": {
                "swagger_docs": "/docs",
                "redoc": "/redoc",
                "health_probe": "/healthz",
                "readiness_probe": "/readyz",
                "prometheus_metrics": "/metrics",
                "api_v1_prefix": "/api/v1",
                "sessions_api": "/api/v1/fraud/sessions",
            },
        }
    )


# Operational health and observability routes
api_app.add_api_route("/healthz", health_check, methods=["GET"], tags=["Health"])
api_app.add_api_route("/readyz", readiness_check, methods=["GET"], tags=["Health"])
api_app.add_api_route("/metrics", prometheus_metrics, methods=["GET"], tags=["Observability"])

# Include core fraud detection and session proctoring API router
api_app.include_router(api_v1_router)


# Pure API ASGI Proxy Middleware: intercepts all API/health/docs requests before Gradio
class PureApiAsgiMiddleware:
    """Zero-overhead ASGI proxy routing API requests directly to the FastAPI microservice."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            clean_path = path.rstrip("/") or "/"

            # Pass internal Gradio worker routes if any
            if path.startswith("/_gradio") or path.startswith("/gradio_api"):
                await self.app(scope, receive, send)
                return

            # Pure backend microservice endpoints: root, health, docs, metrics, and API routes
            if (
                clean_path == "/"
                or clean_path.startswith("/api")
                or clean_path.startswith("/docs")
                or clean_path.startswith("/redoc")
                or clean_path.startswith("/openapi.json")
                or clean_path in ["/healthz", "/readyz", "/metrics"]
            ):
                await api_app(scope, receive, send)
                return

        await self.app(scope, receive, send)


# Monkeypatch Gradio App.create_app so that any runner (CLI, Python, Uvicorn) injects PureApiAsgiMiddleware
_orig_create_app = gr.routes.App.create_app


def _custom_create_app(blocks: Any, app: Any = None, app_kwargs: Any = None, *args: Any, **kwargs: Any) -> Any:
    ak = dict(app_kwargs or {})
    existing_mw = list(ak.get("middleware") or [])
    ak["middleware"] = [Middleware(PureApiAsgiMiddleware)] + existing_mw
    return _orig_create_app(blocks, app, ak, *args, **kwargs)


gr.routes.App.create_app = staticmethod(_custom_create_app)


# ZeroGPU hardware compatibility hook
try:
    import spaces  # type: ignore[import-untyped]

    @spaces.GPU
    def _zero_gpu_worker() -> None:
        pass
except Exception:
    pass

# Gradio container runner compatibility for Hugging Face Spaces free tier
with gr.Blocks(title="FaceGuard AI Backend API") as demo:
    pass

# Attach ASGI proxy middleware to default Gradio instance
demo.app.add_middleware(PureApiAsgiMiddleware)

if __name__ == "__main__":
    demo.launch(app_kwargs={"middleware": [Middleware(PureApiAsgiMiddleware)]})
