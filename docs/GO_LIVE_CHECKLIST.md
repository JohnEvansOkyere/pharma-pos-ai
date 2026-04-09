# Go-Live Checklist

## Purpose

Hard release gate for deciding whether this pharmacy system is dependable enough for a real client rollout.

This checklist is intentionally strict. A client machine should not go live until every Phase 1 item is complete and verified.

## Current Readiness

Current status: **not yet ready for unsupervised commercial rollout**

Reason:
- backups and diagnostics exist, but restore discipline and operational workflows still need broader rollout proof
- critical workflows still rely on manual validation in some client scenarios
- test coverage is still too thin for a safety-critical inventory and sales system
- some operational controls are still incomplete

## Phase 1: Operational Blockers

- [ ] Nightly database backups are automated on every client machine
- [ ] Backup retention is configured and verified
- [ ] Restore procedure has been tested on a real backup file
- [ ] End-of-day closeout is reviewed in pilot operations
- [ ] Sale void/refund control is verified in pilot operations
- [ ] Local PostgreSQL service is configured to start automatically
- [ ] Backend service is configured to start automatically
- [ ] A support technician can verify system health in under 5 minutes
- [ ] Demo credentials are removed from release-facing login and install materials
- [ ] Runtime `.env`, `.db`, and backup artifacts are excluded from packaged releases

Release evidence:
- screenshot or log showing nightly backup schedule installed
- at least one successful restore rehearsal
- startup verification after machine reboot

## Phase 2: Data Integrity And Traceability

- [ ] Sales flow has regression coverage
- [ ] Stock receipt flow has regression coverage
- [ ] Batch management flow has regression coverage
- [ ] User creation and login flow has regression coverage
- [ ] Product creation and pricing flow has regression coverage
- [ ] Sale void/refund flow has regression coverage
- [ ] Dashboard financial endpoint stability has regression coverage
- [ ] Critical stock and sales write paths emit audit records
- [ ] User management actions emit audit records
- [ ] Product master-data changes emit audit records

Release evidence:
- test run artifacts
- documented audit model and sample records

## Phase 3: Workflow Stability

- [ ] POS workflow is stable on common pharmacy workstation screen sizes
- [ ] Product add/edit/receive workflows match pharmacy operations
- [ ] Cashier login lands in the correct route and role scope
- [ ] Sidebar, POS layout, and search interactions work without operator confusion
- [ ] Receipt printing is verified with target printers
- [ ] Barcode scanner input path is verified

Release evidence:
- operator walkthrough with real sample inventory
- signoff from at least one real user or pharmacist

## Phase 4: Deployment And Supportability

- [ ] Install steps are documented and repeatable
- [ ] Backup and restore guide is included in deployment materials
- [ ] Support checklist is included for technicians
- [ ] Environment setup requires explicit secrets and DB credentials
- [ ] Machine-specific configuration is recorded for support
- [ ] Logs are accessible for troubleshooting

Release evidence:
- clean install on a fresh machine
- support handoff notes

## Recommended Immediate Order

1. automate backups and verify restore
2. verify sale reversal and closeout on pilot data
3. add regression tests for auth, products, stock receipt, and sales
4. add audit logging for critical writes
5. remove release-facing demo and dev artifacts
6. verify install/startup/recovery on a fresh machine

## What Counts As Dependable

The system becomes dependable enough for a supervised pilot when:
- backup automation is active
- restore has been tested
- auth and stock workflows are covered by regression tests
- core operator flows are stable in daily use

The system becomes dependable enough for broader client rollout when:
- all Phase 1 items are complete
- Phase 2 has no known critical gaps
- a fresh-machine install and recovery drill both succeed
