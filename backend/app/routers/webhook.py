import logging
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead
from app.schemas import LeadWebhookIn, LeadOut
from app.services.assignment_engine import assign_lead
from app.services.realtime import AssignmentEventOut, connection_manager

log = logging.getLogger("bloc.webhook")

router = APIRouter(tags=["webhook"])


def _verify_webhook_secret(x_webhook_secret: str | None) -> None:
    expected = os.getenv("WEBHOOK_SECRET")
    if expected and x_webhook_secret != expected:
        log.warning("Webhook rejected — invalid secret")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@router.post("/leads/webhook", response_model=LeadOut)
async def lead_webhook(
    payload: LeadWebhookIn,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_webhook_secret(x_webhook_secret)

    try:
        lead = Lead(
            id=uuid4(),
            name=payload.name,
            phone=payload.phone,
            timestamp_from_sheet=payload.timestamp,
            lead_source=payload.lead_source,
            city=payload.city,
            state=payload.state,
            lead_metadata=payload.metadata,
        )
        db.add(lead)
        db.flush()
    except IntegrityError:
        db.rollback()
        lead = (
            db.query(Lead)
            .filter(
                Lead.phone == payload.phone,
                Lead.timestamp_from_sheet == payload.timestamp,
            )
            .first()
        )
        if lead is None:
            raise

    assignment = assign_lead(db, lead)
    db.commit()
    db.refresh(lead)
    db.refresh(assignment)

    await connection_manager.broadcast_assignment(
        AssignmentEventOut(
            lead_id=str(lead.id),
            caller_id=str(assignment.caller_id) if assignment.caller_id else None,
            assignment_status=assignment.status,
            assignment_reason=assignment.assignment_reason,
            timestamp=datetime.utcnow(),
        )
    )

    assigned_caller_id = assignment.caller_id
    return LeadOut(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        lead_source=lead.lead_source,
        city=lead.city,
        state=lead.state,
        metadata=lead.lead_metadata,
        created_at=lead.created_at,
        assigned_caller_id=assigned_caller_id,
        assignment_status=assignment.status,
        assignment_reason=assignment.assignment_reason,
    )

