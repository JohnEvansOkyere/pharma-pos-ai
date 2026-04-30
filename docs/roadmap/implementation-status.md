# Implementation Status

## Implemented

Core local POS:

- login/auth
- POS route
- product catalog
- product batches
- FEFO sale allocation
- sale records and sale items
- sale void/refund workflow
- stock adjustments
- stock takes
- inventory movements
- suppliers/categories
- notifications
- local dashboard

Operational controls:

- role and permission model
- admin user management
- backup status
- manual backup trigger
- restore drill readiness and technician drill recording
- diagnostics
- audit log viewer/export
- tamper-evident audit hash chain and admin integrity verification
- PostgreSQL production enforcement
- Alembic migration history

Hybrid cloud foundation:

- organizations, branches, devices
- local sync outbox
- upload worker
- cloud ingestion records
- cloud projection service
- cloud reporting tables
- cloud dashboard
- cloud reconciliation
- acknowledgement/resolution workflow
- admin repair tooling for supported cloud reconciliation issues

AI manager:

- read-only chat interface
- deterministic answer path
- OpenAI/Claude/Groq adapter support
- tenant AI provider policy
- safety refusals
- persisted weekly reports
- Sunday 7 PM style scheduled generation support
- email and Telegram delivery
- delivery retry records
- manager review metadata

## Partially Implemented

- tenant/branch columns are present in many areas, but older local flows still need deeper tenant hardening
- prescription and controlled-drug fields exist, but enforcement needs more server-side rules
- cloud sync supports reporting event flow, not full bidirectional operational sync
- AI is read-only and guarded, but prompt/version/evaluation governance can be improved
- audit chain incident handling can be expanded with scheduled checks and off-database anchoring

## Not Implemented

- true browser offline-first storage
- bidirectional cloud-to-branch sync
- automatic cloud repair for every reconciliation issue type
- full controlled-drug register workflow
- full prescription verification workflow
- destructive live restore automation
- advanced observability stack
