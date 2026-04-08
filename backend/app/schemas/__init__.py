"""
Pydantic schemas package.
"""
from app.schemas.user import User, UserCreate, UserUpdate, Token
from app.schemas.category import Category, CategoryCreate, CategoryUpdate
from app.schemas.supplier import Supplier, SupplierCreate, SupplierUpdate
from app.schemas.product import (
    Product,
    ProductCreate,
    ProductUpdate,
    ProductWithBatches,
    ProductBatch,
    ProductBatchCreate,
    ProductBatchUpdate,
)
from app.schemas.sale import Sale, SaleCreate, SaleWithItems, SaleItem, SaleSummary
from app.schemas.notification import Notification, NotificationCreate, NotificationUpdate
from app.schemas.stock_adjustment import StockAdjustment, StockAdjustmentCreate
from app.schemas.system import BackupStatus, BackupTriggerResult, SystemDiagnostics

__all__ = [
    "User",
    "UserCreate",
    "UserUpdate",
    "Token",
    "Category",
    "CategoryCreate",
    "CategoryUpdate",
    "Supplier",
    "SupplierCreate",
    "SupplierUpdate",
    "Product",
    "ProductCreate",
    "ProductUpdate",
    "ProductWithBatches",
    "ProductBatch",
    "ProductBatchCreate",
    "ProductBatchUpdate",
    "Sale",
    "SaleCreate",
    "SaleWithItems",
    "SaleItem",
    "SaleSummary",
    "Notification",
    "NotificationCreate",
    "NotificationUpdate",
    "StockAdjustment",
    "StockAdjustmentCreate",
    "BackupStatus",
    "BackupTriggerResult",
    "SystemDiagnostics",
]
