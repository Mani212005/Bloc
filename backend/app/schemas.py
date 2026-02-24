from datetime import datetime, date
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .models import CallerStatus, LeadAssignmentStatus


class CallerBase(BaseModel):
    name: str
    role: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    daily_limit: int = 0
    assigned_states: list[str] = Field(default_factory=list)
    status: CallerStatus = CallerStatus.ACTIVE


class CallerCreate(CallerBase):
    pass


class CallerUpdate(BaseModel):
    role: Optional[str] = None
    languages: Optional[list[str]] = None
    daily_limit: Optional[int] = None
    assigned_states: Optional[list[str]] = None
    status: Optional[CallerStatus] = None


class CallerStatusUpdate(BaseModel):
    status: CallerStatus


class CallerOut(BaseModel):
    id: UUID
    name: str
    role: Optional[str]
    languages: list[str]
    daily_limit: int
    assigned_states: list[str]
    leads_assigned_today: int
    status: CallerStatus

    class Config:
        from_attributes = True


class LeadBase(BaseModel):
    name: Optional[str] = None
    phone: str
    timestamp: datetime
    lead_source: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class LeadWebhookIn(LeadBase):
    pass


class LeadOut(BaseModel):
    id: UUID
    name: Optional[str]
    phone: str
    lead_source: Optional[str]
    city: Optional[str]
    state: Optional[str]
    metadata: Optional[dict[str, Any]]
    created_at: datetime
    assigned_caller_id: Optional[UUID] = None
    assignment_status: Optional[LeadAssignmentStatus] = None
    assignment_reason: Optional[str] = None

    class Config:
        from_attributes = True


class LeadListItem(BaseModel):
    id: UUID
    name: Optional[str]
    phone: str
    state: Optional[str]
    lead_source: Optional[str]
    assigned_caller_name: Optional[str]
    assignment_status: Optional[LeadAssignmentStatus]
    assignment_reason: Optional[str]
    assigned_at: Optional[datetime]


class LeadReassignRequest(BaseModel):
    caller_id: Optional[UUID] = None


class AssignmentEvent(BaseModel):
    lead_id: UUID
    caller_id: Optional[UUID]
    assignment_status: LeadAssignmentStatus
    assignment_reason: str
    timestamp: datetime


class BusinessDateInfo(BaseModel):
    business_date: date

