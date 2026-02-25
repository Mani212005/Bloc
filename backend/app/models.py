import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Enum,
    Integer,
    ForeignKey,
    Text,
    UniqueConstraint,
    Date,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base


class CallerStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class Caller(Base):
    __tablename__ = "callers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=[])
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[CallerStatus] = mapped_column(
        Enum(CallerStatus, name="caller_status"),
        nullable=False,
        default=CallerStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    states: Mapped[list["CallerState"]] = relationship(
        "CallerState", back_populates="caller", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["LeadAssignment"]] = relationship(
        "LeadAssignment", back_populates="caller"
    )


class CallerState(Base):
    __tablename__ = "caller_states"

    caller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("callers.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(Text, primary_key=True)

    caller: Mapped["Caller"] = relationship("Caller", back_populates="states")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    timestamp_from_sheet: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lead_source: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    lead_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    unassigned: Mapped[bool] = mapped_column(default=False, nullable=False)

    assignments: Mapped[list["LeadAssignment"]] = relationship(
        "LeadAssignment", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("phone", "timestamp_from_sheet", name="uq_lead_phone_ts"),
    )


class LeadAssignmentStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


class LeadAssignment(Base):
    __tablename__ = "lead_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    caller_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("callers.id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    assignment_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeadAssignmentStatus] = mapped_column(
        Enum(LeadAssignmentStatus, name="lead_assignment_status"),
        nullable=False,
        default=LeadAssignmentStatus.ASSIGNED,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="assignments")
    caller: Mapped["Caller"] = relationship("Caller", back_populates="assignments")


class RoundRobinPointer(Base):
    __tablename__ = "rr_pointers"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    last_caller_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("callers.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CallerDailyCounter(Base):
    __tablename__ = "caller_daily_counters"

    caller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("callers.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

