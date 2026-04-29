"""
SQLAlchemy models package.
Import all models here for Alembic auto-generation.
"""
from app.models.user import User
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.tenancy import Branch, Device, Organization
from app.models.product import Product, ProductBatch
from app.models.sale import Sale, SaleItem, SaleReversal
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.stock_adjustment import StockAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.stock_take import StockTake, StockTakeItem
from app.models.sync_event import SyncEvent, SyncEventCounter
from app.models.sync_ingestion import IngestedSyncEvent
from app.models.ai_report import AIWeeklyManagerReport, AIWeeklyReportDelivery
from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudSaleFact,
)

__all__ = [
    "User",
    "Category",
    "Supplier",
    "Organization",
    "Branch",
    "Device",
    "Product",
    "ProductBatch",
    "Sale",
    "SaleItem",
    "SaleReversal",
    "Notification",
    "ActivityLog",
    "StockAdjustment",
    "InventoryMovement",
    "StockTake",
    "StockTakeItem",
    "SyncEvent",
    "SyncEventCounter",
    "IngestedSyncEvent",
    "AIWeeklyManagerReport",
    "AIWeeklyReportDelivery",
    "CloudSaleFact",
    "CloudInventoryMovementFact",
    "CloudProductSnapshot",
    "CloudBatchSnapshot",
]
