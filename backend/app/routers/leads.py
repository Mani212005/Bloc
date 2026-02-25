from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Caller, Lead, LeadAssignment
from app.schemas import LeadListItem, LeadOut, LeadReassignRequest
from app.services.assignment_engine import assign_lead
from app.services.realtime import AssignmentEventOut, connection_manager


router = APIRouter(prefix="/leads", tags=["leads"])


def _latest_assignment_subquery():
    """Return a subquery that has the single most-recent assignment per lead."""
    la = LeadAssignment.__table__

    # Rank assignments by assigned_at descending within each lead_id partition
    ranked = (
        select(
            la,
            func.row_number()
            .over(partition_by=la.c.lead_id, order_by=la.c.assigned_at.desc())
            .label("rn"),
        )
    ).subquery("la_ranked")

    return (
        select(ranked)
        .where(ranked.c.rn == 1)
        .subquery("la_latest")
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
    la_latest = _latest_assignment_subquery()

    q = (
        select(
            Lead,
            la_latest.c.status.label("la_status"),
            la_latest.c.assignment_reason.label("la_reason"),
            la_latest.c.assigned_at.label("la_assigned_at"),
            Caller,
        )
        .join(la_latest, la_latest.c.lead_id == Lead.id, isouter=True)
        .join(Caller, Caller.id == la_latest.c.caller_id, isouter=True)
    )

    conditions = []
    if state:
        conditions.append(Lead.state == state)
    if caller_id:
        conditions.append(la_latest.c.caller_id == caller_id)
    if search:
        pattern = f"%{search}%"
        conditions.append(or_(Lead.phone.ilike(pattern), Lead.name.ilike(pattern)))

    if conditions:
        q = q.where(and_(*conditions))

    q = q.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    rows = db.execute(q).all()
    items: list[LeadListItem] = []
    for lead, la_status, la_reason, la_assigned_at, caller in rows:
        items.append(
            LeadListItem(
                id=lead.id,
                name=lead.name,
                phone=lead.phone,
                state=lead.state,
                lead_source=lead.lead_source,
                assigned_caller_name=getattr(caller, "name", None),
                assignment_status=la_status,
                assignment_reason=la_reason,
                assigned_at=la_assigned_at,
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
        metadata=lead.lead_metadata,
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
        metadata=lead.lead_metadata,
        created_at=lead.created_at,
        assigned_caller_id=assignment.caller_id,
        assignment_status=assignment.status,
        assignment_reason=assignment.assignment_reason,
    )

