import os
import time
import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db
from .logging_config import configure_logging
from .routers import callers, leads, webhook
from .services.realtime import connection_manager, AssignmentEventOut

configure_logging()
logger = logging.getLogger("bloc.http")

API_PREFIX = "/api"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bloc Sales CRM",
        version="0.1.0",
        description=(
            "Smart lead assignment CRM. Ingests leads from Google Sheets via webhook, "
            "assigns them using state-based Round Robin with daily caps, and streams "
            "updates to the dashboard over WebSocket."
        ),
        contact={"name": "Bloc Engineering"},
        license_info={"name": "MIT"},
    )

    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %s  (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    app.include_router(callers.router, prefix=API_PREFIX)
    app.include_router(leads.router, prefix=API_PREFIX)
    app.include_router(webhook.router, prefix=API_PREFIX)

    @app.websocket("/ws/dashboard")
    async def dashboard_ws(websocket: WebSocket, db: Session = Depends(get_db)):
        await connection_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)

    @app.get("/health", tags=["meta"])
    async def health():
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()

