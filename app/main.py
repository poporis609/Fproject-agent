"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings
from app.core.startup import startup_handler

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Diary Orchestrator Agent API"
)

# Startup event
@app.on_event("startup")
async def startup():
    await startup_handler()

# Include routers
app.include_router(router)
