"""
Sales transaction models.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Sale(Base):
    """Sales transaction header."""

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    # Pricing
    subtotal = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, nullable=False)

    # Payment
    payment_method = Column(String(50), default="cash")  # cash, card, upi, etc.
    amount_paid = Column(Float, nullable=False)
    change_amount = Column(Float, default=0.0, nullable=False)

    # Customer (optional)
    customer_name = Column(String(100))
    customer_phone = Column(String(20))

    notes = Column(Text)

    # Relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="sales")

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Sale(id={self.id}, invoice='{self.invoice_number}', total={self.total_amount})>"


class SaleItem(Base):
    """Individual items in a sale transaction."""

    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    total_price = Column(Float, nullable=False)

    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")

    def __repr__(self):
        return f"<SaleItem(id={self.id}, product_id={self.product_id}, qty={self.quantity})>"
