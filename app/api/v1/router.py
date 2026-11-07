from fastapi import APIRouter

from app.api.v1.endpoints import analytics, analyze, health, jobs, metrics, sessions

api_v1_router = APIRouter()

# Primary Business APIs
api_v1_router.include_router(sessions.router)
api_v1_router.include_router(analyze.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(analytics.router)

# Operational & Diagnostic APIs
api_v1_router.include_router(health.router)
api_v1_router.include_router(metrics.router)
