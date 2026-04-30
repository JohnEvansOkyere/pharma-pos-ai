# Transactions And Integrity

## ACID Requirements

The core pharmacy workflows must be ACID-safe:

- sale creation
- sale void/refund
- product stock receiving
- stock adjustment
- stock take completion
- sync outbox event creation
- audit log creation for critical actions

The backend owns these workflows. Frontend state must never be treated as authoritative for stock, price, or permissions.

## Sale Transaction Flow

Sale creation does the following inside one backend transaction:

1. Lock product rows with `with_for_update`.
2. Recalculate sellable stock from valid batches.
3. Reject inactive products.
4. Reject insufficient stock.
5. Allocate batches using FEFO.
6. Calculate sale totals on the backend.
7. Decrement batch quantities.
8. Recalculate product total stock.
9. Create sale and sale item records.
10. Record inventory movements.
11. Write a sync outbox event.
12. Write audit logs where applicable.
13. Commit.

If any step fails, the transaction rolls back.

## FEFO Rule

FEFO means first-expiry-first-out. Sellable batches are:

- quantity greater than zero
- not quarantined
- not expired

Allocation order:

1. earliest expiry date
2. earliest received date
3. lowest batch id

This is critical for pharmacy stock safety and waste reduction.

## Stock Adjustments

Stock adjustments are manager/admin controlled through permissions.

Rules:

- additions and returns require a batch
- corrections require a batch
- expiry write-offs require a batch
- future-dated batches cannot be marked expired
- decrement without explicit batch consumes sellable batches in FEFO order
- every stock-changing adjustment writes inventory movements and a sync event

## Stock Takes

Stock take workflow:

1. Create draft from batch-level physical counts.
2. Store expected quantity at draft creation.
3. Complete only if the batch quantity has not changed since draft creation.
4. Apply variance corrections.
5. Record adjustment rows and inventory movements.
6. Write sync outbox event.
7. Write audit log.

The expected-quantity check prevents applying stale count data after another stock movement.

## Sale Reversal

Voids and refunds are controlled workflows:

- only completed sales can be reversed
- reason is required
- stock is restored to original or recreated restoration batch
- sale status changes to void/refunded target
- reversal document is created
- inventory movement is recorded
- sync event is emitted
- audit event is written

## Sync Outbox Atomicity

The local sync outbox event is written inside the same database transaction as the business change. This is the correct pattern for reliable cloud reporting.

Do not emit cloud events from frontend code or after a separate non-transactional process unless a durable outbox record already exists.

## Current Integrity Gaps To Keep On The Roadmap

- Add tamper-evident chaining to `activity_logs`.
- Broaden server-side enforcement for prescription-only and controlled-drug sales.
- Add more tenant/branch scope checks on older operational endpoints where nullable tenant fields still exist.
- Add restore drill automation and verification.
- Add database-level constraints where app-level checks are not enough.
