"""
Customer retention API endpoints.

Routes:
  POST   /customers                       — Register a new customer (POS registration)
  GET    /customers                       — List customers with pagination
  GET    /customers/search                — Search by name or phone (POS autocomplete)
  GET    /customers/analytics             — Retention + churn + product affinity summary
  GET    /customers/follow-ups/pending    — Operator view: all pending follow-ups
  GET    /customers/{id}                  — Customer profile with purchase history
  PATCH  /customers/{id}                  — Update customer details
  PATCH  /customers/{id}/consent          — Update consent only (lightweight POS endpoint)
  GET    /customers/{id}/follow-ups       — List follow-ups for a customer
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, require_manage_users
from app.core.app_mode import scope_query_to_user
from app.core.config import settings
from app.db.base import get_db
from app.models.customer import ConsentStatus, Customer, CustomerFollowUp, FollowUpStatus
from app.models.sale import Sale
from app.models.user import User
from app.schemas.customer import (
    Customer as CustomerSchema,
    CustomerConsentUpdate,
    CustomerCreate,
    CustomerSearchResult,
    CustomerUpdate,
    FollowUpSchema,
)
from app.services.customer_analytics_service import CustomerAnalyticsService

router = APIRouter(prefix="/customers", tags=["Customers"])



def _customer_scope(query, current_user: User, *, include_branch: bool = True):
    return scope_query_to_user(
        query,
        Customer,
        current_user,
        app_mode=settings.APP_MODE,
        include_branch=include_branch,
    )


@router.post("", response_model=CustomerSchema, status_code=status.HTTP_201_CREATED)
def register_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Register a new customer.

    Phone number must be unique per organization. If a customer with the same
    phone already exists, a 409 is returned so the caller can look up the
    existing record.
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no organization — cannot register customers",
        )

    # De-duplicate by phone within org
    existing = (
        _customer_scope(db.query(Customer), current_user, include_branch=False)
        .filter(
            Customer.phone == data.phone.strip(),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A customer with phone {data.phone} is already registered (id={existing.id})",
        )

    now_ts = None
    if data.sms_consent in ("granted", "declined") or data.whatsapp_consent in ("granted", "declined"):
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc)

    customer = Customer(
        organization_id=current_user.organization_id,
        branch_id=current_user.branch_id,
        full_name=data.full_name.strip(),
        phone=data.phone.strip(),
        email=data.email,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        address=data.address,
        town=data.town,
        region=data.region,
        known_allergies=data.known_allergies,
        chronic_conditions=data.chronic_conditions,
        notes=data.notes,
        sms_consent=ConsentStatus(data.sms_consent) if data.sms_consent else ConsentStatus.PENDING,
        whatsapp_consent=ConsentStatus(data.whatsapp_consent) if data.whatsapp_consent else ConsentStatus.PENDING,
        consent_recorded_at=now_ts,
        preferred_channel=data.preferred_channel or "sms",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    customer.total_purchases = 0
    return customer


@router.get("", response_model=List[CustomerSchema])
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all customers with pagination."""
    query = _customer_scope(db.query(Customer), current_user)
    if is_active is not None:
        query = query.filter(Customer.is_active == is_active)
    customers = query.order_by(Customer.full_name).offset(skip).limit(limit).all()
    for c in customers:
        c.total_purchases = db.query(func.count(Sale.id)).filter(Sale.customer_id == c.id).scalar() or 0
    return customers


@router.get("/search", response_model=List[CustomerSearchResult])
def search_customers(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search customers by name or phone — used for POS autocomplete."""
    term = f"%{q}%"
    query = _customer_scope(db.query(Customer), current_user).filter(
        Customer.is_active == True,
        (Customer.full_name.ilike(term)) | (Customer.phone.ilike(term)),
    )
    return query.order_by(Customer.full_name).limit(limit).all()


@router.get("/follow-ups/pending", response_model=List[FollowUpSchema])
def list_pending_follow_ups(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Operator view: all PENDING follow-ups across the organization."""
    query = scope_query_to_user(
        db.query(CustomerFollowUp),
        CustomerFollowUp,
        current_user,
        app_mode=settings.APP_MODE,
    ).filter(
        CustomerFollowUp.status == FollowUpStatus.PENDING
    )
    return query.order_by(CustomerFollowUp.scheduled_at).limit(limit).all()


@router.get("/analytics")
def get_customer_analytics(
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Customer retention analytics: total/new/repeat/at-risk/churned customers,
    consent rates, follow-up stats, top customers by spend, and product affinity."""
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no organization — analytics unavailable",
        )
    return CustomerAnalyticsService.summary(
        db,
        organization_id=current_user.organization_id,
        branch_id=current_user.branch_id,
        period_days=period_days,
    )


@router.get("/{customer_id}", response_model=CustomerSchema)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get customer profile with total purchase count."""
    customer = _get_or_404(db, customer_id, current_user)
    customer.total_purchases = (
        db.query(func.count(Sale.id)).filter(Sale.customer_id == customer_id).scalar() or 0
    )
    return customer


@router.patch("/{customer_id}", response_model=CustomerSchema)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update customer details."""
    customer = _get_or_404(db, customer_id, current_user)
    update_data = data.model_dump(exclude_unset=True)

    consent_fields = {"sms_consent", "whatsapp_consent"}
    has_consent_change = bool(update_data.keys() & consent_fields)

    for field, value in update_data.items():
        if field in consent_fields and value:
            setattr(customer, field, ConsentStatus(value))
        else:
            setattr(customer, field, value)

    if has_consent_change:
        from datetime import datetime, timezone
        customer.consent_recorded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(customer)
    customer.total_purchases = (
        db.query(func.count(Sale.id)).filter(Sale.customer_id == customer_id).scalar() or 0
    )
    return customer


@router.patch("/{customer_id}/consent", response_model=CustomerSchema)
def update_consent(
    customer_id: int,
    data: CustomerConsentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update consent only — lightweight endpoint for the POS registration modal."""
    customer = _get_or_404(db, customer_id, current_user)

    if data.sms_consent:
        customer.sms_consent = ConsentStatus(data.sms_consent)
    if data.whatsapp_consent:
        customer.whatsapp_consent = ConsentStatus(data.whatsapp_consent)
    if data.preferred_channel:
        customer.preferred_channel = data.preferred_channel

    from datetime import datetime, timezone
    customer.consent_recorded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(customer)
    customer.total_purchases = (
        db.query(func.count(Sale.id)).filter(Sale.customer_id == customer_id).scalar() or 0
    )
    return customer


@router.get("/{customer_id}/follow-ups", response_model=List[FollowUpSchema])
def list_customer_follow_ups(
    customer_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List follow-up history for a specific customer."""
    _get_or_404(db, customer_id, current_user)  # access check
    follow_ups = (
        scope_query_to_user(
            db.query(CustomerFollowUp),
            CustomerFollowUp,
            current_user,
            app_mode=settings.APP_MODE,
        )
        .filter(CustomerFollowUp.customer_id == customer_id)
        .order_by(CustomerFollowUp.scheduled_at.desc())
        .limit(limit)
        .all()
    )
    return follow_ups


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, customer_id: int, current_user: User) -> Customer:
    customer = _customer_scope(
        db.query(Customer),
        current_user,
    ).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer
