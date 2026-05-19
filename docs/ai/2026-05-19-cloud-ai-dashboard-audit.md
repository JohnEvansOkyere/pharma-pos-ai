# Cloud AI Dashboard Audit - Claude Report Validation

Date: 2026-05-19
Auditor: Dex
Scope: Validate the supplied Claude report against the current codebase and reconcile it with the prior architecture audit.

## Executive Verdict

Claude's report is directionally correct: the cloud sync/reporting plumbing is valuable, but the AI layer is still a thin summarizer rather than a CEO-grade advisor. The strongest alignment is on these points:

- The cloud dashboard has real infrastructure: projected sales, product snapshots, batch snapshots, sync health, stock risk, expiry risk, reconciliation, weekly reports, and delivery settings.
- The AI chat is not yet a real intelligence layer. The deterministic answer path is a keyword router over a handful of aggregate queries.
- The system needs proactive, ranked findings with evidence, data freshness, confidence, and follow-up workflow.
- Cloud AI currently lacks trends, stock velocity, days-of-stock remaining, conversation memory, and durable decisions.

Claude's report needs correction or nuance in three places:

- Weekly reports are not strictly manual-only. A scheduler exists behind `AI_WEEKLY_REPORTS_ENABLED`; however, the dashboard still treats generation as a manual action and there is no unread owner notification workflow.
- Branch names exist in the data model, but the cloud dashboard often displays `Branch {id}`. This is a UI/query usage problem, not a missing model field.
- "Inventory movements are all synced and queryable" is too broad. Some stock events project movement facts, but `sale_created` currently adjusts product/batch snapshots without creating `CloudInventoryMovementFact` rows for sold items.

## Confirmed Working Capabilities

### Cloud Reporting Infrastructure

Confirmed. The cloud projection models exist for:

- `CloudSaleFact`
- `CloudInventoryMovementFact`
- `CloudProductSnapshot`
- `CloudBatchSnapshot`
- `CloudReconciliationAcknowledgement`

Evidence:

- `backend/app/models/cloud_projection.py`
- `backend/app/services/cloud_projection_service.py`
- `backend/app/api/endpoints/cloud_reports.py`

The cloud dashboard fetches real cloud endpoints for sales, branch sales, inventory movement summaries, sync health, stock risk, low stock, expiry risk, reconciliation, and AI weekly reports.

Evidence:

- `frontend/src/pages/CloudDashboardPage.tsx`
- `frontend/src/services/api.ts`

### Reconciliation Workflow

Confirmed. The reconciliation service detects projection failures, negative stock, orphan batches, product-vs-batch mismatches, and latest `stock_after` mismatches. It also supports acknowledge, resolve, retry failed projections, and controlled product stock total repair.

Evidence:

- `backend/app/services/cloud_reconciliation_service.py`
- `backend/app/api/endpoints/cloud_reports.py`

### Weekly Reports and Delivery

Confirmed. Weekly report generation and delivery are implemented:

- Reports are persisted in `AIWeeklyManagerReport`.
- Reports can be generated manually from the API/UI.
- Reports can be delivered through email or Telegram.
- Delivery retry exists.
- Scheduler can auto-generate reports when enabled.

Evidence:

- `backend/app/services/ai_weekly_report_service.py`
- `backend/app/services/ai_report_delivery_service.py`
- `backend/app/api/endpoints/ai_manager.py`
- `backend/app/services/scheduler.py`

Correction to Claude: the feature is not manual-only at the backend level. `SchedulerService` registers `generate_weekly_ai_reports` when `settings.AI_WEEKLY_REPORTS_ENABLED` is true, and it can call delivery when `AI_WEEKLY_REPORT_DELIVERY_ENABLED` is true. The product gap is that the dashboard does not surface this as an unread CEO briefing/notification.

## Validated Weaknesses

### 1. AI Chat Is Mostly a Keyword Router

Confirmed. The deterministic answer path in `AIManagerService._compose_answer()` checks for keywords such as:

- `risk`
- `expiry`
- `reconcile`
- `sync`
- `branch`
- `stock`
- `inventory`

Then it returns a fixed template using aggregate query results.

Evidence:

- `backend/app/services/ai_manager_service.py`

This is useful as a safe fallback, but it is not enough for CEO-grade decision support. It can summarize known counters; it does not discover, rank, persist, or track business opportunities and risks.

### 2. LLM Prompting Is Underpowered

Partially confirmed.

