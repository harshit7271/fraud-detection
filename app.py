"""
FACEGUARD AI — Production Biometric Fraud Detection Microservice
Pure FastAPI REST API Backend running on Hugging Face Spaces free tier.
Zero UI / Zero Gradio Frontend — Dedicated backend engine for Vercel/Web clients.
"""

import os

# Disable Gradio SvelteKit SSR Node proxy completely
os.environ["GRADIO_SSR_MODE"] = "False"

from typing import Any

import gradio as gr
import gradio.networking as net
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

# Bypass localhost probing check inside container environments
net.url_ok = lambda url: True

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


# Root JSON endpoint for pure backend microservice (supports both GET and HEAD for HF healthchecks)
@api_app.api_route("/", methods=["GET", "HEAD"], response_class=JSONResponse, tags=["Service"])
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
api_app.add_api_route("/healthz", health_check, methods=["GET", "HEAD"], tags=["Health"])
api_app.add_api_route("/readyz", readiness_check, methods=["GET", "HEAD"], tags=["Health"])
api_app.add_api_route("/metrics", prometheus_metrics, methods=["GET"], tags=["Observability"])

# Include core fraud detection and session proctoring API router
api_app.include_router(api_v1_router)


# Pure API ASGI Proxy Middleware: intercepts all HTTP traffic before Gradio
class PureApiAsgiMiddleware:
    """Zero-overhead ASGI proxy routing API requests directly to the FastAPI microservice."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")

            # Pass internal Gradio worker routes if any
            if path.startswith("/_gradio") or path.startswith("/gradio_api"):
                await self.app(scope, receive, send)
                return

            # All external traffic is routed exclusively to the pure FastAPI microservice
            await api_app(scope, receive, send)
            return

        await self.app(scope, receive, send)


# Monkeypatch Gradio App.create_app so that any runner (CLI, Python, Uvicorn, ZeroGPU) injects PureApiAsgiMiddleware
_orig_create_app = gr.routes.App.create_app


def _custom_create_app(blocks: Any, *args: Any, **kwargs: Any) -> Any:
    if "app_kwargs" in kwargs:
        ak = dict(kwargs["app_kwargs"] or {})
        existing_mw = list(ak.get("middleware") or [])
        ak["middleware"] = [Middleware(PureApiAsgiMiddleware)] + existing_mw
        kwargs["app_kwargs"] = ak
    elif len(args) >= 2:
        args_list = list(args)
        ak = dict(args_list[1] or {})
        existing_mw = list(ak.get("middleware") or [])
        ak["middleware"] = [Middleware(PureApiAsgiMiddleware)] + existing_mw
        args_list[1] = ak
        args = tuple(args_list)
    else:
        kwargs["app_kwargs"] = {"middleware": [Middleware(PureApiAsgiMiddleware)]}
    return _orig_create_app(blocks, *args, **kwargs)


gr.routes.App.create_app = staticmethod(_custom_create_app)

# Monkeypatch Blocks.launch to force ssr_mode=False and _frontend=False
_orig_launch = gr.Blocks.launch


def _custom_launch(self: Any, *args: Any, **kwargs: Any) -> Any:
    kwargs["ssr_mode"] = False
    kwargs["_frontend"] = False
    return _orig_launch(self, *args, **kwargs)


gr.Blocks.launch = _custom_launch


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
    demo.launch(
        ssr_mode=False,
        _frontend=False,
        app_kwargs={"middleware": [Middleware(PureApiAsgiMiddleware)]},
    )
