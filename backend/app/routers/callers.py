from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Caller, CallerDailyCounter, CallerState, CallerStatus
from app.schemas import CallerCreate, CallerOut, CallerStatusUpdate, CallerUpdate
from app.services.assignment_engine import get_business_date


router = APIRouter(prefix="/callers", tags=["callers"])


def _get_caller_or_404(db: Session, caller_id: UUID) -> Caller:
    caller = db.get(Caller, caller_id)
    if caller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="caller not found")
    return caller


@router.post("", response_model=CallerOut, status_code=status.HTTP_201_CREATED)
def create_caller(payload: CallerCreate, db: Session = Depends(get_db)):
    if payload.daily_limit < 0:
        raise HTTPException(status_code=400, detail="daily_limit must be non-negative")

    caller = Caller(
        id=uuid4(),
        name=payload.name,
        role=payload.role,
        languages=payload.languages,
        daily_limit=payload.daily_limit,
        status=payload.status,
    )
    db.add(caller)
    db.flush()

    for state_value in payload.assigned_states:
        db.add(CallerState(caller_id=caller.id, state=state_value))

    db.commit()
    db.refresh(caller)

    leads_today = _leads_assigned_today(db, caller.id, get_business_date())
    return CallerOut(
        id=caller.id,
        name=caller.name,
        role=caller.role,
        languages=caller.languages,
        daily_limit=caller.daily_limit,
        assigned_states=[cs.state for cs in caller.states],
        leads_assigned_today=leads_today,
        status=caller.status,
    )


def _leads_assigned_today(db: Session, caller_id: UUID, day: date) -> int:
    counter = db.get(CallerDailyCounter, {"caller_id": caller_id, "date": day})
    return counter.count if counter else 0


@router.get("", response_model=list[CallerOut])
def list_callers(db: Session = Depends(get_db)):
    today = get_business_date()

    callers = db.scalars(select(Caller)).all()
    state_rows = db.execute(
        select(CallerState.caller_id, CallerState.state).where(
            CallerState.caller_id.in_([c.id for c in callers])
        )
    ).all()
    states_map: dict[UUID, list[str]] = {}
    for cid, state_value in state_rows:
        states_map.setdefault(cid, []).append(state_value)

    counters = db.execute(
        select(CallerDailyCounter).where(CallerDailyCounter.date == today)
    ).scalars()
    count_map = {c.caller_id: c.count for c in counters}

    results: list[CallerOut] = []
    for c in callers:
        results.append(
            CallerOut(
                id=c.id,
                name=c.name,
                role=c.role,
                languages=c.languages,
                daily_limit=c.daily_limit,
                assigned_states=states_map.get(c.id, []),
                leads_assigned_today=count_map.get(c.id, 0),
                status=c.status,
            )
        )
    return results


@router.put("/{caller_id}", response_model=CallerOut)
def update_caller(
    caller_id: UUID,
    payload: CallerUpdate,
    db: Session = Depends(get_db),
):
    caller = _get_caller_or_404(db, caller_id)

    if payload.daily_limit is not None and payload.daily_limit < 0:
        raise HTTPException(status_code=400, detail="daily_limit must be non-negative")

    if payload.role is not None:
        caller.role = payload.role
    if payload.languages is not None:
        caller.languages = payload.languages
    if payload.daily_limit is not None:
        caller.daily_limit = payload.daily_limit
    if payload.status is not None:
        caller.status = payload.status

    if payload.assigned_states is not None:
        db.query(CallerState).filter(CallerState.caller_id == caller.id).delete()
        for state_value in payload.assigned_states:
            db.add(CallerState(caller_id=caller.id, state=state_value))

    db.commit()
    db.refresh(caller)

    today = get_business_date()
    return CallerOut(
        id=caller.id,
        name=caller.name,
        role=caller.role,
        languages=caller.languages,
        daily_limit=caller.daily_limit,
        assigned_states=[cs.state for cs in caller.states],
        leads_assigned_today=_leads_assigned_today(db, caller.id, today),
        status=caller.status,
    )


@router.patch("/{caller_id}/status", response_model=CallerOut)
def update_caller_status(
    caller_id: UUID,
    payload: CallerStatusUpdate,
    db: Session = Depends(get_db),
):
    caller = _get_caller_or_404(db, caller_id)
    caller.status = payload.status
    db.commit()
    db.refresh(caller)

    today = get_business_date()
    return CallerOut(
        id=caller.id,
        name=caller.name,
        role=caller.role,
        languages=caller.languages,
        daily_limit=caller.daily_limit,
        assigned_states=[cs.state for cs in caller.states],
        leads_assigned_today=_leads_assigned_today(db, caller.id, today),
        status=caller.status,
    )


@router.delete("/{caller_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_caller(caller_id: UUID, db: Session = Depends(get_db)):
    caller = _get_caller_or_404(db, caller_id)
    caller.status = CallerStatus.PAUSED
    db.commit()
    return