Claude is right that the LLM gets raw Python-style dictionaries using `f"{tool_results}"`, plus a deterministic baseline answer. That is weak for serious advisory output because the model receives unstructured aggregates instead of a clean evidence pack.

Evidence:

- `AIManagerService._provider_prompt()` in `backend/app/services/ai_manager_service.py`
- `AIWeeklyReportService._provider_prompt()` in `backend/app/services/ai_weekly_report_service.py`

Correction to Claude: there is a system instruction in `AIManagerLLMProvider._system_instructions()`. It defines the assistant as a read-only pharmacy business manager assistant. The weakness is that the system prompt is minimal and generic; it does not include Ghana/local pharmacy context, owner operating style, output schema, decision workflow, freshness rules, or confidence rules.

### 3. No Conversation History

Confirmed. `AIManagerChatRequest` carries only:

- `message`
- `organization_id`
- `branch_id`
- `period_days`

The frontend sends only the latest message. The backend does not persist or pass prior messages to the provider.

Evidence:

- `backend/app/schemas/ai_manager.py`
- `frontend/src/pages/CloudDashboardPage.tsx`
- `backend/app/api/endpoints/ai_manager.py`

Impact: follow-up questions such as "what about branch 3?" lose context unless the user restates the full question.

### 4. No Cloud Trend or Velocity Intelligence

Confirmed. The cloud AI collects simple aggregate windows:

- sales count
- total revenue
- total items
- branch sales totals
- inventory movement totals
- stock risk counts
- sync health
- reconciliation

It does not compute:

- current week vs previous week
- daily revenue trend
- product sales velocity
- days of stock remaining
- reorder urgency based on velocity
- margin contribution
- stockout probability
- expiry-loss prevention priority

There is velocity-style logic in `AIInsightsService`, but it reads the local database (`Product`, `Sale`, `SaleItem`) and is not used by the cloud AI.

Evidence:

- `backend/app/services/ai_manager_service.py`
- `backend/app/services/ai_weekly_report_service.py`
- `backend/app/services/ai_insights.py`

### 5. No Days-of-Stock Remaining

Confirmed. Current cloud stock risk queries compare `total_stock` to thresholds and expiry dates. They do not combine current stock with sales velocity.

Evidence:

- `backend/app/api/endpoints/cloud_reports.py`
- `backend/app/services/ai_weekly_report_service.py`

This is a high-value pharmacy-owner metric and should be prioritized.

### 6. Branch Names Are Not Used Enough

Partially confirmed. The model has `Branch.name`, `Branch.code`, phone, and address. The admin command center uses branch names in attention items. The cloud dashboard and AI often show only numeric IDs.

Evidence:

- `backend/app/models/tenancy.py`
- `frontend/src/pages/CloudDashboardPage.tsx`
- `backend/app/services/ai_manager_service.py`

Fix: cloud report endpoints and AI tool results should join branch metadata and return `branch_name`/`branch_code` beside every branch-scoped metric.

### 7. No Proactive CEO Briefing

Mostly confirmed. The vendor admin command center has an attention queue, but the cloud AI dashboard does not auto-load a personalized owner briefing with ranked recommendations. The AI waits for a question or manual weekly-report generation.

Evidence:

- `backend/app/api/endpoints/admin_tenancy.py`
- `frontend/src/pages/CloudDashboardPage.tsx`

The product should move from "ask the assistant" to "the assistant opens with today's ranked decisions."

## Additional Issues From Dex Audit

These are not emphasized in Claude's report, but they are important before trusting CEO decisions.

### A. Cloud Fact Time Semantics Need Hardening

`CloudSaleFact.created_at` uses the cloud projection row timestamp, not necessarily the original local sale time. The `sale_created` sync payload currently includes invoice, payment, totals, and items, but not a canonical `occurred_at`/sale timestamp.

Risk: daily revenue, trend comparisons, and weekly reports can be distorted if events sync late.

Fix:

- Add `occurred_at` to every `SyncEvent` payload or envelope.
- Add `occurred_at` to cloud fact tables.
- Use `occurred_at` for business windows; keep `received_at`/`projected_at` for data freshness.

### B. Sale Inventory Movement Facts Are Missing

`CloudProjectionService.project_event()` handles `SALE_CREATED` by projecting a sale fact and applying snapshot effects. It does not call `_project_inventory_event()` for each sale item, and `_movement_lines()` has no `SALE_CREATED` branch.

