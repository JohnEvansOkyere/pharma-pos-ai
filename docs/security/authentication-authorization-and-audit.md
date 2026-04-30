# Authentication, Authorization, And Audit

## Authentication

The backend uses JWT bearer authentication.

Flow:

1. User submits username/password to `/auth/login`.
2. Backend validates credentials.
3. Backend returns access token.
4. Frontend stores token in local storage.
5. API client sends `Authorization: Bearer <token>`.
6. Backend resolves the current active user from the token.

## Authorization

Backend authorization uses:

- role checks
- granular permission checks
- organization and branch scope checks

Important backend dependency helpers:

- `require_admin`
- `require_manager`
- `require_permission`
- `require_view_reports`
- `require_adjust_stock`
- `require_perform_stock_take`
- `require_trigger_backup`
- `require_organization_access`

## Audit Logging

`activity_logs` records important actions with:

- organization id
- branch id
- source device id
- user id
- action
- entity type
- entity id
- description
- extra JSON data
- IP address
- created timestamp
- hash version
- previous hash
- current hash

Implemented audit-sensitive actions include sale reversal, stock adjustment, stock take, AI workflow actions, cloud reconciliation acknowledgement/resolution/repair, and operational admin review/export paths.

## Tamper-Evident Chain

New audit rows written through `AuditService.log` are sealed with a SHA-256 hash chain per organization.

The canonical hash payload includes:

- hash version
- row id
- organization, branch, and source device
- user id
- action
- entity type and entity id
- description
- extra data
- IP address
- created timestamp
- previous hash

The first sealed row in an organization chain uses the genesis hash `0000000000000000000000000000000000000000000000000000000000000000`.

The backend exposes `/system/audit-integrity` for admin verification. It reports:

- whether the chain is valid
- sealed row count
- unsealed row count
- unsealed rows inserted after a chain started
- invalid hash count
- first invalid log id
- first issues found

Legacy rows that existed before this feature are reported as unsealed. Unsealed rows after a chain has started are treated as integrity issues.

## Admin Audit Viewer

Admins can view and export audit logs through `/system/audit-logs` and `/system/audit-logs/export`. The Audit Logs page also shows the current audit integrity status and can trigger a chain verification check.

Tenant-scoped filtering is supported.

## Current Audit Limitations

Tamper-evident audit chaining detects changes after rows are sealed, but it does not stop a database superuser from editing rows. It makes tampering visible during verification.

Remaining improvements:

- add a dedicated incident workflow for broken chains
- add optional scheduled integrity verification
- add off-database hash anchoring for stronger protection
