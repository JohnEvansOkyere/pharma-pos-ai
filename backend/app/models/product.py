"""
Product and ProductBatch models for inventory management.
"""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Product(Base):
    """Product master data model."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    generic_name = Column(String(200))
    sku = Column(String(50), unique=True, nullable=False, index=True)
    barcode = Column(String(100), unique=True, index=True)
    description = Column(Text)

    # Pricing
    cost_price = Column(Float, nullable=False)  # Purchase/cost price
    selling_price = Column(Float, nullable=False)  # Retail price
    mrp = Column(Float)  # Maximum retail price

    # Inventory
    total_stock = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=10, nullable=False)

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
        return f"<Product(id={self.id}, name='{self.name}', sku='{self.sku}')>"


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

    # Relationship
    product = relationship("Product", back_populates="batches")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ProductBatch(id={self.id}, batch='{self.batch_number}', expiry='{self.expiry_date}')>"
