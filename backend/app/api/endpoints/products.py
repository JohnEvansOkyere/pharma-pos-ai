"""
Product management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.base import get_db
from app.models.product import Product, ProductBatch
from app.models.user import User
from app.schemas.product import (
    Product as ProductSchema,
    ProductCreate,
    ProductUpdate,
    ProductWithBatches,
    ProductSearch,
    ProductBatch as ProductBatchSchema,
    ProductBatchCreate,
)
from app.api.dependencies import get_current_active_user, require_manager

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=List[ProductSearch])
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=10000),
    category_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all products with pagination and filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        category_id: Filter by category
        is_active: Filter by active status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of products with expiry information
    """
    from sqlalchemy import func

    query = db.query(Product)

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    products = query.offset(skip).limit(limit).all()

    # Enrich products with nearest expiry date from batches and category name
    from app.models.category import Category

    result = []
    for product in products:
        # Get category name
        category_name = None
        if product.category_id:
            category = db.query(Category).filter(Category.id == product.category_id).first()
            if category:
                category_name = category.name

        product_dict = {
            "id": product.id,
            "name": product.name,
            "generic_name": product.generic_name,
            "sku": product.sku,
            "barcode": product.barcode,
            "dosage_form": product.dosage_form,
            "strength": product.strength,
            "selling_price": product.selling_price,
            "cost_price": product.cost_price,
            "total_stock": product.total_stock,
            "low_stock_threshold": product.low_stock_threshold,
            "manufacturer": product.manufacturer,
            "category_name": category_name,
            "nearest_expiry": None
        }

        # Get earliest expiry date from non-quarantined batches
        earliest_batch = db.query(ProductBatch).filter(
            ProductBatch.product_id == product.id,
            ProductBatch.is_quarantined == False,
            ProductBatch.quantity > 0
        ).order_by(ProductBatch.expiry_date.asc()).first()

        if earliest_batch:
            product_dict["nearest_expiry"] = earliest_batch.expiry_date

        result.append(product_dict)

    return result


@router.get("/search", response_model=List[ProductSearch])
def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search products by name, SKU, or barcode.

    Args:
        q: Search query
        limit: Maximum results
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of matching products with expiry information
    """
    search_term = f"%{q}%"
    products = db.query(Product).filter(
        or_(
            Product.name.ilike(search_term),
            Product.sku.ilike(search_term),
            Product.barcode.ilike(search_term),
            Product.generic_name.ilike(search_term)
        ),
        Product.is_active == True
    ).limit(limit).all()

    # Enrich products with nearest expiry date from batches and category name
    from app.models.category import Category

    result = []
    for product in products:
        # Get category name
        category_name = None
        if product.category_id:
            category = db.query(Category).filter(Category.id == product.category_id).first()
            if category:
                category_name = category.name

        product_dict = {
            "id": product.id,
            "name": product.name,
            "generic_name": product.generic_name,
            "sku": product.sku,
            "barcode": product.barcode,
            "dosage_form": product.dosage_form,
            "strength": product.strength,
            "selling_price": product.selling_price,
            "cost_price": product.cost_price,
            "total_stock": product.total_stock,
            "low_stock_threshold": product.low_stock_threshold,
            "manufacturer": product.manufacturer,
            "category_name": category_name,
            "nearest_expiry": None
        }

        # Get earliest expiry date from non-quarantined batches
        earliest_batch = db.query(ProductBatch).filter(
            ProductBatch.product_id == product.id,
            ProductBatch.is_quarantined == False,
            ProductBatch.quantity > 0
        ).order_by(ProductBatch.expiry_date.asc()).first()

        if earliest_batch:
            product_dict["nearest_expiry"] = earliest_batch.expiry_date

        result.append(product_dict)

    return result


@router.get("/{product_id}", response_model=ProductWithBatches)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific product by ID with batches.

    Args:
        product_id: Product ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Product with batches

    Raises:
        HTTPException: If product not found
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product


@router.post("", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """
    Create a new product.
    Requires manager or admin role.

    Args:
        product: Product data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created product

    Raises:
        HTTPException: If SKU or barcode already exists
    """
    # Check for duplicate SKU
    if db.query(Product).filter(Product.sku == product.sku).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU already exists"
        )

    # Check for duplicate barcode if provided
    if product.barcode and db.query(Product).filter(Product.barcode == product.barcode).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode already exists"
        )

    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product


@router.put("/{product_id}", response_model=ProductSchema)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """
    Update a product.
    Requires manager or admin role.

    Args:
        product_id: Product ID
        product_update: Updated product data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated product

    Raises:
        HTTPException: If product not found
    """
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Update fields
    update_data = product_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)

    db.commit()
    db.refresh(db_product)

    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """
    Delete a product (soft delete by marking inactive).
    Requires manager or admin role.

    Args:
        product_id: Product ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If product not found
    """
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    db_product.is_active = False
    db.commit()


@router.post("/{product_id}/batches", response_model=ProductBatchSchema, status_code=status.HTTP_201_CREATED)
def add_product_batch(
    product_id: int,
    batch: ProductBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """
    Add a new batch for a product.
    Requires manager or admin role.

    Args:
        product_id: Product ID
        batch: Batch data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created batch

    Raises:
        HTTPException: If product not found
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Create batch
    db_batch = ProductBatch(
        product_id=product_id,
        **batch.model_dump(exclude={'product_id'})
    )
    db.add(db_batch)

    # Update product stock
    product.total_stock += batch.quantity

    db.commit()
    db.refresh(db_batch)

    return db_batch


@router.get("/low-stock", response_model=List[ProductSchema])
def get_low_stock_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get products with stock below threshold.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of low stock products
    """
    products = db.query(Product).filter(
        Product.total_stock <= Product.low_stock_threshold,
        Product.is_active == True
    ).all()

    return products
