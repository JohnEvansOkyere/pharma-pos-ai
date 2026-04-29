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
from app.schemas.sale import Sale, SaleCreate, SaleReversal, SaleWithItems, SaleItem, SaleSummary
from app.schemas.notification import Notification, NotificationCreate, NotificationUpdate
from app.schemas.stock_adjustment import StockAdjustment, StockAdjustmentCreate
from app.schemas.system import BackupStatus, BackupTriggerResult, SystemDiagnostics
from app.schemas.inventory_movement import InventoryMovement
from app.schemas.stock_take import StockTake, StockTakeCreate, StockTakeComplete, StockTakeItem
from app.schemas.tenancy import Branch, Device, Organization
from app.schemas.sync_event import SyncEvent
from app.schemas.sync_ingestion import SyncIngestionRequest, SyncIngestionResponse
from app.schemas.cloud_projection import CloudProjectionRunResult, CloudProjectionStatus
from app.schemas.cloud_reports import (
    CloudBranchSalesSummary,
    CloudExpiryRiskItem,
    CloudInventoryMovementSummary,
    CloudLowStockItem,
    CloudReconciliationIssue,
    CloudReconciliationSummary,
    CloudSalesSummary,
    CloudStockRiskSummary,
    CloudSyncHealth,
)
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
    "SaleReversal",
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
    "InventoryMovement",
    "StockTake",
    "StockTakeCreate",
    "StockTakeComplete",
    "StockTakeItem",
    "Organization",
    "Branch",
    "Device",
    "SyncEvent",
    "SyncIngestionRequest",
    "SyncIngestionResponse",
    "CloudProjectionRunResult",
    "CloudProjectionStatus",
    "CloudSalesSummary",
    "CloudBranchSalesSummary",
    "CloudInventoryMovementSummary",
    "CloudStockRiskSummary",
    "CloudLowStockItem",
    "CloudExpiryRiskItem",
    "CloudReconciliationIssue",
    "CloudReconciliationSummary",
    "CloudSyncHealth",
    "AIManagerChatRequest",
    "AIManagerChatResponse",
    "AIWeeklyReportGenerateRequest",
    "AIWeeklyReportDeliverRequest",
    "AIWeeklyReportDeliveryResponse",
    "AIWeeklyReportDeliverySettingUpsert",
    "AIWeeklyReportDeliverySettingResponse",
    "AIWeeklyManagerReportResponse",
]
