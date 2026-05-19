"""
Persisted AI-generated manager reports and findings.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    review_notes = Column(Text, nullable=True)
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
    retryable = Column(Boolean, nullable=False, default=False, index=True)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    max_attempts = Column(Integer, nullable=False, default=3)
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


class AIFinding(Base):
    """
    Persistent CEO workbench finding.

    Upserted from the on-demand briefing service and tracked through a simple
    status workflow: open → acknowledged / snoozed → resolved / dismissed.
    Fingerprint ensures at most one active row per (org, scope, finding type).
    """

    __tablename__ = "ai_findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_ai_findings_org_fingerprint"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    summary = Column(Text, nullable=False)
    affected_count = Column(Integer, nullable=False, default=0)
    action_hint = Column(Text, nullable=False, default="")
    # fingerprint = "<branch_id or 0>:<type>" — unique per org scope
    fingerprint = Column(String(120), nullable=False, index=True)
    evidence = Column(JSON, nullable=False, default=dict)
    data_trust_status = Column(String(20), nullable=False, default="ok")
    confidence = Column(Float, nullable=False, default=1.0)
    # status: open | acknowledged | snoozed | dismissed | resolved
    status = Column(String(20), nullable=False, default="open", index=True)
    due_date = Column(Date, nullable=True, index=True)
    snoozed_until = Column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AIChatSession(Base):
    """A named conversation session between a manager and the AI assistant."""

    __tablename__ = "ai_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class AIChatMessage(Base):
    """A single turn (user or assistant) within an AI chat session."""

    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class TelegramAlertLog(Base):
    """
    Deduplication log for proactive Telegram anomaly alerts.
    One row per (organization, alert_key). Updated on each send.
    Alerts are suppressed until the cooldown window passes.
    """

    __tablename__ = "telegram_alert_logs"
    __table_args__ = (
        UniqueConstraint("organization_id", "alert_key", name="uq_telegram_alert_logs_org_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    alert_key = Column(String(200), nullable=False, index=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIExternalProviderSetting(Base):
    """Tenant-level policy for external AI provider use."""

    __tablename__ = "ai_external_provider_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_ai_external_provider_settings_org"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    external_ai_enabled = Column(Boolean, nullable=False, default=False, index=True)
    allowed_providers = Column(JSON, nullable=False, default=list)
    preferred_provider = Column(String(50), nullable=True)
    preferred_model = Column(String(100), nullable=True)
    consent_text = Column(Text, nullable=True)
    consented_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    consented_at = Column(DateTime(timezone=True), nullable=True, index=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
