# Recommended Next Improvements

## 1. Audit Integrity Operations

Hash chaining for new audit events is implemented. The next improvement is operationalizing it.

Why:

- pharmacy systems need strong accountability
- admin repair, stock, sale reversal, and AI policy actions must be defensible
- broken chains must have a clear response process

Expected scope:

- scheduled integrity verification
- dashboard alerting when verification fails
- incident checklist linked from the UI
- optional off-database hash anchoring
- restore/forensics playbook

## 2. Prescription And Controlled-Drug Enforcement

Turn existing metadata into hard server-side controls.

Expected scope:

- prescription-required sale validation
- required prescription number/doctor fields
- required customer ID where configured
- controlled-drug sale audit enhancement
- manager override policy if required by business process

## 3. Restore Drill Operations

Restore drill readiness and recording are implemented. The next step is making the drill process more operationally rigorous.

Expected scope:

- technician checklist templates
- post-restore integrity check script
- printable handoff report
- restore drill reminders
- optional separate-machine restore helper

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