Risk: cloud inventory movement summaries can miss the main negative stock flow: sales dispensed.

Fix:

- For `SALE_CREATED`, create one negative `CloudInventoryMovementFact` per sold item.
- Include `stock_after` when available, or compute from snapshot effect if safe.

### C. Sale Item Payload Needs `batch_id`

The sale sync payload includes `batch_number`, not `batch_id`. Projection finds a batch by number, product, org, and branch.

Risk: batch numbers are not guaranteed globally unique over time. Batch-level AI and reconciliation are weaker without the local batch ID.

Fix:

- Add `batch_id` to sale item sync payload.
- Prefer `local_batch_id` in cloud projection.

### D. Initial Full Snapshot Sync Is Needed

If cloud sync is enabled after a pharmacy already has products, batches, and stock, the cloud may lack real product and batch snapshots until future product/batch events occur. Projection can create placeholder products and batches.

Risk: early cloud AI can advise from incomplete or placeholder catalog data.

Fix:

- Add an admin/maintenance endpoint or script to enqueue a full snapshot:
  - active products
  - active batches
  - current stock
  - thresholds/prices
  - opening reconciliation marker

## Recommended Target Architecture

Keep the current outbox -> ingestion -> projection architecture. Add an intelligence layer above the projection tables.

Recommended flow:

```text
Local POS events
  -> Sync outbox
  -> Cloud ingestion
  -> Cloud projections
  -> Deterministic analyzers
  -> AI findings and recommendations
  -> LLM narration
  -> CEO dashboard, briefing, and follow-up workflow
```

The LLM should not be responsible for calculating facts. Deterministic services should calculate facts and produce an evidence pack. The LLM should explain and prioritize.

## Required New Concepts

### AI Finding

Persistent record for something the CEO should know.

Suggested fields:

- organization_id
- branch_id
- finding_type
- severity
- title
- summary
- evidence_json
- confidence
- freshness_status
- reconciliation_status
- expected_impact_amount
- status: open, acknowledged, snoozed, dismissed, resolved
- generated_at
- due_at

### AI Recommendation

Persistent action linked to a finding.

Suggested fields:

- finding_id
- action_type
- action_text
- owner_user_id
- status
- due_at
- completed_at
- manager_notes

### AI Briefing

Daily or on-demand summary composed from open findings.

Suggested behavior:

- auto-generate when the cloud dashboard opens
- show 3-5 highest priority actions
- include evidence and confidence
- block or downgrade advice when data trust is stale/unsafe

## Build Priority

### P0 - Data Correctness Before Advice

1. Add `occurred_at` to sync/cloud facts and use it in business reporting.
2. Add `batch_id` to sale item sync payloads.
3. Project sale-created item rows into `CloudInventoryMovementFact`.
4. Add full catalog/batch/current-stock snapshot sync for existing installs.
5. Add trust gates so AI labels advice as unsafe/limited when sync or reconciliation is bad.

### P1 - CEO Briefing

1. Add `GET /ai-manager/briefing`.
2. Generate ranked findings:
   - urgent stockouts
   - low stock with days remaining
   - expiry value at risk
   - stale sync/data trust
   - branch sales drop
   - no-sales-during-hours alert
3. Put the briefing at the top of the cloud dashboard.
4. Add action buttons: acknowledge, snooze, dismiss, mark resolved.

### P2 - Intelligence Depth

1. Daily revenue time series.
2. Current week vs previous week.
3. Product velocity from projected sale item movement facts.
4. Days-of-stock remaining.
5. Margin and profit contribution.
6. Dead stock and slow movers from cloud projections.
7. Refund/void anomaly analysis.

### P3 - Conversation Quality

1. Persist chat sessions.
2. Pass the last 6 messages to the LLM.
3. Replace raw dict prompts with structured evidence packs.
4. Add strict output schema for:
   - answer
   - evidence
   - caveats
   - recommended next actions
5. Add branch/product names everywhere.

## Final Decision

Claude's report aligns with the main conclusion: the infrastructure is good, but the product needs a real intelligence layer. The most important correction is that this is not only a prompt engineering problem. Prompting helps, but the CEO-grade behavior depends on better cloud facts, deterministic analyzers, persistent findings, and action workflow.

The immediate next build should be:

1. Fix cloud fact correctness.
2. Add product velocity and days-of-stock remaining.
3. Add `/ai-manager/briefing`.
4. Put the briefing at the top of the cloud dashboard.
5. Persist findings and decisions so the system can follow up.
