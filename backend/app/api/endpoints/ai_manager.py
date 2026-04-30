"""
Read-only AI manager assistant endpoints.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_organization_access, require_view_reports
from app.db.base import get_db
from app.models.ai_report import AIWeeklyManagerReport, AIWeeklyReportDelivery, AIWeeklyReportDeliverySetting
from app.models.user import User
from app.schemas.ai_manager import (
    AIManagerChatRequest,
    AIManagerChatResponse,
    AIWeeklyManagerReportResponse,
    AIWeeklyReportDeliverRequest,
    AIWeeklyReportDeliveryResponse,
    AIWeeklyReportDeliverySettingResponse,
    AIWeeklyReportDeliverySettingUpsert,
    AIWeeklyReportGenerateRequest,
)
from app.services.ai_report_delivery_service import AIReportDeliveryService
from app.services.ai_manager_service import AIManagerService
from app.services.ai_weekly_report_service import AIWeeklyReportService

router = APIRouter(prefix="/ai-manager", tags=["AI Manager Assistant"])


@router.post("/chat", response_model=AIManagerChatResponse)
def chat_with_ai_manager(
    payload: AIManagerChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """
    Answer manager questions from approved cloud reporting data.

    The assistant is read-only and inherits the same organization/branch access
    control as cloud reporting endpoints.
    """
    require_organization_access(
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        current_user=current_user,
    )
    result = AIManagerService.answer(
        db,
        message=payload.message,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        period_days=payload.period_days,
        current_user=current_user,
    )
    return AIManagerChatResponse(**result)


@router.post("/weekly-reports/generate", response_model=AIWeeklyManagerReportResponse)
def generate_weekly_manager_report(
    payload: AIWeeklyReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """
    Generate and persist a read-only weekly manager report.

    The report combines the just-ended seven-day performance window with the
    next Monday-Sunday stock-risk and action-planning window.
    """
    require_organization_access(
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        current_user=current_user,
    )
    effective_branch_id = _resolve_branch_scope(current_user, payload.branch_id)
    report = AIWeeklyReportService.generate_for_organization(
        db,
        organization_id=payload.organization_id,
        branch_id=effective_branch_id,
        generated_by_user_id=current_user.id,
        deliver=payload.deliver,
        idempotent=True,
    )
    return _report_response(report)


@router.get("/weekly-reports", response_model=List[AIWeeklyManagerReportResponse])
def list_weekly_manager_reports(
    organization_id: int,
    branch_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """List saved weekly manager reports within the user's tenant scope."""
    require_organization_access(
        organization_id=organization_id,
        branch_id=branch_id,
        current_user=current_user,
    )
    effective_branch_id = _resolve_branch_scope(current_user, branch_id)
    reports = AIWeeklyReportService.list_reports(
        db,
        organization_id=organization_id,
        branch_id=effective_branch_id,
        limit=limit,
    )
    return [_report_response(report) for report in reports]


