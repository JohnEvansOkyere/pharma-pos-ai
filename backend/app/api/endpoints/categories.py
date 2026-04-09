"""
Category management API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.category import Category
from app.models.user import User
from app.services.audit_service import AuditService
from app.schemas.category import Category as CategorySchema, CategoryCreate, CategoryUpdate
from app.api.dependencies import get_current_active_user, require_manager

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategorySchema])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all categories."""
    categories = db.query(Category).all()
    return categories


@router.post("", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Create a new category."""
    # Check for duplicate name
    if db.query(Category).filter(Category.name == category.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name already exists"
        )

    db_category = Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    AuditService.log(
        db,
        action="create_category",
        user_id=current_user.id,
        entity_type="category",
        entity_id=db_category.id,
        description=f"Created category {db_category.name}",
    )
    db.commit()

    return db_category


@router.put("/{category_id}", response_model=CategorySchema)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Update a category."""
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_category, field, value)

    db.commit()
    db.refresh(db_category)
    AuditService.log(
        db,
        action="update_category",
        user_id=current_user.id,
        entity_type="category",
        entity_id=db_category.id,
        description=f"Updated category {db_category.name}",
        extra_data={"updated_fields": sorted(update_data.keys())},
    )
    db.commit()

    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Delete a category."""
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    deleted_category_id = db_category.id
    deleted_category_name = db_category.name
    db.delete(db_category)
    db.commit()
    AuditService.log(
        db,
        action="delete_category",
        user_id=current_user.id,
        entity_type="category",
        entity_id=deleted_category_id,
        description=f"Deleted category {deleted_category_name}",
    )
    db.commit()
