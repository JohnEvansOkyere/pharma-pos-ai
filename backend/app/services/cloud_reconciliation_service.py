"""
Reconciliation checks for cloud reporting projections.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.cloud_projection import (
    CloudBatchSnapshot,
    CloudInventoryMovementFact,
    CloudProductSnapshot,
    CloudReconciliationAcknowledgement,
)
from app.models.sync_ingestion import IngestedSyncEvent
from app.services.cloud_projection_service import CloudProjectionService
from app.services.audit_service import AuditService


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

        for issue in issues:
            issue["issue_key"] = CloudReconciliationService.issue_key(issue)
        CloudReconciliationService._apply_acknowledgements(db, organization_id=organization_id, issues=issues)

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
            "acknowledged_issue_count": sum(1 for issue in issues if issue.get("acknowledgement_status") == "acknowledged"),
            "resolved_issue_count": sum(1 for issue in issues if issue.get("acknowledgement_status") == "resolved"),
            "issues": limited_issues,
        }

    @staticmethod
    def acknowledge_issue(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        issue_key: str,
        notes: Optional[str],
        current_user_id: int,
    ) -> CloudReconciliationAcknowledgement:
        issue = CloudReconciliationService.find_active_issue(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            issue_key=issue_key,
        )
        if issue is None:
            raise ValueError("Active reconciliation issue not found")

        now = datetime.now(timezone.utc)
        acknowledgement = CloudReconciliationService._get_acknowledgement(
            db,
            organization_id=organization_id,
            issue_key=issue_key,
        )
        if acknowledgement is None:
            acknowledgement = CloudReconciliationAcknowledgement(
                organization_id=organization_id,
                issue_key=issue_key,
            )
            db.add(acknowledgement)

        acknowledgement.branch_id = issue.get("branch_id")
        acknowledgement.issue_type = issue["issue_type"]
        acknowledgement.severity = issue["severity"]
        acknowledgement.status = "acknowledged"
        acknowledgement.notes = notes.strip() if notes else None
        acknowledgement.acknowledged_by_user_id = current_user_id
        acknowledgement.acknowledged_at = now
        acknowledgement.resolved_by_user_id = None
        acknowledgement.resolved_at = None
        acknowledgement.resolution_notes = None
        db.flush()
        AuditService.log(
            db,
            action="acknowledge_cloud_reconciliation_issue",
            user_id=current_user_id,
            organization_id=organization_id,
            branch_id=acknowledgement.branch_id,
            entity_type="cloud_reconciliation_issue",
            entity_id=acknowledgement.id,
            description="Acknowledged cloud reconciliation issue",
            extra_data={
                "issue_key": issue_key,
                "issue_type": issue["issue_type"],
                "severity": issue["severity"],
                "notes_present": bool(acknowledgement.notes),
            },
        )
        db.commit()
        db.refresh(acknowledgement)
        return acknowledgement

    @staticmethod
    def resolve_issue(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        issue_key: str,
        notes: Optional[str],
        current_user_id: int,
    ) -> CloudReconciliationAcknowledgement:
        issue = CloudReconciliationService.find_active_issue(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            issue_key=issue_key,
        )
        acknowledgement = CloudReconciliationService._get_acknowledgement(
            db,
            organization_id=organization_id,
            issue_key=issue_key,
        )
        if acknowledgement is not None and branch_id is not None and acknowledgement.branch_id != branch_id:
            raise ValueError("Active reconciliation issue not found")
        if acknowledgement is None and issue is None:
            raise ValueError("Active reconciliation issue not found")
        if acknowledgement is None:
            acknowledgement = CloudReconciliationAcknowledgement(
                organization_id=organization_id,
                issue_key=issue_key,
                branch_id=issue.get("branch_id") if issue else branch_id,
                issue_type=issue["issue_type"] if issue else "unknown",
                severity=issue["severity"] if issue else "unknown",
                acknowledged_by_user_id=current_user_id,
                acknowledged_at=datetime.now(timezone.utc),
            )
            db.add(acknowledgement)
            db.flush()

        acknowledgement.status = "resolved"
        acknowledgement.resolved_by_user_id = current_user_id
        acknowledgement.resolved_at = datetime.now(timezone.utc)
        acknowledgement.resolution_notes = notes.strip() if notes else None
        if issue is not None:
            acknowledgement.branch_id = issue.get("branch_id")
            acknowledgement.issue_type = issue["issue_type"]
            acknowledgement.severity = issue["severity"]
        db.flush()
        AuditService.log(
            db,
            action="resolve_cloud_reconciliation_issue",
            user_id=current_user_id,
            organization_id=organization_id,
            branch_id=acknowledgement.branch_id,
            entity_type="cloud_reconciliation_issue",
            entity_id=acknowledgement.id,
            description="Marked cloud reconciliation issue workflow as resolved",
            extra_data={
                "issue_key": issue_key,
                "issue_type": acknowledgement.issue_type,
                "severity": acknowledgement.severity,
                "notes_present": bool(acknowledgement.resolution_notes),
            },
        )
        db.commit()
        db.refresh(acknowledgement)
        return acknowledgement

    @staticmethod
    def repair_issue(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        issue_key: Optional[str],
        repair_type: str,
        notes: Optional[str],
        limit: int,
        current_user_id: int,
    ) -> Dict[str, Any]:
        normalized_type = repair_type.strip().lower()
        if normalized_type == "retry_failed_projections":
            result = CloudReconciliationService._retry_failed_projections(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                limit=limit,
            )
        elif normalized_type == "rebuild_product_stock_total":
            if not issue_key:
                raise ValueError("issue_key is required for product stock total rebuild")
            issue = CloudReconciliationService.find_active_issue(
                db,
                organization_id=organization_id,
                branch_id=branch_id,
                issue_key=issue_key,
            )
            if issue is None:
                raise ValueError("Active reconciliation issue not found")
            if issue["issue_type"] != "product_batch_quantity_mismatch":
                raise ValueError("Only product_batch_quantity_mismatch can rebuild product stock total")
            result = CloudReconciliationService._rebuild_product_stock_total(
                db,
                organization_id=organization_id,
                issue=issue,
            )
        else:
            raise ValueError("Unsupported reconciliation repair type")

        AuditService.log(
            db,
            action="repair_cloud_reconciliation_issue",
            user_id=current_user_id,
            organization_id=organization_id,
            branch_id=branch_id,
            entity_type="cloud_reconciliation_repair",
            entity_id=None,
            description="Ran controlled cloud reconciliation repair",
            extra_data={
                "repair_type": normalized_type,
                "issue_key": issue_key,
                "attempted": result["attempted"],
                "repaired": result["repaired"],
                "failed": result["failed"],
                "skipped": result["skipped"],
                "notes_present": bool(notes and notes.strip()),
            },
        )
        db.commit()
        return {
            "organization_id": organization_id,
            "branch_id": branch_id,
            "repair_type": normalized_type,
            "issue_key": issue_key,
            **result,
        }

    @staticmethod
    def find_active_issue(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        issue_key: str,
    ) -> Optional[Dict[str, Any]]:
        result = CloudReconciliationService.reconcile(
            db,
            organization_id=organization_id,
            branch_id=branch_id,
            limit=500,
        )
        return next((issue for issue in result["issues"] if issue["issue_key"] == issue_key), None)

    @staticmethod
    def _retry_failed_projections(
        db: Session,
        *,
        organization_id: int,
        branch_id: Optional[int],
        limit: int,
    ) -> Dict[str, Any]:
        query = db.query(IngestedSyncEvent).filter(
            IngestedSyncEvent.organization_id == organization_id,
            IngestedSyncEvent.projection_error.is_not(None),
        )
        if branch_id is not None:
            query = query.filter(IngestedSyncEvent.branch_id == branch_id)
        events = query.order_by(IngestedSyncEvent.received_at.asc(), IngestedSyncEvent.id.asc()).limit(limit).all()

        attempted = repaired = failed = skipped = 0
        details: List[dict] = []
        for event in events:
            attempted += 1
            event_id = event.id
            try:
                event.projected_at = None
                was_projected = CloudProjectionService.project_event(db, event)
                event.projected_at = datetime.now(timezone.utc)
                event.projection_error = None
                if was_projected:
                    repaired += 1
                else:
                    skipped += 1
                details.append({"event_id": event.event_id, "status": "projected" if was_projected else "skipped"})
                db.commit()
            except Exception as exc:
                db.rollback()
                failed += 1
                failed_event = db.query(IngestedSyncEvent).filter(IngestedSyncEvent.id == event_id).one()
                failed_event.projection_error = str(exc)
                details.append({"event_id": failed_event.event_id, "status": "failed", "error": str(exc)})
                db.commit()

        return {
            "attempted": attempted,
            "repaired": repaired,
            "failed": failed,
            "skipped": skipped,
            "message": "Failed projection retry complete",
            "details": details,
        }

    @staticmethod
    def _rebuild_product_stock_total(
        db: Session,
        *,
        organization_id: int,
        issue: Dict[str, Any],
    ) -> Dict[str, Any]:
        branch_id = issue.get("branch_id")
        product_id = issue.get("product_id")
        if branch_id is None or product_id is None:
            return {
                "attempted": 1,
                "repaired": 0,
                "failed": 0,
                "skipped": 1,
                "message": "Issue is missing product scope",
                "details": [],
            }

        product = (
            db.query(CloudProductSnapshot)
            .filter(
                CloudProductSnapshot.organization_id == organization_id,
                CloudProductSnapshot.branch_id == branch_id,
                CloudProductSnapshot.local_product_id == product_id,
            )
            .first()
        )
        if product is None:
            return {
                "attempted": 1,
                "repaired": 0,
                "failed": 0,
                "skipped": 1,
                "message": "Product snapshot no longer exists",
                "details": [],
            }

        expected_quantity = int(issue.get("expected_quantity") or 0)
        old_quantity = product.total_stock
        product.total_stock = expected_quantity
        product.updated_at = datetime.now(timezone.utc)
        db.flush()
        return {
            "attempted": 1,
            "repaired": 1,
            "failed": 0,
            "skipped": 0,
            "message": "Product stock total rebuilt from batch snapshots",
            "details": [
                {
                    "branch_id": branch_id,
                    "product_id": product_id,
                    "old_total_stock": old_quantity,
                    "new_total_stock": expected_quantity,
                }
            ],
        }

    @staticmethod
    def issue_key(issue: Dict[str, Any]) -> str:
        scope = {
            "issue_type": issue.get("issue_type"),
            "branch_id": issue.get("branch_id"),
            "product_id": issue.get("product_id"),
            "batch_id": issue.get("batch_id"),
        }
        return hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _apply_acknowledgements(db: Session, *, organization_id: int, issues: List[Dict[str, Any]]) -> None:
        issue_keys = [issue["issue_key"] for issue in issues]
        if not issue_keys:
            return
        acknowledgements = (
            db.query(CloudReconciliationAcknowledgement)
            .filter(
                CloudReconciliationAcknowledgement.organization_id == organization_id,
                CloudReconciliationAcknowledgement.issue_key.in_(issue_keys),
            )
            .all()
        )
        by_key = {ack.issue_key: ack for ack in acknowledgements}
        for issue in issues:
            acknowledgement = by_key.get(issue["issue_key"])
            issue["acknowledgement_status"] = acknowledgement.status if acknowledgement else None
            issue["acknowledgement_notes"] = acknowledgement.notes if acknowledgement else None
            issue["acknowledged_by_user_id"] = acknowledgement.acknowledged_by_user_id if acknowledgement else None
            issue["acknowledged_at"] = acknowledgement.acknowledged_at if acknowledgement else None
            issue["resolved_by_user_id"] = acknowledgement.resolved_by_user_id if acknowledgement else None
            issue["resolved_at"] = acknowledgement.resolved_at if acknowledgement else None
            issue["resolution_notes"] = acknowledgement.resolution_notes if acknowledgement else None

    @staticmethod
    def _get_acknowledgement(
        db: Session,
        *,
        organization_id: int,
        issue_key: str,
    ) -> Optional[CloudReconciliationAcknowledgement]:
        return (
            db.query(CloudReconciliationAcknowledgement)
            .filter(
                CloudReconciliationAcknowledgement.organization_id == organization_id,
                CloudReconciliationAcknowledgement.issue_key == issue_key,
            )
            .first()
        )

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