@router.get("/weekly-reports/{report_id}", response_model=AIWeeklyManagerReportResponse)
def get_weekly_manager_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """Fetch a saved weekly manager report by id."""
    report = db.query(AIWeeklyManagerReport).filter(AIWeeklyManagerReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly manager report not found")
    require_organization_access(
        organization_id=report.organization_id,
        branch_id=report.branch_id,
        current_user=current_user,
    )
    if current_user.branch_id is not None and report.branch_id != current_user.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")
    return _report_response(report)


@router.post("/weekly-reports/{report_id}/deliver", response_model=List[AIWeeklyReportDeliveryResponse])
def deliver_weekly_manager_report(
    report_id: int,
    payload: AIWeeklyReportDeliverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """Send a saved weekly manager report through configured email and/or Telegram channels."""
    report = db.query(AIWeeklyManagerReport).filter(AIWeeklyManagerReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly manager report not found")
    require_organization_access(
        organization_id=report.organization_id,
        branch_id=report.branch_id,
        current_user=current_user,
    )
    if current_user.branch_id is not None and report.branch_id != current_user.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")
    deliveries = AIReportDeliveryService.deliver(db, report, channels=payload.channels)
    return [_delivery_response(delivery) for delivery in deliveries]


@router.get("/weekly-reports/{report_id}/deliveries", response_model=List[AIWeeklyReportDeliveryResponse])
def list_weekly_report_deliveries(
    report_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_view_reports),
):
    """List persisted delivery attempts for a saved weekly manager report."""
    report = db.query(AIWeeklyManagerReport).filter(AIWeeklyManagerReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly manager report not found")
    require_organization_access(
        organization_id=report.organization_id,
        branch_id=report.branch_id,
        current_user=current_user,
    )
    if current_user.branch_id is not None and report.branch_id != current_user.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")

    deliveries = (
        db.query(AIWeeklyReportDelivery)
        .filter(AIWeeklyReportDelivery.report_id == report.id)
        .order_by(AIWeeklyReportDelivery.created_at.desc(), AIWeeklyReportDelivery.id.desc())
        .limit(limit)
        .all()
    )
    return [_delivery_response(delivery) for delivery in deliveries]


@router.get("/weekly-report-delivery-settings", response_model=AIWeeklyReportDeliverySettingResponse)
def get_weekly_report_delivery_setting(
    organization_id: int,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Fetch tenant-scoped weekly report delivery recipients."""
    require_organization_access(
        organization_id=organization_id,
        branch_id=branch_id,
        current_user=current_user,
    )
    setting = _find_delivery_setting(
        db,
        organization_id=organization_id,
        branch_id=branch_id,
    )
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weekly report delivery setting not found")
    return _delivery_setting_response(setting)


@router.put("/weekly-report-delivery-settings", response_model=AIWeeklyReportDeliverySettingResponse)
def upsert_weekly_report_delivery_setting(
    payload: AIWeeklyReportDeliverySettingUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create or update tenant-scoped weekly report delivery recipients."""
    require_organization_access(
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        current_user=current_user,
    )
    setting = _find_delivery_setting(
        db,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
    )
    report_scope_key = AIWeeklyReportService.scope_key(payload.branch_id)
    if setting is None:
        setting = AIWeeklyReportDeliverySetting(
            organization_id=payload.organization_id,
            branch_id=payload.branch_id,
            report_scope_key=report_scope_key,
            created_by_user_id=current_user.id,
        )
        db.add(setting)

    setting.email_enabled = payload.email_enabled
    setting.email_recipients = _clean_list(payload.email_recipients)
    setting.telegram_enabled = payload.telegram_enabled
    setting.telegram_chat_ids = _clean_list(payload.telegram_chat_ids)
    setting.is_active = payload.is_active
    setting.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(setting)
    return _delivery_setting_response(setting)


def _resolve_branch_scope(current_user: User, requested_branch_id: Optional[int]) -> Optional[int]:
    if current_user.branch_id is None:
        return requested_branch_id
    if requested_branch_id is not None and requested_branch_id != current_user.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")
    return current_user.branch_id


def _report_response(report: AIWeeklyManagerReport) -> AIWeeklyManagerReportResponse:
    return AIWeeklyManagerReportResponse(
        id=report.id,
        organization_id=report.organization_id,
        branch_id=report.branch_id,
        generated_by_user_id=report.generated_by_user_id,
        performance_period_start=report.performance_period_start,
        performance_period_end=report.performance_period_end,
        action_period_start=report.action_period_start,
        action_period_end=report.action_period_end,
        title=report.title,
        executive_summary=report.executive_summary,
        sections=report.sections,
        tool_results=report.tool_results,
        safety_notes=report.safety_notes,
        provider=report.provider,
        model=report.model,
        fallback_used=report.fallback_used,
        generated_at=report.generated_at,
        created_at=report.created_at,
    )


def _delivery_response(delivery) -> AIWeeklyReportDeliveryResponse:
    return AIWeeklyReportDeliveryResponse(
        id=delivery.id,
        report_id=delivery.report_id,
        organization_id=delivery.organization_id,
        branch_id=delivery.branch_id,
        channel=delivery.channel,
        recipient=delivery.recipient,
        status=delivery.status,
        attempt_count=delivery.attempt_count,
        error_message=delivery.error_message,
        provider_response=delivery.provider_response,
        sent_at=delivery.sent_at,
        created_at=delivery.created_at,
    )


def _find_delivery_setting(
    db: Session,
    *,
    organization_id: int,
    branch_id: Optional[int],
):
    return (
        db.query(AIWeeklyReportDeliverySetting)
        .filter(
            AIWeeklyReportDeliverySetting.organization_id == organization_id,
            AIWeeklyReportDeliverySetting.report_scope_key == AIWeeklyReportService.scope_key(branch_id),
        )
        .first()
    )


def _delivery_setting_response(setting: AIWeeklyReportDeliverySetting) -> AIWeeklyReportDeliverySettingResponse:
    return AIWeeklyReportDeliverySettingResponse(
        id=setting.id,
        organization_id=setting.organization_id,
        branch_id=setting.branch_id,
        report_scope_key=setting.report_scope_key,
        email_enabled=setting.email_enabled,
        email_recipients=setting.email_recipients or [],
        telegram_enabled=setting.telegram_enabled,
        telegram_chat_ids=setting.telegram_chat_ids or [],
        is_active=setting.is_active,
        created_by_user_id=setting.created_by_user_id,
        updated_by_user_id=setting.updated_by_user_id,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


def _clean_list(values: List[str]) -> List[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]
