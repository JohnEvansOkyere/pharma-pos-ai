"""
Persisted AI-generated manager reports.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class AIWeeklyManagerReport(Base):
    """Weekly manager report generated from approved cloud reporting data."""

    __tablename__ = "ai_weekly_manager_reports"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "report_scope_key",
            "action_period_start",
            "action_period_end",
            name="uq_ai_weekly_reports_scope_action_period",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    report_scope_key = Column(String(50), nullable=False, index=True)
    generated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    performance_period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    performance_period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    action_period_start = Column(Date, nullable=False, index=True)
    action_period_end = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    executive_summary = Column(Text, nullable=False)
    sections = Column(JSON, nullable=False)
    tool_results = Column(JSON, nullable=False)
    safety_notes = Column(JSON, nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIWeeklyReportDelivery(Base):
    """Audited delivery attempt for a weekly manager report."""

    __tablename__ = "ai_weekly_report_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("ai_weekly_manager_reports.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    channel = Column(String(30), nullable=False, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=1)
    error_message = Column(Text, nullable=True)
    provider_response = Column(JSON, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIWeeklyReportDeliverySetting(Base):
    """Tenant-scoped recipients for weekly manager report delivery."""

    __tablename__ = "ai_weekly_report_delivery_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "report_scope_key", name="uq_ai_weekly_delivery_settings_scope"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    report_scope_key = Column(String(50), nullable=False, index=True)
    email_enabled = Column(Boolean, nullable=False, default=False)
    email_recipients = Column(JSON, nullable=False, default=list)
    telegram_enabled = Column(Boolean, nullable=False, default=False)
    telegram_chat_ids = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
