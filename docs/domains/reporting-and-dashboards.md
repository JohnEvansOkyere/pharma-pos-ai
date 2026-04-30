# Reporting And Dashboards

## Local Dashboard

The local dashboard provides operational visibility for the local installation. It should not block the POS workflow if non-critical dashboard requests fail.

Local reports include sales summaries, inventory summaries, and operational status cards.

## Cloud Dashboard

The cloud dashboard is for manager/owner visibility across branch event projections.

Current sections include:

- sales summary
- branch sales comparison
- inventory movement summary
- sync health
- stock risk summary
- low-stock list
- expiry risk list
- cloud reconciliation
- AI manager chat
- weekly AI manager reports
- weekly report delivery settings
- external AI provider policy

## Reconciliation Workflow

The reconciliation panel surfaces generated data quality issues.

Supported actions:

- acknowledge issue
- resolve issue
- admin-only repair where supported

Repairs currently support failed projection retry and product stock-total rebuild from batch snapshots.

## Audit Logs

Admins can view and export audit logs from the frontend. Backend audit endpoints support filtering by tenant, branch, action, entity, user, and time range.

## Report Safety

Reports are decision-support tools. They are not dispensing authorization. AI-generated report content must be treated as manager guidance over aggregate reporting data, not clinical advice.
