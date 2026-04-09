# Missing Operational Controls Checklist

This is the shortlist of pharmacy-critical operational controls that should exist before broad client rollout.

## Already Present

- Backup status and manual backup trigger
- Local diagnostics endpoint and settings screen
- Critical write audit logging
- Batch-aware stock deduction
- Low-stock and expiry visibility

## Highest Priority Still Needed

### 1. Sale Void And Refund Control

Why it matters:
- protects cash accountability
- prevents silent stock mismatches
- gives managers a controlled reversal path

Required behavior:
- cashier cannot silently erase a sale
- manager/admin must provide a reason
- stock must be restored correctly
- action must be audited

Status:
- started

### 2. End-Of-Day Closeout

Why it matters:
- owner needs a daily business control point
- makes reconciliation easier
- exposes payment mix and reversal activity

Required behavior:
- total completed sales
- total refunded/voided sales
- payment method totals
- transaction counts
- optional operator/date filtering later

Status:
- started

### 3. Stock Take / Physical Count Workflow

Why it matters:
- pharmacies eventually drift without stock counts
- correction without a count workflow becomes risky

Required behavior:
- record counted quantity
- compare against system quantity
- approve variance
- write audited correction entries

Status:
- not started

### 4. Price Change History And Approval Trail

Why it matters:
- protects margin
- reduces staff abuse or accidental price changes

Required behavior:
- before/after values
- who changed the price
- when it changed
- optional manager approval path

Status:
- partially covered by audit logs, not yet structured

### 5. Receipt Reprint Tracking

Why it matters:
- helps prevent abuse and supports customer disputes

Required behavior:
- reprint count
- who reprinted
- when it happened

Status:
- fields exist, workflow not complete

## Next Priority

- shift handover and cash reconciliation
- backup health warning on main dashboard
- restore verification checklist in-app
- support export bundle for troubleshooting
- upgrade preflight checks before migration

## Recommended Execution Order

1. sale void and refund control
2. end-of-day closeout
3. stock take workflow
4. structured price history
5. receipt reprint tracking
6. shift reconciliation
7. support export bundle

## Rollout Rule

Do not treat nice dashboards as a substitute for operational controls.
The system becomes trustworthy when reversal, closeout, stock counting, backup awareness, and recovery are routine and auditable.
