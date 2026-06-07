# Documentation Index

## Purpose

This folder contains the current working documentation for Pharma POS AI.

The documentation is organized by audience:

- developers
- client operators
- installation/support technicians
- release and backup operations

## Start Here

### Full System Architecture

- [Architecture Documentation](architecture/README.md)
- [Data Documentation](data/README.md)
- [Domain Documentation](domains/README.md)
- [Security Documentation](security/README.md)
- [AI Documentation](ai/README.md)
- [Operations Documentation](operations/README.md)
- [Roadmap Documentation](roadmap/README.md)

Use these for:
- understanding what the system is
- understanding local-first and hybrid cloud architecture
- understanding database design, ACID rules, and sync flow
- understanding pharmacy workflows and safety boundaries
- understanding AI, reporting, operations, and remaining production work

### For Developers

- [Developer Guide](/home/grejoy/Projects/pharma-pos-ai/docs/DEVELOPER_GUIDE.md)

Use this for:
- local development setup
- architecture orientation
- critical workflow expectations
- release discipline
- current hardening status
- operational-control roadmap

### For Pharmacy Operators

- [Client User Guide](/home/grejoy/Projects/pharma-pos-ai/docs/CLIENT_USER_GUIDE.md)

Use this for:
- daily system use
- logging in
- POS workflow
- product and stock workflows
- backup awareness
- sale reversal rules
- closeout expectations

### For Installers And Support Technicians

#### City Pharmacy (hosted operational deployment, internet required)

- [**SETUP_ONLINE_CITY_PHARMACY.md**](SETUP_ONLINE_CITY_PHARMACY.md)

Use this for: the historical city setup flow. The shared-Supabase instructions
are superseded by the dedicated Render backend/database topology and must be
revised before client use.

#### Village / Rural Pharmacy (offline operational deployment)

- [**SETUP_OFFLINE_VILLAGE_PHARMACY.md**](SETUP_OFFLINE_VILLAGE_PHARMACY.md)

Use this for: offline install on a local machine, configuring local PostgreSQL and nightly backups, optional cloud sync, UPS guidance, and the village handover checklist.

#### Technical Reference

- [Windows Local Deployment Runbook](WINDOWS_LOCAL_DEPLOYMENT_RUNBOOK.md) — detailed technical reference for the offline profile

### For Backup And Recovery

- [Backup And Restore Guide](/home/grejoy/Projects/pharma-pos-ai/docs/BACKUP_RESTORE_GUIDE.md)

Use this for:
- manual backups
- restore procedure
- retention expectations
- scheduled backup notes

### For Release Decisions

- [Go-Live Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/GO_LIVE_CHECKLIST.md)

Use this for:
- deciding whether a build is dependable enough to ship
- checking operational readiness
- tracking remaining blockers

### For Operational Gaps

- [Missing Operational Controls Checklist](/home/grejoy/Projects/pharma-pos-ai/docs/MISSING_OPERATIONAL_CONTROLS_CHECKLIST.md)

Use this for:
- identifying what still separates the system from a stronger pharmacy rollout
- prioritizing operational safeguards
- planning hardening work after audit findings

### For Hybrid Cloud Production Architecture

- [Hybrid Cloud Production Architecture Plan](/home/grejoy/Projects/pharma-pos-ai/docs/HYBRID_CLOUD_PRODUCTION_ARCHITECTURE_PLAN.md)

Use this for:
- multi-client and branch architecture decisions
- local-first/cloud sync planning
- ACID and database correctness rules
- audit, backup, security, and AI boundaries
- rollout sequencing for the scalable cloud product

## Existing Planning And Audit Docs

These documents remain useful, but they are not the main entry points for day-to-day work:

- [Client Installation Plan](/home/grejoy/Projects/pharma-pos-ai/docs/CLIENT_INSTALLATION_PLAN.md)
- [Offline Deployment Strategy](/home/grejoy/Projects/pharma-pos-ai/docs/OFFLINE_DEPLOYMENT_STRATEGY.md)
- [Backend Audit Recommendations](/home/grejoy/Projects/pharma-pos-ai/docs/audits/add_remove_recommendations.md)

## Historical Notes

Older project notes and legacy deployment writeups are kept in:

- [docs/root-docs](/home/grejoy/Projects/pharma-pos-ai/docs/root-docs)

Treat those as historical reference, not as the default operating documentation.
