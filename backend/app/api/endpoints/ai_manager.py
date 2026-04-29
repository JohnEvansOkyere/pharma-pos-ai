"""
Read-only AI manager assistant endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_organization_access, require_view_reports
from app.db.base import get_db
from app.models.user import User
from app.schemas.ai_manager import AIManagerChatRequest, AIManagerChatResponse
from app.services.ai_manager_service import AIManagerService

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
