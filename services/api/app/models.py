import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CardApplication(Base):
    __tablename__ = "card_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    applicant_email = Column(String(255), nullable=False)
    surface = Column(String(32), nullable=False)
    experiment_variant = Column(String(64), nullable=False, default="control")
    state = Column(String(32), nullable=False, default="STARTED")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("idempotency_key", "endpoint_path", name="uq_idempotency_key_path"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(128), nullable=False)
    endpoint_path = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_status = Column(Integer, nullable=False)
    response_body = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class FunnelEvent(Base):
    __tablename__ = "funnel_events"
    __table_args__ = (
        Index("ix_funnel_events_app_created", "application_id", "occurred_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), nullable=False)
    event_name = Column(String(64), nullable=False)
    surface = Column(String(32), nullable=False)
    experiment_variant = Column(String(64), nullable=False)
    step_key = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
