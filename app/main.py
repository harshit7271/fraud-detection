from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from app.api.v1.endpoints.health import health_check, readiness_check
from app.api.v1.endpoints.metrics import prometheus_metrics
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging import StructuredLoggingMiddleware

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_HTML_PATH = FRONTEND_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup actions: pre-validate configurations
    _ = get_settings()
    yield
    # Shutdown actions


def create_application() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS & Tracing / Logging Middleware
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security exception handlers
    register_exception_handlers(app)

    # Top-level operational endpoints for Kubernetes & Prometheus
    app.add_api_route("/healthz", health_check, methods=["GET"], tags=["Health"])
    app.add_api_route("/readyz", readiness_check, methods=["GET"], tags=["Health"])
    app.add_api_route("/metrics", prometheus_metrics, methods=["GET"], tags=["Observability & Metrics"])

    # Static files mounting for frontend
    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
        if (FRONTEND_DIR / "css").exists():
            app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
        if (FRONTEND_DIR / "js").exists():
            app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
        if (FRONTEND_DIR / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
        if (FRONTEND_DIR / "pages").exists():
            app.mount("/pages", StaticFiles(directory=str(FRONTEND_DIR / "pages")), name="pages")

    # Embedded UI Dashboard routes
    @app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/ui", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/index.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_dashboard_ui() -> HTMLResponse:
        if INDEX_HTML_PATH.exists():
            return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>FACEGUARD AI Face Fraud Detection Dashboard Online</h1>")

    # Individual page routes for direct URL navigation
    @app.get("/register", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/pages/register.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_register_page() -> HTMLResponse:
        p = FRONTEND_DIR / "pages" / "register.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Not Found</h1>")

    @app.get("/monitor", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/pages/monitor.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_monitor_page() -> HTMLResponse:
        p = FRONTEND_DIR / "pages" / "monitor.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Not Found</h1>")

    @app.get("/history", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/pages/history.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_history_page() -> HTMLResponse:
        p = FRONTEND_DIR / "pages" / "history.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Not Found</h1>")

    @app.get("/session-details", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/pages/session-details.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_session_details_page() -> HTMLResponse:
        p = FRONTEND_DIR / "pages" / "session-details.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Not Found</h1>")

    @app.get("/settings", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/pages/settings.html", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_settings_page() -> HTMLResponse:
        p = FRONTEND_DIR / "pages" / "settings.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Not Found</h1>")

    @app.get("/performance-report", response_class=HTMLResponse, tags=["Dashboard UI"])
    def serve_performance_report() -> HTMLResponse:
        p = FRONTEND_DIR / "performance-report.html"
        return HTMLResponse(content=p.read_text(encoding="utf-8") if p.exists() else "<h1>Performance Report Not Found</h1>")

    # API v1 routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
