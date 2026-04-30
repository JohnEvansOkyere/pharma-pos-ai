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

Implemented audit-sensitive actions include sale reversal, stock adjustment, stock take, AI workflow actions, cloud reconciliation acknowledgement/resolution/repair, and operational admin review/export paths.

## Admin Audit Viewer

Admins can view and export audit logs through `/system/audit-logs` and `/system/audit-logs/export`.

Tenant-scoped filtering is supported.

## Current Audit Limitation

Audit logs are not yet tamper-evident. A database operator with direct write access could alter rows without immediate detection.

Recommended next improvement:

- add hash chaining to critical audit events
- store previous hash and current hash
- include canonicalized event fields in the hash
- provide verifier endpoint and dashboard signal
- document incident handling when a chain breaks
