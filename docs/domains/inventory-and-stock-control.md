# Inventory And Stock Control

## Purpose

Inventory correctness is central to pharmacy safety. The system tracks product-level stock and batch-level stock, with expiry dates and quarantine support.

## Product Model

Products include:

- commercial and generic identity
- SKU and barcode
- dosage and strength
- category and supplier
- cost, selling, wholesale, and MRP values
- low-stock threshold
- reorder level and quantity
- active/inactive status
- regulatory and controlled-drug fields

## Batch Model

Batches include:

- organization and branch ownership
- product id
- batch number
- quantity
- manufacture date
- expiry date
- cost price
- storage location
- received date
- quarantine flag and reason

## Sellable Stock

Sellable stock excludes:

- expired batches
- quarantined batches
- zero or negative quantity batches

Product `total_stock` is recalculated from sellable batches by `InventoryService`.

## Stock Receiving

Product stock receiving should create or update batch quantity, recalculate product stock, record inventory movement, and emit sync event.

## Manual Stock Adjustments

Supported adjustment classes include:

- addition
- subtraction
- damage
- expired
- return
- correction

Rules:

- stock additions need a target batch
- returns need a target batch
- corrections need a target batch
- expiry write-offs need a target batch
- future-dated batches cannot be written off as expired
- decrement without selected batch consumes FEFO sellable batches

## Stock Takes

Stock takes are batch-level count workflows:

- create draft with expected and counted quantities
- complete draft to apply variance
- reject completion if batch stock changed after draft
- write stock adjustments and movement ledger records
- emit sync event
- audit completion

## Inventory Movement Ledger

Inventory movements record:

- organization, branch, and source device scope when available
- product
- batch
- movement type
- quantity delta
- stock after
- source document
- reason
- user

This ledger is the operational trace for stock changes.

## Scope Propagation

Inventory scope is written before the first database flush. The scope contract
applies to every stock-changing workflow:

- initial product batch creation;
- stock receipt into a new or existing batch;
- sale dispensing;
- sale void/refund stock restoration, including reconstructed batches;
- manual stock adjustments;
- physical stock-take corrections.

Each workflow carries the same organization and branch through its source
document, `ProductBatch`, `StockAdjustment`, `InventoryMovement`, sync event,
and audit entry. This keeps the append-only ledger and tamper-evident audit
chain aligned with the operational row that caused the stock change.

## Alerts And Notifications

The scheduler can create notifications for:

- low stock
- expiring products
- near-expiry products
- dead stock
- overstock

Existing low-stock and expiry threshold tracking remains deterministic. AI should explain, prioritize, and summarize these risks rather than replace core threshold enforcement.
