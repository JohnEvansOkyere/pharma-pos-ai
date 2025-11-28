"""
Product and ProductBatch models for inventory management.
Enhanced for professional pharmaceutical POS system.
"""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.db.base import Base


class DosageForm(str, Enum):
    """Pharmaceutical dosage forms."""
    TABLET = "TABLET"
    CAPSULE = "CAPSULE"
    SYRUP = "SYRUP"
    INJECTION = "INJECTION"
    SUSPENSION = "SUSPENSION"
    CREAM = "CREAM"
    OINTMENT = "OINTMENT"
    DROPS = "DROPS"
    POWDER = "POWDER"
    INHALER = "INHALER"
    SUPPOSITORY = "SUPPOSITORY"
    PATCH = "PATCH"
    OTHER = "OTHER"


class PrescriptionStatus(str, Enum):
    """Prescription requirement status."""
    PRESCRIPTION_REQUIRED = "PRESCRIPTION_REQUIRED"
    PRESCRIPTION_OPTIONAL = "PRESCRIPTION_OPTIONAL"
    OTC = "OTC"  # Over-the-counter


class Product(Base):
    """Product master data model - Enhanced for pharmaceutical management."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    generic_name = Column(String(200))
    sku = Column(String(50), unique=True, nullable=False, index=True)
    barcode = Column(String(100), unique=True, index=True)
    description = Column(Text)

    # Pharmaceutical-specific fields
    dosage_form = Column(SQLEnum(DosageForm), nullable=False, default=DosageForm.TABLET)
    strength = Column(String(50))  # e.g., "500mg", "10ml"
    prescription_status = Column(SQLEnum(PrescriptionStatus), default=PrescriptionStatus.OTC)
    active_ingredient = Column(String(200))  # Main active pharmaceutical ingredient
    manufacturer = Column(String(200))

    # Drug information
    usage_instructions = Column(Text)  # How to take the medication
    side_effects = Column(Text)  # Common side effects
    contraindications = Column(Text)  # When not to use
    storage_conditions = Column(String(200))  # e.g., "Store below 25°C"

    # Regulatory
    drug_license_number = Column(String(100))  # FDA/regulatory number
    is_narcotic = Column(Boolean, default=False)  # Controlled substance
    requires_id = Column(Boolean, default=False)  # Requires customer ID

    # Pricing (GH₵ - Ghana Cedis)
    cost_price = Column(Float, nullable=False)  # Purchase/cost price
    selling_price = Column(Float, nullable=False)  # Retail price
    wholesale_price = Column(Float)  # Bulk pricing
    mrp = Column(Float)  # Maximum retail price

    # Inventory
    total_stock = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=10, nullable=False)
    reorder_level = Column(Integer, default=20)  # Automatic reorder trigger
    reorder_quantity = Column(Integer, default=100)  # Suggested reorder qty

    # Relationships
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))

    category = relationship("Category", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    batches = relationship("ProductBatch", back_populates="product", cascade="all, delete-orphan")
    sale_items = relationship("SaleItem", back_populates="product")

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', form='{self.dosage_form}')>"


class ProductBatch(Base):
    """Product batch for tracking expiries and batch-specific stock."""

    __tablename__ = "product_batches"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    batch_number = Column(String(100), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    manufacture_date = Column(Date)
    expiry_date = Column(Date, nullable=False)
    cost_price = Column(Float, nullable=False)

    # Batch-specific info
    location = Column(String(100))  # Storage location (e.g., "Shelf A3")
    received_date = Column(Date, server_default=func.current_date())

    # Quality control
    is_quarantined = Column(Boolean, default=False)  # Quality hold
    quarantine_reason = Column(Text)

    # Relationship
    product = relationship("Product", back_populates="batches")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ProductBatch(id={self.id}, batch='{self.batch_number}', expiry='{self.expiry_date}')>"
