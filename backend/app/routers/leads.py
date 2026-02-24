from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Caller, Lead, LeadAssignment
from app.schemas import LeadListItem, LeadOut, LeadReassignRequest
from app.services.assignment_engine import assign_lead
from app.services.realtime import AssignmentEventOut, connection_manager


router = APIRouter(prefix="/leads", tags=["leads"])


def _latest_assignment_subquery():
    la = LeadAssignment
    return (
        select(la)
        .order_by(la.lead_id, la.assigned_at.desc())
        .distinct(la.lead_id)
        .subquery()
    )


@router.get("", response_model=list[LeadListItem])
def list_leads(
    state: Optional[str] = None,
    caller_id: Optional[UUID] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    la_sub = _latest_assignment_subquery()
    la_alias = LeadAssignment.__table__.alias("la_latest")

    q = (
        select(Lead, la_alias, Caller)
        .join(la_alias, la_alias.c.lead_id == Lead.id, isouter=True)
        .join(Caller, Caller.id == la_alias.c.caller_id, isouter=True)
    )

    conditions = []
    if state:
        conditions.append(Lead.state == state)
    if caller_id:
        conditions.append(la_alias.c.caller_id == caller_id)
    if search:
        pattern = f"%{search}%"
        conditions.append(or_(Lead.phone.ilike(pattern), Lead.name.ilike(pattern)))

    if conditions:
        q = q.where(and_(*conditions))

    q = q.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    rows = db.execute(q).all()
    items: list[LeadListItem] = []
    for lead, la_row, caller in rows:
        items.append(
            LeadListItem(
                id=lead.id,
                name=lead.name,
                phone=lead.phone,
                state=lead.state,
                lead_source=lead.lead_source,
                assigned_caller_name=getattr(caller, "name", None),
                assignment_status=la_row.status if la_row is not None else None,
                assignment_reason=la_row.assignment_reason if la_row is not None else None,
                assigned_at=la_row.assigned_at if la_row is not None else None,
            )
        )
    return items


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: UUID, db: Session = Depends(get_db)):
    lead = (
        db.query(Lead)
        .options(joinedload(Lead.assignments).joinedload(LeadAssignment.caller))
        .filter(Lead.id == lead_id)
        .first()
    )
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")

    latest = (
        sorted(lead.assignments, key=lambda a: a.assigned_at, reverse=True)[0]
        if lead.assignments
        else None
    )
    return LeadOut(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        lead_source=lead.lead_source,
        city=lead.city,
        state=lead.state,
        metadata=lead.metadata,
        created_at=lead.created_at,
        assigned_caller_id=latest.caller_id if latest else None,
        assignment_status=latest.status if latest else None,
        assignment_reason=latest.assignment_reason if latest else None,
    )


@router.patch("/{lead_id}/reassign", response_model=LeadOut)
async def reassign_lead(
    lead_id: UUID,
    payload: LeadReassignRequest,
    db: Session = Depends(get_db),
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")

    assignment = assign_lead(
        db,
        lead,
        forced_caller_id=payload.caller_id,
        reason_override="manual_reassign",
    )
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

    return LeadOut(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        lead_source=lead.lead_source,
        city=lead.city,
        state=lead.state,
        metadata=lead.metadata,
        created_at=lead.created_at,
        assigned_caller_id=assignment.caller_id,
        assignment_status=assignment.status,
        assignment_reason=assignment.assignment_reason,
    )

