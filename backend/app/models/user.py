"""
User model for authentication and authorization.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.db.base import Base


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MANAGER = "manager"
    CASHIER = "cashier"


class UserPermission(str, Enum):
    """Granular permission flags for sensitive workflows."""

    MANAGE_PRODUCTS = "can_manage_products"
    MANAGE_SUPPLIERS = "can_manage_suppliers"
    MANAGE_CATEGORIES = "can_manage_categories"
    MANAGE_USERS = "can_manage_users"
    VIEW_REPORTS = "can_view_reports"
    VOID_SALE = "can_void_sale"
    REFUND_SALE = "can_refund_sale"
    ADJUST_STOCK = "can_adjust_stock"
    PERFORM_STOCK_TAKE = "can_perform_stock_take"
    TRIGGER_BACKUP = "can_trigger_backup"


ROLE_DEFAULT_PERMISSIONS = {
    UserRole.ADMIN: {permission.value for permission in UserPermission},
    UserRole.MANAGER: {
        UserPermission.MANAGE_PRODUCTS.value,
        UserPermission.MANAGE_SUPPLIERS.value,
        UserPermission.MANAGE_CATEGORIES.value,
        UserPermission.VIEW_REPORTS.value,
        UserPermission.VOID_SALE.value,
        UserPermission.REFUND_SALE.value,
        UserPermission.ADJUST_STOCK.value,
        UserPermission.PERFORM_STOCK_TAKE.value,
        UserPermission.TRIGGER_BACKUP.value,
    },
    UserRole.CASHIER: set(),
}


class User(Base):
    """User model for system authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.CASHIER, nullable=False)
    permissions = Column(JSON, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sales = relationship("Sale", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    organization = relationship("Organization")
    branch = relationship("Branch")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def effective_permissions(self) -> set[str]:
        """Return explicit permissions, falling back to role defaults."""
        if self.permissions is not None:
            return set(self.permissions)
        return set(ROLE_DEFAULT_PERMISSIONS.get(self.role, set()))
