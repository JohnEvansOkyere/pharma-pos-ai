"""
Tenant, branch, and device models for hybrid cloud readiness.
"""
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class DeviceStatus(str, Enum):
    """Registered device lifecycle status."""

    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"


class Organization(Base):
    """A pharmacy client/business tenant."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    legal_name = Column(String(200))
    contact_phone = Column(String(20))
    contact_email = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    branches = relationship("Branch", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"


class Branch(Base):
    """A physical pharmacy branch under an organization."""

    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    phone = Column(String(20))
    address = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="branches")
    devices = relationship("Device", back_populates="branch", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Branch(id={self.id}, organization_id={self.organization_id}, code='{self.code}')>"


class Device(Base):
    """A registered local branch machine/till/server."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    device_uid = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    status = Column(SQLEnum(DeviceStatus), default=DeviceStatus.ACTIVE, nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    branch = relationship("Branch", back_populates="devices")

    def __repr__(self):
        return f"<Device(id={self.id}, uid='{self.device_uid}', status='{self.status}')>"
