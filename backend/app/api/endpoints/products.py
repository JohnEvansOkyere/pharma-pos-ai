"""
Product management API endpoints.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.core.money import to_decimal, round_money
from app.db.base import get_db
from app.models.product import Product, ProductBatch
from app.models.stock_adjustment import AdjustmentType, StockAdjustment
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.inventory_service import InventoryService
from app.schemas.product import (
    Product as ProductSchema,
    ProductCreate,
    ProductUpdate,
    ProductWithBatches,
    ProductSearch,
    ProductSearchPage,
    ProductBatch as ProductBatchSchema,
    ProductBatchCreate,
    ProductBatchUpdate,
    ReceiveStock,
    StockReceiptResult,
)
from app.api.dependencies import get_current_active_user, require_manager

router = APIRouter(prefix="/products", tags=["Products"])


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_product_payload(payload: dict, *, require_identity_fields: bool) -> dict:
    for field in [
        "name",
        "generic_name",
        "sku",
        "barcode",
        "description",
        "strength",
        "active_ingredient",
        "manufacturer",
        "usage_instructions",
        "side_effects",
        "contraindications",
        "storage_conditions",
        "drug_license_number",
    ]:
        if field in payload:
            payload[field] = _normalize_optional_text(payload[field])

    if require_identity_fields and payload.get("name") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product name is required",
        )

    if require_identity_fields and payload.get("sku") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU is required",
        )

    return payload


def _validate_product_prices(
    *,
    cost_price: Optional[float],
    selling_price: Optional[float],
    mrp: Optional[float],
) -> None:
    cost_price_decimal = to_decimal(cost_price, allow_none=True)
    selling_price_decimal = to_decimal(selling_price, allow_none=True)
    mrp_decimal = to_decimal(mrp, allow_none=True)

    if (
        cost_price_decimal is not None
        and selling_price_decimal is not None
        and selling_price_decimal < cost_price_decimal
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selling price cannot be lower than cost price",
        )

    if (
        mrp_decimal is not None
        and selling_price_decimal is not None
        and selling_price_decimal > mrp_decimal
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selling price cannot be greater than MRP",
        )


def _normalize_product_money_fields(payload: dict) -> dict:
    for field in ["cost_price", "selling_price", "wholesale_price", "mrp"]:
        if field in payload and payload[field] is not None:
            payload[field] = round_money(payload[field])
    return payload


def _validate_batch_dates(
    *,
    expiry_date: Optional[date],
    manufacture_date: Optional[date],
) -> None:
    if expiry_date is not None and expiry_date <= date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock batches must have a future expiry date",
        )

    if (
        manufacture_date is not None
        and expiry_date is not None
        and manufacture_date >= expiry_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manufacture date must be earlier than expiry date",
        )


def _refresh_product_stocks(db: Session, products: List[Product]) -> None:
    """Normalize stored sellable stock for the products being returned."""
    stock_changed = False
    for product in products:
        previous_stock = product.total_stock
        current_stock = InventoryService.recalculate_product_stock(db, product)
        if current_stock != previous_stock:
            stock_changed = True

    if stock_changed:
        db.commit()


def _nearest_expiry_by_product_ids(db: Session, product_ids: List[int]) -> dict[int, Optional[date]]:
    if not product_ids:
        return {}

    rows = db.query(
        ProductBatch.product_id,
        func.min(ProductBatch.expiry_date).label("nearest_expiry"),
    ).filter(
        ProductBatch.product_id.in_(product_ids),
        ProductBatch.quantity > 0,
        ProductBatch.is_quarantined == False,
        ProductBatch.expiry_date >= date.today(),
    ).group_by(ProductBatch.product_id).all()

    return {row.product_id: row.nearest_expiry for row in rows}


def _serialize_product_search_rows(
    db: Session,
    products: List[Product],
    *,
    nearest_expiry_map: Optional[dict[int, Optional[date]]] = None,
) -> List[dict]:
    """Build product search rows with derived display fields."""
    if nearest_expiry_map is None:
        nearest_expiry_map = _nearest_expiry_by_product_ids(db, [product.id for product in products])

    result = []
    for product in products:
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
            "category_name": product.category.name if product.category else None,
            "nearest_expiry": nearest_expiry_map.get(product.id),
        }
        result.append(product_dict)

    return result


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
    query = db.query(Product).options(joinedload(Product.category))

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    products = query.offset(skip).limit(limit).all()
    _refresh_product_stocks(db, products)
    nearest_expiry_map = _nearest_expiry_by_product_ids(db, [product.id for product in products])
    return _serialize_product_search_rows(db, products, nearest_expiry_map=nearest_expiry_map)


@router.get("/catalog", response_model=ProductSearchPage)
def list_products_catalog(
    q: Optional[str] = Query(None, min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    category_id: Optional[int] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Paginated product catalog for operator search screens."""
    query = db.query(Product).options(joinedload(Product.category))

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    if q:
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.barcode.ilike(search_term),
                Product.generic_name.ilike(search_term),
            )
        )

    total = query.count()
    products = query.order_by(Product.name.asc()).offset(skip).limit(limit).all()
    _refresh_product_stocks(db, products)
    nearest_expiry_map = _nearest_expiry_by_product_ids(db, [product.id for product in products])

    return {
        "items": _serialize_product_search_rows(db, products, nearest_expiry_map=nearest_expiry_map),
        "total": total,
        "skip": skip,
        "limit": limit,
    }


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
    products = db.query(Product).options(joinedload(Product.category)).filter(
        or_(
            Product.name.ilike(search_term),
            Product.sku.ilike(search_term),
            Product.barcode.ilike(search_term),
            Product.generic_name.ilike(search_term)
        ),
        Product.is_active == True
    ).limit(limit).all()
    _refresh_product_stocks(db, products)
    nearest_expiry_map = _nearest_expiry_by_product_ids(db, [product.id for product in products])
    return _serialize_product_search_rows(db, products, nearest_expiry_map=nearest_expiry_map)


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
    payload = _normalize_product_payload(
        product.model_dump(),
        require_identity_fields=True,
    )
    payload = _normalize_product_money_fields(payload)
    _validate_product_prices(
        cost_price=payload.get("cost_price"),
        selling_price=payload.get("selling_price"),
        mrp=payload.get("mrp"),
    )

    # Check for duplicate SKU
    if db.query(Product).filter(Product.sku == payload["sku"]).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU already exists"
        )

    # Check for duplicate barcode if provided
    if payload.get("barcode") and db.query(Product).filter(Product.barcode == payload["barcode"]).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode already exists"
        )

    db_product = Product(**payload)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    AuditService.log(
        db,
        action="create_product",
        user_id=current_user.id,
        entity_type="product",
        entity_id=db_product.id,
        description=f"Created product {db_product.name}",
        extra_data={"sku": db_product.sku},
    )
    db.commit()

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

    update_data = _normalize_product_payload(
        product_update.model_dump(exclude_unset=True),
        require_identity_fields=False,
    )
    update_data = _normalize_product_money_fields(update_data)

    if "sku" in update_data:
        duplicate_sku = db.query(Product).filter(
            Product.sku == update_data["sku"],
            Product.id != product_id,
        ).first()
        if duplicate_sku:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SKU already exists",
            )

    if "barcode" in update_data and update_data["barcode"]:
        duplicate_barcode = db.query(Product).filter(
            Product.barcode == update_data["barcode"],
            Product.id != product_id,
        ).first()
        if duplicate_barcode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Barcode already exists",
            )

    _validate_product_prices(
        cost_price=update_data.get("cost_price", db_product.cost_price),
        selling_price=update_data.get("selling_price", db_product.selling_price),
        mrp=update_data.get("mrp", db_product.mrp),
    )

    for field, value in update_data.items():
        setattr(db_product, field, value)

    db.commit()
    db.refresh(db_product)
    AuditService.log(
        db,
        action="update_product",
        user_id=current_user.id,
        entity_type="product",
        entity_id=db_product.id,
        description=f"Updated product {db_product.name}",
        extra_data={"updated_fields": sorted(update_data.keys())},
    )
    db.commit()

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
    AuditService.log(
        db,
        action="deactivate_product",
        user_id=current_user.id,
        entity_type="product",
        entity_id=db_product.id,
        description=f"Deactivated product {db_product.name}",
        extra_data={"sku": db_product.sku},
    )
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

    batch_data = batch.model_dump(exclude={'product_id'})
    batch_data["cost_price"] = round_money(batch_data["cost_price"])
    batch_data["batch_number"] = batch_data["batch_number"].strip()
    if not batch_data["batch_number"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch number is required",
        )
    batch_data["location"] = _normalize_optional_text(batch_data.get("location"))
    _validate_batch_dates(
        expiry_date=batch_data.get("expiry_date"),
        manufacture_date=batch_data.get("manufacture_date"),
    )

    duplicate_batch = db.query(ProductBatch).filter(
        ProductBatch.product_id == product_id,
        ProductBatch.batch_number == batch_data["batch_number"],
        ProductBatch.expiry_date == batch_data["expiry_date"],
    ).first()
    if duplicate_batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A batch with the same batch number and expiry date already exists for this product",
        )

    # Create batch
    db_batch = ProductBatch(
        product_id=product_id,
        **batch_data
    )
    db.add(db_batch)

    InventoryService.recalculate_product_stock(db, product)

    db.commit()
    db.refresh(db_batch)
    AuditService.log(
        db,
        action="create_product_batch",
        user_id=current_user.id,
        entity_type="product_batch",
        entity_id=db_batch.id,
        description=f"Created batch {db_batch.batch_number} for product {product.name}",
        extra_data={"product_id": product.id, "quantity": db_batch.quantity},
    )
    db.commit()

    return db_batch


