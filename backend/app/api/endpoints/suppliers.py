"""
Supplier management API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.supplier import Supplier
from app.models.sync_event import SyncEventType
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.sync_outbox_service import SyncOutboxService
from app.schemas.supplier import Supplier as SupplierSchema, SupplierCreate, SupplierUpdate
from app.api.dependencies import get_current_active_user, require_manage_suppliers

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=List[SupplierSchema])
def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all suppliers with pagination."""
    suppliers = db.query(Supplier).offset(skip).limit(limit).all()
    return suppliers


@router.get("/{supplier_id}", response_model=SupplierSchema)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific supplier by ID."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    return supplier


@router.post("", response_model=SupplierSchema, status_code=status.HTTP_201_CREATED)
def create_supplier(
    supplier: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_suppliers)
):
    """Create a new supplier."""
    # Check for duplicate name
    if db.query(Supplier).filter(Supplier.name == supplier.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier name already exists"
        )

    db_supplier = Supplier(**supplier.model_dump())
    db.add(db_supplier)
    db.flush()
    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.SUPPLIER_CREATED,
        aggregate_type="supplier",
        aggregate_id=db_supplier.id,
        payload={"supplier_id": db_supplier.id, "name": db_supplier.name},
    )
    AuditService.log(
        db,
        action="create_supplier",
        user_id=current_user.id,
        entity_type="supplier",
        entity_id=db_supplier.id,
        description=f"Created supplier {db_supplier.name}",
    )
    db.commit()
    db.refresh(db_supplier)

    return db_supplier


@router.put("/{supplier_id}", response_model=SupplierSchema)
def update_supplier(
    supplier_id: int,
    supplier_update: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_suppliers)
):
    """Update a supplier."""
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    update_data = supplier_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_supplier, field, value)

    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.SUPPLIER_UPDATED,
        aggregate_type="supplier",
        aggregate_id=db_supplier.id,
        payload={
            "supplier_id": db_supplier.id,
            "updated_fields": sorted(update_data.keys()),
            "updates": update_data,
        },
    )
    AuditService.log(
        db,
        action="update_supplier",
        user_id=current_user.id,
        entity_type="supplier",
        entity_id=db_supplier.id,
        description=f"Updated supplier {db_supplier.name}",
        extra_data={"updated_fields": sorted(update_data.keys())},
    )
    db.commit()
    db.refresh(db_supplier)

    return db_supplier


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manage_suppliers)
):
    """Delete a supplier."""
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )

    deleted_supplier_id = db_supplier.id
    deleted_supplier_name = db_supplier.name
    db.delete(db_supplier)
    SyncOutboxService.record_event(
        db,
        event_type=SyncEventType.SUPPLIER_DELETED,
        aggregate_type="supplier",
        aggregate_id=deleted_supplier_id,
        payload={"supplier_id": deleted_supplier_id, "name": deleted_supplier_name},
    )
    AuditService.log(
        db,
        action="delete_supplier",
        user_id=current_user.id,
        entity_type="supplier",
        entity_id=deleted_supplier_id,
        description=f"Deleted supplier {deleted_supplier_name}",
    )
    db.commit()
