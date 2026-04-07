# AGENTS.md

## Purpose

Working rules for future agent sessions in this repository.

Primary objective:
- turn this project from a prototype into a deployable offline pharmacy product

Current phase:
- audit follow-up and production hardening

## Product Context

- Project type: pharmaceutical POS system
- Deployment target: on-site pharmacy installations
- Primary requirement: reliable offline/local operation
- Risk posture: correctness and recoverability matter more than feature count

## Operating Priorities

1. Protect data integrity.
2. Protect dispensing and stock workflows.
3. Prefer simple, maintainable local deployment patterns.
4. Do not market or describe capabilities that are not actually implemented.
5. Treat security, auditability, backups, and operator workflow as first-class features.

## Engineering Rules

- Do not introduce placeholder claims like "offline-ready", "AI-powered", or "production-grade" unless the implementation supports them.
- Prefer local-first designs that work on low-spec pharmacy machines.
- Keep dependencies conservative.
- Favor deterministic behavior over cleverness.
- Preserve existing user changes unless explicitly asked to replace them.

## Backend Expectations

- Public self-registration must not exist in release builds.
- User provisioning must be admin-controlled.
- Sales must be transaction-safe.
- Inventory must be batch-aware.
- FEFO is the default for dispensed stock unless an audited override exists.
- Prescription-only and controlled-drug rules must be enforced server-side.
- Local database mode must be explicitly hardened and tested.
- Every critical write path should eventually have audit logging.

## Frontend Expectations

- The POS route is the most important workflow.
- Startup should be fast on pharmacy workstations.
- Do not block the whole UI on non-critical dashboard/reporting requests.
- Offline behavior must be explicit:
  - either the app requires a local backend to be running at all times
  - or true offline-first sync/storage must be implemented
- Avoid mock business metrics in release-facing screens.

## Testing Expectations

- Any fix touching auth, sales, inventory, pricing, or user roles should come with test coverage where practical.
- Prefer adding regression tests before broad refactors in critical flows.
- Before closing work, run the smallest meaningful verification available.

## Documentation Rules

- Keep `README.md` as the top-level entry point.
- Keep project guidance and reports under `docs/`.
- Put audits under `docs/audits/`.
- Put older root-level project notes under `docs/root-docs/`.

## Release Guidance

Before client rollout, agents should prioritize:

1. security hardening
2. stock and dispensing correctness
3. backup and restore workflows
4. installability on offline/local pharmacy setups
5. operational diagnostics and support tooling

## Avoid

- shipping demo credentials
- shipping committed database files or local env files
- depending on mock analytics for product decisions
- adding large new feature surfaces before core flows are safe