@router.put("/{product_id}/batches/{batch_id}", response_model=ProductBatchSchema)
def update_product_batch(
    product_id: int,
    batch_id: int,
    batch_update: ProductBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Update operational batch metadata such as location, expiry, quarantine
    status, and corrected batch identifiers.
    """
    try:
        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        batch = db.query(ProductBatch).filter(
            ProductBatch.id == batch_id,
            ProductBatch.product_id == product_id,
        ).with_for_update().first()
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found for the selected product",
            )

        update_data = batch_update.model_dump(exclude_unset=True)
        if "cost_price" in update_data and update_data["cost_price"] is not None:
            update_data["cost_price"] = round_money(update_data["cost_price"])
        if "batch_number" in update_data:
            batch_number = (update_data["batch_number"] or "").strip()
            if not batch_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Batch number is required",
                )
            update_data["batch_number"] = batch_number

        _validate_batch_dates(
            expiry_date=update_data.get("expiry_date", batch.expiry_date),
            manufacture_date=update_data.get("manufacture_date", batch.manufacture_date),
        )

        target_batch_number = update_data.get("batch_number", batch.batch_number)
        target_expiry_date = update_data.get("expiry_date", batch.expiry_date)
        duplicate_batch = db.query(ProductBatch).filter(
            ProductBatch.product_id == product_id,
            ProductBatch.id != batch.id,
            ProductBatch.batch_number == target_batch_number,
            ProductBatch.expiry_date == target_expiry_date,
        ).first()
        if duplicate_batch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another batch already exists with the same batch number and expiry date",
            )

        target_is_quarantined = update_data.get("is_quarantined", batch.is_quarantined)
        target_quarantine_reason = update_data.get("quarantine_reason", batch.quarantine_reason)
        if target_is_quarantined and not (target_quarantine_reason or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quarantine reason is required when quarantining a batch",
            )

        for field, value in update_data.items():
            setattr(batch, field, value)

        if not batch.is_quarantined:
            batch.quarantine_reason = None

        InventoryService.recalculate_product_stock(db, product)
        db.commit()
        db.refresh(batch)
        AuditService.log(
            db,
            action="update_product_batch",
            user_id=current_user.id,
            entity_type="product_batch",
            entity_id=batch.id,
            description=f"Updated batch {batch.batch_number} for product {product.name}",
            extra_data={"updated_fields": sorted(update_data.keys())},
        )
        db.commit()
        return batch
    except Exception:
        db.rollback()
        raise


@router.post("/{product_id}/receive-stock", response_model=StockReceiptResult, status_code=status.HTTP_201_CREATED)
def receive_stock(
    product_id: int,
    receipt: ReceiveStock,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Receive stock for an existing product in one transaction.
    Creates or updates a batch, refreshes sellable stock, optionally updates
    product pricing, and records the stock movement.
    """
    try:
        batch_number = receipt.batch_number.strip()
        if not batch_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch number is required",
            )

        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive products cannot receive stock",
            )

        receipt_cost_price = round_money(receipt.cost_price)
        receipt_selling_price = round_money(receipt.selling_price) if receipt.selling_price is not None else None
        receipt_wholesale_price = round_money(receipt.wholesale_price) if receipt.wholesale_price is not None else None
        receipt_mrp = round_money(receipt.mrp) if receipt.mrp is not None else None

        _validate_batch_dates(
            expiry_date=receipt.expiry_date,
            manufacture_date=receipt.manufacture_date,
        )
        _validate_product_prices(
            cost_price=receipt_cost_price,
            selling_price=receipt_selling_price or product.selling_price,
            mrp=receipt_mrp if receipt_mrp is not None else product.mrp,
        )

        previous_stock = InventoryService.recalculate_product_stock(db, product)
        price_updated = False

        existing_batch = db.query(ProductBatch).filter(
            ProductBatch.product_id == product.id,
            ProductBatch.batch_number == batch_number,
            ProductBatch.expiry_date == receipt.expiry_date,
        ).with_for_update().first()

        if existing_batch:
            if existing_batch.is_quarantined:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot receive into a quarantined batch. Use a new batch or resolve the quarantine first.",
                )
            existing_batch.quantity += receipt.quantity
            existing_batch.cost_price = receipt_cost_price
            existing_batch.manufacture_date = receipt.manufacture_date
            existing_batch.location = _normalize_optional_text(receipt.location)
            batch = existing_batch
        else:
            batch = ProductBatch(
                product_id=product.id,
                batch_number=batch_number,
                quantity=receipt.quantity,
                expiry_date=receipt.expiry_date,
                cost_price=receipt_cost_price,
                manufacture_date=receipt.manufacture_date,
                location=_normalize_optional_text(receipt.location),
            )
            db.add(batch)
            db.flush()

        product.cost_price = receipt_cost_price
        if receipt_selling_price is not None:
            product.selling_price = receipt_selling_price
            price_updated = True
        if receipt_wholesale_price is not None:
            product.wholesale_price = receipt_wholesale_price
            price_updated = True
        if receipt_mrp is not None:
            product.mrp = receipt_mrp
            price_updated = True

        new_stock = InventoryService.recalculate_product_stock(db, product)

        db.add(
            StockAdjustment(
                product_id=product.id,
                batch_id=batch.id,
                adjustment_type=AdjustmentType.ADDITION,
                quantity=receipt.quantity,
                reason=(receipt.reason or "Stock receipt").strip(),
                performed_by=current_user.id,
            )
        )

        db.commit()
        db.refresh(product)
        db.refresh(batch)
        AuditService.log(
            db,
            action="receive_stock",
            user_id=current_user.id,
            entity_type="product_batch",
            entity_id=batch.id,
            description=f"Received stock into batch {batch.batch_number} for product {product.name}",
            extra_data={"product_id": product.id, "quantity": receipt.quantity, "new_stock": new_stock},
        )
        db.commit()

        return {
            "product": product,
            "batch": batch,
            "previous_stock": previous_stock,
            "new_stock": new_stock,
            "price_updated": price_updated,
        }
    except Exception:
        db.rollback()
        raise


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
    products = db.query(Product).filter(Product.is_active == True).all()
    _refresh_product_stocks(db, products)

    products = [
        product
        for product in products
        if product.total_stock <= product.low_stock_threshold
    ]

    return products
