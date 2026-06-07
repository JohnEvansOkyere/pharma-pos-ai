# Global Identifiers And Event Identity

## Purpose

Each pharmacy organization has its own operational database. Integer primary
keys remain useful inside one database, but they are not globally unique and
must not identify tenant data across the central sync boundary.

The control plane therefore allocates stable external identifiers:

| Scope | External identifier | Local database key |
| --- | --- | --- |
| Pharmacy organization | `organization_uid` | `organizations.id` |
| Branch | `branch_uid` | `branches.id` |
| Deployment | `deployment_uid` | none; stored on each registered device |
| Device | `device_uid` | `devices.id` |
| Event | `event_id` | `sync_events.id` / `ingested_sync_events.id` |
| Business aggregate | `aggregate_uid` | type-specific local integer |

Local integer keys never become globally unique merely because they are sent
to the central service.

## Allocation And Provisioning

Organization, branch, deployment, and device identifiers are created by the
central control plane. The device provisioning response and
`provision_client.py` output include:

- `CLOUD_SYNC_ORGANIZATION_UID`
- `CLOUD_SYNC_BRANCH_UID`
- `CLOUD_SYNC_DEPLOYMENT_UID`
- `CLOUD_SYNC_DEVICE_UID`

The tenant provisioning workflow must seed the operational database with those
same organization and branch UUIDs. It must not independently create a second
identity for the same pharmacy. Completing that database creation and seeding
workflow is tracked separately under Phase 10.2 tenant provisioning.

Existing rows are backfilled by migration with deterministic UUIDv5 values so
an upgrade is repeatable. On PostgreSQL, the migration enables the standard
`uuid-ossp` extension and performs set-based updates for organizations,
branches, devices, and ingested events. It does not issue one update per event.
New control-plane records use UUIDv4 values.

## Event Envelope

Every new upload includes the complete global identity envelope:

- organization UUID
- branch UUID
- deployment UUID
- device UID
- event UUID
- aggregate UUID when the event refers to a persisted business row

The central ingestion service authenticates `device_uid` and its per-device
token, then validates the submitted UUID envelope against the registered
device. A partial UUID envelope is rejected.

The submitted numeric `organization_id` and `branch_id` remain temporarily for
legacy clients. When a complete UUID envelope is present, ingestion stamps the
central event with the organization and branch IDs from the registered device,
not the submitted local integers. Legacy uploads without UUIDs must still match
the registered numeric scope.

## Aggregate Identity

`aggregate_id` is a local integer such as sale `42` or product `42`.
`aggregate_uid` is deterministic UUIDv5:

```text
uuid5(deployment_uid, "<aggregate_type>:<aggregate_id>")
```

The result is stable for retries from one deployment and different for the
same local integer in another deployment. Events without a persisted aggregate
ID, such as a system heartbeat, have no aggregate UUID.

## Replay And Collision Rules

- the same `event_id` and payload hash is an idempotent duplicate
- the same `event_id` with a different payload hash is rejected
- an `event_id` already owned by another device or deployment is rejected
- one device sequence number cannot identify two events
- a submitted aggregate UUID must match its deployment, aggregate type, and
  local aggregate ID

These checks prevent separate operational databases from colliding in the
central reporting database while preserving local integer primary keys.
