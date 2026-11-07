"""
FACEGUARD AI — Production Biometric Fraud Detection Microservice
Pure FastAPI REST API Backend running on Hugging Face Spaces free tier.
Zero UI / Zero Gradio Frontend — Dedicated backend engine for Vercel/Web clients.
"""

import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

# Prepend our pure FastAPI routes so they resolve FIRST before Gradio catch-all
demo.app.router.routes = api_app.router.routes + demo.app.router.routes

if __name__ == "__main__":
    demo.launch()
