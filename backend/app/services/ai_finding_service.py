"""
Persistent AI finding service: upsert, list, and status-update CEO workbench findings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.ai_report import AIFinding

_ACTIVE_STATUSES = {"open", "acknowledged", "snoozed"}
_ALLOWED_STATUSES = {"open", "acknowledged", "snoozed", "dismissed", "resolved"}


def _make_fingerprint(branch_id: Optional[int], finding_type: str) -> str:
    return f"{branch_id or 0}:{finding_type}"


class AIFindingService:
    """Manage persistent findings in the ai_findings table."""

    @staticmethod
    def upsert_findings(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        findings: list[dict[str, Any]],
        data_trust_status: str = "ok",
    ) -> list[AIFinding]:
        """
        Insert new findings and refresh existing open/snoozed ones.
        Dismissed and resolved findings are left untouched so the decision persists.
        Flushes to DB but does NOT commit — caller must commit.
        """
        now = datetime.now(timezone.utc)
        saved: list[AIFinding] = []

        for f in findings:
            fingerprint = _make_fingerprint(branch_id, f["type"])
            existing = (
                db.query(AIFinding)
                .filter(
                    AIFinding.organization_id == organization_id,
                    AIFinding.fingerprint == fingerprint,
                )
                .first()
            )
            if existing is not None:
                if existing.status in _ACTIVE_STATUSES:
                    existing.severity = f["severity"]
                    existing.title = f["title"]
                    existing.summary = f["summary"]
                    existing.affected_count = f["affected_count"]
                    existing.action_hint = f["action_hint"]
                    existing.data_trust_status = data_trust_status
                    existing.last_seen_at = now
                    saved.append(existing)
            else:
                new_finding = AIFinding(
                    organization_id=organization_id,
                    branch_id=branch_id,
                    type=f["type"],
                    severity=f["severity"],
                    title=f["title"],
                    summary=f["summary"],
                    affected_count=f["affected_count"],
                    action_hint=f["action_hint"],
                    fingerprint=fingerprint,
                    evidence=f.get("evidence", {}),
                    data_trust_status=data_trust_status,
                    confidence=f.get("confidence", 1.0),
                    status="open",
                    last_seen_at=now,
                )
                db.add(new_finding)
                saved.append(new_finding)

        db.flush()
        return saved

    @staticmethod
    def get_findings(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        include_all_branches: bool = False,
        limit: int = 50,
    ) -> list[AIFinding]:
        """
        List findings for an org. By default returns active (non-resolved/dismissed) findings.
        When branch_id is given and include_all_branches is False, only that branch's findings
        plus org-level (branch_id=None) findings are returned.
        """
        now = datetime.now(timezone.utc)
        query = db.query(AIFinding).filter(AIFinding.organization_id == organization_id)

        if branch_id is not None and not include_all_branches:
            query = query.filter(
                (AIFinding.branch_id == branch_id) | (AIFinding.branch_id.is_(None))
            )
        elif branch_id is not None:
            query = query.filter(AIFinding.branch_id == branch_id)

        if status_filter and status_filter in _ALLOWED_STATUSES:
            query = query.filter(AIFinding.status == status_filter)
        else:
            query = query.filter(AIFinding.status.in_(list(_ACTIVE_STATUSES)))

        results = (
            query
            .order_by(AIFinding.severity.asc(), AIFinding.last_seen_at.desc())
            .limit(limit)
            .all()
        )

        # Auto-expire snoozed findings whose snooze window has passed
        for finding in results:
            if finding.status == "snoozed" and finding.snoozed_until and finding.snoozed_until <= now:
                finding.status = "open"
                finding.snoozed_until = None

        return results

    @staticmethod
    def update_status(
        db: Session,
        *,
        finding_id: int,
        organization_id: int,
        new_status: str,
        snoozed_until: Optional[datetime] = None,
        resolved_by_user_id: Optional[int] = None,
    ) -> Optional[AIFinding]:
        """
        Update finding status. Returns None if the finding does not exist or is not in scope.
        Flushes to DB but does NOT commit — caller must commit.
        """
        if new_status not in _ALLOWED_STATUSES:
            return None

        finding = (
            db.query(AIFinding)
            .filter(
                AIFinding.id == finding_id,
                AIFinding.organization_id == organization_id,
            )
            .first()
        )
        if finding is None:
            return None

        finding.status = new_status
        if new_status == "snoozed":
            finding.snoozed_until = snoozed_until
        elif new_status == "resolved":
            finding.resolved_at = datetime.now(timezone.utc)
            finding.resolved_by_user_id = resolved_by_user_id
        elif new_status == "open":
            finding.snoozed_until = None

        db.flush()
        return finding
