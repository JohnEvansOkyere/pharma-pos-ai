# Weekly Report Operations

## Purpose

Weekly AI manager reports help managers prepare for the coming week. They combine performance review with forward-looking operational priorities.

## Period Design

Each report has two time windows:

- performance period: the just-ended week
- action period: the coming week

This gives the manager both what happened and what needs attention next.

## Generation

`AIWeeklyReportService`:

- collects sales performance
- collects branch sales comparison
- collects inventory movement
- collects stock risks
- collects sync health
- collects cloud reconciliation status
- builds structured sections
- writes a persisted report
- uses deterministic summary plus optional external provider
- enforces idempotency per organization/scope/action week

## Scheduling

The scheduler can generate reports when:

- `AI_WEEKLY_REPORTS_ENABLED=true`
- report day/hour/minute are configured

Default intended schedule:

- Sunday 7:00 PM

## Delivery

Delivery can be enabled separately.

Channels:

- email via SMTP
- Telegram via bot API

Delivery settings are tenant-scoped and can be organization-level or branch-level.

Delivery attempts are stored in `ai_weekly_report_deliveries`, with retry metadata.

## Review

Reports support manager review metadata:

- reviewed by user
- reviewed at
- review notes

Review is important because AI output is advisory and should be operationally accepted by a human manager.
