import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db
from .routers import callers, leads, webhook
from .services.realtime import connection_manager, AssignmentEventOut


API_PREFIX = "/api"


def create_app() -> FastAPI:
    app = FastAPI(title="Bloc Sales CRM", version="0.1.0")

    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(callers.router, prefix=API_PREFIX)
    app.include_router(leads.router, prefix=API_PREFIX)
    app.include_router(webhook.router, prefix=API_PREFIX)

    @app.websocket("/ws/dashboard")
    async def dashboard_ws(websocket: WebSocket, db: Session = Depends(get_db)):
        await connection_manager.connect(websocket)
        try:
            while True:
                # We don't expect incoming messages for now; keep connection open.
                await websocket.receive_text()
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()

