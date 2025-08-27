from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .core.logger import setup_logger

# ===== Global Variables =====
logger: Any = None


async def initialize_services():
    """Initialize minimal services for API"""
    global logger
    if logger is None:
        logger = setup_logger("charging_predictor", level="INFO")

    logger.info("Initializing services...")
    try:
        # API routes가 main을 참조할 수 있도록 설정
        from .api.routes import set_main_module

        set_main_module(sys.modules[__name__])
        logger.info("Main module reference set for routes")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise


async def shutdown_services():
    """Cleanup services"""
    global logger
    if logger:
        logger.info("Services shut down successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global logger
    if logger is None:
        logger = setup_logger("charging_predictor", level="INFO")

    logger.info("=== Starting EV Charging Station Peak Predictor ===")
    try:
        await initialize_services()
        logger.info("Startup completed")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    yield
    logger.info("=== Shutting down ===")
    await shutdown_services()


def setup_routes():
    """Setup routes and middleware"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=86400,
    )

    from .api.routes import api_router

    app.include_router(api_router, prefix="/api")
    if logger:
        logger.info("Routes configured")


# ===== FastAPI App =====
app = FastAPI(title="EV Charging Station Peak Predictor", version="1.0.0", lifespan=lifespan)

logger = setup_logger("charging_predictor", level="INFO")
setup_routes()


# 프리플라이트 로깅(디버그용)
@app.middleware("http")
async def log_cors(request: Request, call_next):
    if request.method == "OPTIONS":
        logger.info(
            f"Preflight - Origin={request.headers.get('origin')} "
            f"ACRM={request.headers.get('access-control-request-method')} "
            f"ACRH={request.headers.get('access-control-request-headers')}"
        )
    return await call_next(request)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/")
async def root():
    return {
        "message": "EV Charging Station Peak Predictor API",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
        "api": "/api",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
