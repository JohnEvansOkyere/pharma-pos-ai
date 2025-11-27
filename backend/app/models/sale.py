"""
Sales transaction models - Enhanced for professional pharmaceutical POS.
Currency: GH₵ (Ghana Cedis)
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.db.base import Base


class PaymentMethod(str, Enum):
    """Payment methods for transactions."""
    CASH = "cash"
    MOMO = "momo"  # Mobile Money
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CREDIT = "credit"  # Customer credit/tab


class SaleStatus(str, Enum):
    """Sale transaction status."""
    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Sale(Base):
    """Sales transaction header - Enhanced with professional features."""

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    # Status
    status = Column(SQLEnum(SaleStatus), default=SaleStatus.COMPLETED, nullable=False)

    # Pricing (GH₵ - Ghana Cedis)
    subtotal = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    discount_percentage = Column(Float, default=0.0)  # Percentage discount applied
    tax_amount = Column(Float, default=0.0, nullable=False)
    tax_rate = Column(Float, default=0.0)  # Tax rate percentage
    total_amount = Column(Float, nullable=False)

    # Payment
    payment_method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.CASH, nullable=False)
    amount_paid = Column(Float, nullable=False)
    change_amount = Column(Float, default=0.0, nullable=False)

    # Mobile Money specific
    momo_reference = Column(String(100))  # MOMO transaction reference
    momo_number = Column(String(20))  # Customer MOMO number

    # Customer information
    customer_name = Column(String(100))
    customer_phone = Column(String(20))
    customer_id_number = Column(String(50))  # For controlled substances
    customer_address = Column(Text)

    # Prescription tracking
    prescription_number = Column(String(100))
    doctor_name = Column(String(100))
    has_prescription = Column(Boolean, default=False)

    # Insurance (for future enhancement)
    insurance_company = Column(String(100))
    insurance_claim_number = Column(String(100))
    insurance_coverage = Column(Float, default=0.0)

    notes = Column(Text)

    # Receipt printing
    is_printed = Column(Boolean, default=False)
    print_count = Column(Integer, default=0)

    # Relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="sales")

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Sale(id={self.id}, invoice='{self.invoice_number}', total=GH₵{self.total_amount})>"


class SaleItem(Base):
    """Individual items in a sale transaction - Enhanced with pharmaceutical info."""

    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # Product snapshot at time of sale
    product_name = Column(String(200), nullable=False)  # Store name at time of sale
    dosage_form = Column(String(50))  # Tablet, Syrup, etc.
    strength = Column(String(50))  # e.g., "500mg"

    # Batch tracking
    batch_number = Column(String(100))
    expiry_date = Column(Date)

    # Pricing
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)  # GH₵ per unit
    discount_amount = Column(Float, default=0.0, nullable=False)
    total_price = Column(Float, nullable=False)  # GH₵

    # Tax (if applicable per item)
    tax_amount = Column(Float, default=0.0)

    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")

    def __repr__(self):
        return f"<SaleItem(id={self.id}, product='{self.product_name}', qty={self.quantity}, form='{self.dosage_form}')>"
