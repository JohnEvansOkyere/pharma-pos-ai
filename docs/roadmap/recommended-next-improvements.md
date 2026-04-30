# Recommended Next Improvements

## 1. Tamper-Evident Audit Logs

Add hash chaining for critical audit events.

Why:

- pharmacy systems need strong accountability
- admin repair, stock, sale reversal, and AI policy actions must be defensible
- ordinary audit rows can be silently edited by direct database access

Expected scope:

- previous hash
- current hash
- canonical event payload
- verifier service
- admin endpoint
- dashboard status
- tests for broken chain detection

## 2. Prescription And Controlled-Drug Enforcement

Turn existing metadata into hard server-side controls.

Expected scope:

- prescription-required sale validation
- required prescription number/doctor fields
- required customer ID where configured
- controlled-drug sale audit enhancement
- manager override policy if required by business process

## 3. Backup Restore Drill Automation

Add guided restore verification.

Expected scope:

- restore checklist endpoint or script
- post-restore integrity checks
- backup metadata verification
- operator-facing restore status documentation

## 4. Tenant/Branch Hardening

Continue moving single-site assumptions to explicit tenant scope.

Expected scope:

- enforce organization/branch on critical writes
- update old nullable operational rows where practical
- add tests for branch user isolation
- add cloud report tenant-leak tests

## 5. Sync Operations Maturity

Improve cloud sync recovery.

Expected scope:

- better failed event dashboard
- event replay controls
- dead-letter queue concept
- projection versioning
- backfill commands

## 6. AI Governance

Improve robustness around AI.

Expected scope:

- prompt versioning
- saved report generation metadata
- evaluation fixtures for AI reports
- provider health checks
- explicit manager acceptance workflow for high-risk recommendations
