from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Caller,
    CallerDailyCounter,
    CallerState,
    Lead,
    LeadAssignment,
    LeadAssignmentStatus,
    RoundRobinPointer,
    CallerStatus,
)

log = logging.getLogger("bloc.assignment")


def get_business_date() -> date:
    # Single timezone system; adjust here if needed.
    return date.today()


def _eligible_callers_for_state(db: Session, state: Optional[str]) -> list[Caller]:
    base_query = select(Caller).where(Caller.status == CallerStatus.ACTIVE)

    if state:
        state_q = (
            base_query.join(CallerState, Caller.id == CallerState.caller_id)
            .where(CallerState.state == state)
            .with_for_update()
        )
        callers = list(db.scalars(state_q))
        if callers:
            return callers

    q = base_query.with_for_update()
    return list(db.scalars(q))


def _apply_daily_cap_filter(
    db: Session, callers: Iterable[Caller], business_date: date
) -> list[Caller]:
    caller_ids = [c.id for c in callers]
    if not caller_ids:
        return []

    counters = db.execute(
        select(CallerDailyCounter)
        .where(
            CallerDailyCounter.caller_id.in_(caller_ids),
            CallerDailyCounter.date == business_date,
        )
        .with_for_update()
    ).scalars()
    count_map = {c.caller_id: c for c in counters}

    eligible: list[Caller] = []
    for c in callers:
        if c.daily_limit == 0:
            eligible.append(c)
            continue
        counter = count_map.get(c.id)
        current = counter.count if counter else 0
        if current < c.daily_limit:
            eligible.append(c)
    return eligible


def _next_round_robin_caller(
    db: Session, key: str, eligible: list[Caller]
) -> Optional[Caller]:
    if not eligible:
        return None

    pointer = db.get(RoundRobinPointer, key)
    if pointer is None:
        pointer = RoundRobinPointer(key=key, last_caller_id=None)
        db.add(pointer)
        db.flush()

    ordered = sorted(eligible, key=lambda c: str(c.id))
    if pointer.last_caller_id is None:
        chosen = ordered[0]
    else:
        ids = [c.id for c in ordered]
        try:
            idx = ids.index(pointer.last_caller_id)
            chosen = ordered[(idx + 1) % len(ordered)]
        except ValueError:
            chosen = ordered[0]

    pointer.last_caller_id = chosen.id
    return chosen


def assign_lead(
    db: Session,
    lead: Lead,
    forced_caller_id: Optional[UUID] = None,
    reason_override: Optional[str] = None,
) -> LeadAssignment:
    """
    Execute smart assignment for a single lead inside an open transaction.
    """
    t0 = time.perf_counter()
    business_date = get_business_date()
    log.info("assign_lead start | lead_id=%s phone=%s state=%s", lead.id, lead.phone, lead.state)

    if forced_caller_id is not None:
        caller = db.get(Caller, forced_caller_id)
        if caller is None or caller.status != CallerStatus.ACTIVE:
            raise ValueError("Forced caller is not active or does not exist")
        chosen = caller
        assignment_reason = reason_override or "manual_reassign"
        log.info("assign_lead manual | caller=%s (%s)", caller.id, caller.name)
    else:
        eligible = _eligible_callers_for_state(db, lead.state)
        log.info("assign_lead state_eligible | count=%d state=%s", len(eligible), lead.state)

        eligible = _apply_daily_cap_filter(db, eligible, business_date)
        log.info("assign_lead cap_filtered | count=%d date=%s", len(eligible), business_date)

        if not eligible:
            log.warning("assign_lead unassigned | reason=cap_reached lead_id=%s", lead.id)
            lead.unassigned = True
            assignment = LeadAssignment(
                lead_id=lead.id,
                caller_id=None,
                status=LeadAssignmentStatus.UNASSIGNED,
                assignment_reason="unassigned_cap_reached",
            )
            db.add(assignment)
            return assignment

        has_state_specific = bool(
            lead.state
            and db.scalar(
                select(func.count())
                .select_from(CallerState)
                .where(CallerState.state == lead.state)
            )
        )
        key = f"state:{lead.state}" if lead.state and has_state_specific else "global"

        chosen = _next_round_robin_caller(db, key, eligible)
        if chosen is None:
            log.warning("assign_lead unassigned | reason=no_eligible lead_id=%s", lead.id)
            lead.unassigned = True
            assignment = LeadAssignment(
                lead_id=lead.id,
                caller_id=None,
                status=LeadAssignmentStatus.UNASSIGNED,
                assignment_reason="unassigned_no_eligible",
            )
            db.add(assignment)
            return assignment

        assignment_reason = reason_override or (
            "state_round_robin" if key.startswith("state:") else "global_round_robin"
        )
        log.info(
            "assign_lead chosen | caller=%s (%s) key=%s reason=%s",
            chosen.id, chosen.name, key, assignment_reason,
        )

    counter = db.get(
        CallerDailyCounter,
        {"caller_id": chosen.id, "date": business_date},
    )
    if counter is None:
        counter = CallerDailyCounter(
            caller_id=chosen.id,
            date=business_date,
            count=0,
        )
        db.add(counter)
        db.flush()
    counter.count += 1

    assignment = LeadAssignment(
        lead_id=lead.id,
        caller_id=chosen.id,
        status=LeadAssignmentStatus.ASSIGNED,
        assignment_reason=assignment_reason,
    )
    db.add(assignment)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "assign_lead complete | lead_id=%s caller=%s reason=%s  (%.1fms)",
        lead.id, chosen.name, assignment_reason, elapsed_ms,
    )
    return assignment

