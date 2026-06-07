"""
Customer model for the retention module.

Only meaningful in ``online_pos`` mode where the pharmacy can register
customers and send digital receipts + health follow-up messages.

In ``local_pos`` mode this table exists but is unused — village pharmacies
capture customer_name and customer_phone on the Sale record directly and do
not build a registered customer base.
"""
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ConsentStatus(str, PyEnum):
    """Customer consent for marketing/follow-up communications."""
    GRANTED = "granted"     # Customer explicitly opted in
    DECLINED = "declined"   # Customer explicitly opted out
    PENDING = "pending"     # Not yet asked


class FollowUpStatus(str, PyEnum):
    """Status of a scheduled health follow-up message."""
    PENDING = "pending"         # Waiting to be sent
    SENT = "sent"               # Delivered to SMS/WhatsApp provider
    DELIVERED = "delivered"     # Confirmed delivery receipt
    FAILED = "failed"           # All retries exhausted
    SKIPPED = "skipped"         # Consent declined or customer opted out
    RESPONDED = "responded"     # Customer replied


def _enum_values(enum_class):
    """Persist enum values (lowercase), matching the PostgreSQL migration."""
    return [member.value for member in enum_class]


class Customer(Base):
    """Registered pharmacy customer.

    Customers are tenant-scoped — each organization maintains its own
    customer registry. Phone number is the primary de-duplication key
    within an organization.
    """

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)

    # Identity
    full_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False, index=True)  # Primary contact + de-dup key
    email = Column(String(200), nullable=True)
    date_of_birth = Column(String(20), nullable=True)       # ISO date string (YYYY-MM-DD)
    gender = Column(String(20), nullable=True)              # male / female / other / not_stated

    # Address
    address = Column(Text, nullable=True)
    town = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)

    # Health notes (pharmacist-facing, NOT sent in messages)
    known_allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Communication consent (Ghana NCA / DPA compliance)
    sms_consent = Column(
        SQLEnum(ConsentStatus, name="consentstatus", values_callable=_enum_values),
        default=ConsentStatus.PENDING,
        nullable=False,
    )
    whatsapp_consent = Column(
        SQLEnum(ConsentStatus, name="consentstatus", values_callable=_enum_values),
        default=ConsentStatus.PENDING,
        nullable=False,
    )
    consent_recorded_at = Column(DateTime(timezone=True), nullable=True)

    # Preferred channel: sms, whatsapp, or none
    preferred_channel = Column(String(20), default="sms", nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sales = relationship("Sale", back_populates="customer")
    follow_ups = relationship("CustomerFollowUp", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.full_name}', phone='{self.phone}')>"


class CustomerFollowUp(Base):
    """Scheduled health follow-up message for a specific sale.

    Created automatically when a sale is linked to a registered customer
    who has granted SMS/WhatsApp consent. The scheduler sends these at
    the configured interval after the sale date (default: 3 days).
    """

    __tablename__ = "customer_follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)

    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    channel = Column(String(20), nullable=False)            # sms or whatsapp

    # Delivery tracking
    status = Column(
        SQLEnum(FollowUpStatus, name="followupstatus", values_callable=_enum_values),
        default=FollowUpStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    provider_message_id = Column(String(200), nullable=True)    # External delivery reference

    # Message content snapshot (what was actually sent)
    message_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="follow_ups")

    def __repr__(self):
        return (
            f"<CustomerFollowUp(id={self.id}, customer_id={self.customer_id}, "
            f"sale_id={self.sale_id}, status='{self.status}')>"
        )
