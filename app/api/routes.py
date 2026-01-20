"""
API Routes
"""
from fastapi import APIRouter
from app.api.endpoints import health, agent, image, report, summarize

router = APIRouter()

# Health check endpoints (root level)
router.include_router(health.router, tags=["health"])

# Agent endpoints (all under /agent prefix)
agent_router = APIRouter()
agent_router.include_router(agent.router, prefix="", tags=["agent"])
agent_router.include_router(image.router, prefix="/image", tags=["image"])
agent_router.include_router(report.router, prefix="/report", tags=["report"])
agent_router.include_router(summarize.router, prefix="/summarize", tags=["summarize"])

router.include_router(agent_router, prefix="/agent")
