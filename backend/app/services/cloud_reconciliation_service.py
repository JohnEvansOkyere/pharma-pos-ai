"""
Reconciliation checks for cloud reporting projections.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.cloud_projection import CloudBatchSnapshot, CloudInventoryMovementFact, CloudProductSnapshot
from app.models.sync_ingestion import IngestedSyncEvent


class CloudReconciliationService:
    """Detect projection inconsistencies before managers trust reports."""

    @staticmethod
    def reconcile(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        product_query = db.query(CloudProductSnapshot).filter(
            CloudProductSnapshot.organization_id == organization_id,
            CloudProductSnapshot.is_active.is_(True),
        )
        batch_query = db.query(CloudBatchSnapshot).filter(CloudBatchSnapshot.organization_id == organization_id)
        movement_query = db.query(CloudInventoryMovementFact).filter(
            CloudInventoryMovementFact.organization_id == organization_id
        )
        failed_projection_query = db.query(IngestedSyncEvent).filter(
            IngestedSyncEvent.organization_id == organization_id,
            IngestedSyncEvent.projection_error.is_not(None),
        )

        if branch_id is not None:
            product_query = product_query.filter(CloudProductSnapshot.branch_id == branch_id)
            batch_query = batch_query.filter(CloudBatchSnapshot.branch_id == branch_id)
            movement_query = movement_query.filter(CloudInventoryMovementFact.branch_id == branch_id)
            failed_projection_query = failed_projection_query.filter(IngestedSyncEvent.branch_id == branch_id)

        products = product_query.all()
        batches = batch_query.all()
        movement_count = movement_query.count()
        projection_failed_count = failed_projection_query.count()
        product_by_scope = {
            (product.branch_id, product.local_product_id): product
            for product in products
        }
        batch_sum_by_product: Dict[Tuple[int, int], int] = defaultdict(int)
        issues: List[Dict[str, Any]] = []

        for batch in batches:
            if not batch.is_quarantined:
                batch_sum_by_product[(batch.branch_id, batch.local_product_id)] += batch.quantity

            product = product_by_scope.get((batch.branch_id, batch.local_product_id))
            if product is None:
                issues.append(
                    CloudReconciliationService._issue(
                        severity="high",
                        issue_type="orphan_batch_snapshot",
                        branch_id=batch.branch_id,
                        product_id=batch.local_product_id,
                        batch_id=batch.local_batch_id,
                        batch_number=batch.batch_number,
                        actual_quantity=batch.quantity,
                        message="Batch snapshot has no active product snapshot in the same organization and branch.",
                    )
                )
            if batch.quantity < 0:
                issues.append(
                    CloudReconciliationService._issue(
                        severity="critical",
                        issue_type="negative_batch_quantity",
                        branch_id=batch.branch_id,
                        product_id=batch.local_product_id,
                        batch_id=batch.local_batch_id,
                        batch_number=batch.batch_number,
                        actual_quantity=batch.quantity,
                        message="Batch snapshot quantity is negative.",
                    )
                )

        latest_stock_after_by_product = CloudReconciliationService._latest_stock_after_by_product(movement_query)
        for product in products:
            if product.total_stock < 0:
                issues.append(
                    CloudReconciliationService._issue(
                        severity="critical",
                        issue_type="negative_product_stock",
                        branch_id=product.branch_id,
                        product_id=product.local_product_id,
                        product_name=product.name,
                        actual_quantity=product.total_stock,
                        message="Product snapshot total stock is negative.",
                    )
                )

            expected_from_batches = batch_sum_by_product.get((product.branch_id, product.local_product_id), 0)
            if product.total_stock != expected_from_batches:
                issues.append(
                    CloudReconciliationService._issue(
                        severity="high",
                        issue_type="product_batch_quantity_mismatch",
                        branch_id=product.branch_id,
                        product_id=product.local_product_id,
                        product_name=product.name,
                        expected_quantity=expected_from_batches,
                        actual_quantity=product.total_stock,
                        delta=product.total_stock - expected_from_batches,
                        message="Product total stock does not equal the sum of non-quarantined batch quantities.",
                    )
                )

            latest_stock_after = latest_stock_after_by_product.get((product.branch_id, product.local_product_id))
            if latest_stock_after is not None and latest_stock_after != product.total_stock:
                issues.append(
                    CloudReconciliationService._issue(
                        severity="medium",
                        issue_type="latest_movement_stock_after_mismatch",
                        branch_id=product.branch_id,
                        product_id=product.local_product_id,
                        product_name=product.name,
                        expected_quantity=latest_stock_after,
                        actual_quantity=product.total_stock,
                        delta=product.total_stock - latest_stock_after,
                        message="Latest projected inventory movement stock_after does not match product snapshot total stock.",
                    )
                )

        if projection_failed_count:
            issues.append(
                CloudReconciliationService._issue(
                    severity="high",
                    issue_type="projection_failures_present",
                    branch_id=branch_id,
                    actual_quantity=projection_failed_count,
                    message="One or more ingested sync events failed projection; cloud reports may be incomplete.",
                )
            )

        issue_count = len(issues)
        limited_issues = issues[:limit]
        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "product_snapshot_count": len(products),
            "batch_snapshot_count": len(batches),
            "movement_fact_count": movement_count,
            "projection_failed_count": projection_failed_count,
            "issue_count": issue_count,
            "critical_issue_count": sum(1 for issue in issues if issue["severity"] == "critical"),
            "high_issue_count": sum(1 for issue in issues if issue["severity"] == "high"),
            "medium_issue_count": sum(1 for issue in issues if issue["severity"] == "medium"),
            "issues": limited_issues,
        }

    @staticmethod
    def _latest_stock_after_by_product(query) -> Dict[Tuple[int, int], int]:
        latest_rows = (
            query.filter(
                CloudInventoryMovementFact.local_product_id.is_not(None),
                CloudInventoryMovementFact.stock_after.is_not(None),
            )
            .with_entities(
                CloudInventoryMovementFact.branch_id,
                CloudInventoryMovementFact.local_product_id,
                CloudInventoryMovementFact.stock_after,
                CloudInventoryMovementFact.created_at,
                CloudInventoryMovementFact.id,
            )
            .order_by(
                CloudInventoryMovementFact.branch_id.asc(),
                CloudInventoryMovementFact.local_product_id.asc(),
                CloudInventoryMovementFact.created_at.asc(),
                CloudInventoryMovementFact.id.asc(),
            )
            .all()
        )
        latest: Dict[Tuple[int, int], int] = {}
        for row in latest_rows:
            latest[(row.branch_id, row.local_product_id)] = int(row.stock_after)
        return latest

    @staticmethod
    def _issue(
        *,
        severity: str,
        issue_type: str,
        message: str,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        batch_id: Optional[int] = None,
        product_name: Optional[str] = None,
        batch_number: Optional[str] = None,
        expected_quantity: Optional[int] = None,
        actual_quantity: Optional[int] = None,
        delta: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "severity": severity,
            "issue_type": issue_type,
            "branch_id": branch_id,
            "product_id": product_id,
            "batch_id": batch_id,
            "product_name": product_name,
            "batch_number": batch_number,
            "expected_quantity": expected_quantity,
            "actual_quantity": actual_quantity,
            "delta": delta,
            "message": message,
        }
