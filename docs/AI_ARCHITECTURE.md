# AI Architecture — Pharma POS

> This document describes the complete AI layer: what it does, how it is built, what data it reads, and how it delivers output. It is intended for developers and technical owners who need to understand, extend, or audit the AI components.

---

## 1. Design Philosophy

The AI layer is built on three constraints that govern every design decision:

1. **Read-only.** The AI cannot mutate stock, sales, users, or any operational record. It answers questions and pushes alerts; it never acts on the pharmacy system.
2. **Cloud-projection data only.** All AI reads come from pre-projected cloud read-model tables (`cloud_sale_facts`, `cloud_product_snapshots`, `cloud_batch_snapshots`, `cloud_inventory_movement_facts`, `ingested_sync_events`). Raw local POS tables are never touched by the AI.
3. **Deterministic fallback always exists.** Every feature that optionally uses an external LLM has a functional deterministic code path. If no LLM API key is configured, or the external provider fails, the system returns a backend-generated answer and exposes `fallback_used` to callers.

---

## 2. High-Level Component Map

```
┌────────────────────────────────────────────────────────────────┐
│ Delivery Layer (output)                                         │
│                                                                  │
│  Telegram Bot ──► TelegramService.send_message()               │
│  Email (SMTP) ──► AIReportDeliveryService._send_email()        │
│  HTTP API    ──► /api/ai-manager/* and /api/telegram/webhook     │
└────────────────────────────────────────────────────────────────┘
          ▲                  ▲                    ▲
          │                  │                    │
┌─────────┴──────┐  ┌────────┴───────┐  ┌───────┴──────────────┐
│ TelegramAlert  │  │ AIWeeklyReport │  │ AIManagerService      │
│ Service        │  │ Service        │  │ (on-demand chat)      │
│                │  │                │  │                        │
│ push alerts    │  │ generate +     │  │ answer() method        │
│ daily briefing │  │ persist weekly │  │ tool dispatcher        │
│ route messages │  │ report         │  │ LLM orchestration      │
└────────┬───────┘  └────────┬───────┘  └───────┬──────────────┘
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                    ┌────────┴─────────────────────────────────┐
                    │ Analyzer Services (shared, stateless)     │
                    │                                           │
                    │  AIBriefingService          (findings)    │
                    │  CloudStockVelocityService  (velocity)    │
                    │  CloudDeadStockService      (dead stock)  │
                    │  CloudSalesTrendService     (trends)      │
                    │  CloudReconciliationService (data quality)│
                    └────────┬──────────────────────────────────┘
                             │
                    ┌────────┴──────────────────────────────────┐
                    │ Cloud Read Models (PostgreSQL, read-only)  │
                    │                                           │
                    │  cloud_sale_facts                         │
                    │  cloud_inventory_movement_facts           │
                    │  cloud_product_snapshots                  │
                    │  cloud_batch_snapshots                    │
                    │  ingested_sync_events                     │
                    └────────────────────────────────────────────┘
```

---

## 3. Data Sources

The AI never reads from live POS tables. It reads exclusively from the cloud projection layer:

| Table | What it contains | Used for |
|-------|-----------------|----------|
| `cloud_sale_facts` | One row per synced sale, with revenue and item count | Sales summaries, branch comparisons, trend detection |
| `cloud_inventory_movement_facts` | One row per stock movement (sale, receipt, adjustment) with `quantity_delta` | Inventory movement, product-level sales ranking, velocity |
| `cloud_product_snapshots` | Latest known product state (stock level, thresholds, SKU) | Stock risk, out-of-stock, low-stock detection |
| `cloud_batch_snapshots` | Latest known batch state (quantity, expiry date, quarantine flag) | Expiry risk, near-expiry alerting |
| `ingested_sync_events` | All events received from local POS devices, with projection status | Sync health, data staleness detection |

Data arrives in these tables via the cloud sync pipeline: local POS devices upload sync events → `ingested_sync_events` → `CloudProjectionService` projects them into the read models above.

Reconciliation evidence is computed by `CloudReconciliationService` from snapshots, movement facts, and acknowledgement state. `cloud_reconciliation_checks` is used as an AI source label, not as a standalone fact table.

---

## 4. Analyzer Services

These are stateless services that run deterministic queries and return structured data. They are called by every AI feature.

### AIBriefingService (`ai_briefing_service.py`)

The central finding generator. Produces a ranked list of findings from six detection categories:

| Category | Severity | Finding types |
|----------|----------|---------------|
| Stock velocity | critical / high / medium | `stock_out`, `critical_velocity`, `urgent_velocity` |
| Expiry | critical / medium | `expired_batch`, `near_expiry` |
| Dead stock | medium | `dead_stock`, `slow_mover` |
| Revenue drops | high / medium | `revenue_drop`, `revenue_decline` |
| Sync health | high / medium | `sync_failure`, `stale_sync`, `no_sync` |
| Reconciliation | critical / high | `reconciliation` |

Findings are sorted by severity rank, then by `affected_count` descending. The caller controls `max_findings`. A `data_trust_status` of `ok`, `degraded`, or `unsafe` is also returned based on sync and reconciliation health.

### CloudStockVelocityService

Ranks products by daily sales rate (units/day) derived from movement facts. Computes `days_of_stock_remaining = current_stock / daily_rate`. Status buckets: `out_of_stock`, `critical` (≤3 days), `urgent` (≤7 days), `low` (≤14 days), `stable`.

### CloudDeadStockService

Identifies products with zero or near-zero sales over the period. `dead_stock` = zero sales. `slow_mover` = < 0.3 units/day average.

### CloudSalesTrendService

Compares current period revenue to an equivalent prior period per branch. Flags `severe_drop` (>50% fall), `drop` (>20% fall), `no_sales_current` (zero sales this period with prior activity), and `growth`.

### CloudReconciliationService

Cross-checks product snapshot totals against movement fact aggregates. Flags mismatches as critical/high/medium severity issues.

---

## 5. AIManagerService — On-Demand Chat

**File:** `backend/app/services/ai_manager_service.py`

This is the core Q&A engine. The `answer()` method is the single entry point for on-demand AI chat across the system. It is called from the HTTP chat endpoint and from Telegram message routing. Weekly reports use the same analyzer/data services, but are generated by `AIWeeklyReportService`.

### Flow

```
answer(db, message, organization_id, branch_id, period_days, current_user)
    │
    ├── _is_disallowed_request() → return REFUSAL_MESSAGE if blocked
    │
    ├── _reporting_window() → parse "today" / "yesterday" / default from message
    │
    ├── Resolve effective scope:
    │     user-pinned branch wins over requested branch_id
    │
    ├── Fetch approved evidence pack:
    │     _sales_summary, _branch_sales, _product_sales,
    │     _inventory_summary, _sync_health, _stock_risk_summary,
    │     CloudStockVelocityService, CloudDeadStockService,
    │     CloudSalesTrendService, CloudReconciliationService
    │
    ├── _build_trust_warning() → prepend data quality caveat if degraded
    │
    ├── _compose_answer() → deterministic fallback answer
    │
    ├── AIProviderPolicyService.resolve_provider() → pick LLM provider
    │
    ├── if external LLM configured:
    │       AIManagerLLMProvider.generate_answer_with_tools()
    │           → tool-use loop (up to 5 iterations)
    │           → LLM calls registered tools, gets real data back
    │           → returns natural language answer + tool_trace
    │   else:
    │       use deterministic answer
    │
    ├── _verify_answer_numbers()
    │       → compare final numeric claims against tool_results + tool_trace
    │       → unsupported number triggers deterministic fallback
    │
    └── Return answer, data_scope, tool_results, tool_trace, verification,
        safety_notes, provider/model, fallback_used, refused
```

### Response Contract

The chat response intentionally includes both user-facing text and audit/debug context:

| Field | Meaning |
|-------|---------|
| `answer` | Text shown to the manager/CEO |
| `data_scope` | Organization, branch, period, and source tables used |
| `tool_results` | Backend evidence pack fetched by approved service functions |
| `tool_trace` | External LLM tool calls with tool name, arguments, and returned result |
| `verification` | Numeric-claim verification status and unsupported numbers, if any |
| `fallback_used` | Whether the deterministic answer replaced an external answer |
| `refused` | Whether the request was blocked by safety policy |

### Deterministic Mode

When no LLM is configured, the answer is composed locally by matching broad intent keywords in the user's message. This is an offline-safe fallback, not the primary intelligence layer:

| Keywords | Response covers |
|----------|----------------|
| drug / product + sell / sold | Top products by units sold |
| sale / revenue / income / total | Sales summary (revenue, count, items) |
| risk / expiry / expired / low stock | Stock risk summary |
| velocity / reorder / days remaining | Velocity ranking with days of stock |
| dead stock / slow mover | Dead stock and slow movers |
| reconcile / data quality / trust | Reconciliation status |
| sync / cloud / upload | Sync health |
| trend / compare / drop / anomaly | Revenue comparison across periods |
| branch / best / perform | Top branch by revenue |
| stock / inventory / movement | Inventory movement totals |
| (default) | Sales + inventory + sync summary |

The deterministic path is deliberately conservative. It should not be marketed as fully conversational AI; it exists so the product can still answer common reporting questions when external AI is disabled or unavailable.

### Tool-Use Mode

When external AI is configured and tenant policy allows it, the LLM receives a CEO-oriented system prompt and the registered tool schemas. It decides which tools are relevant, receives only the approved tool outputs, and writes the final explanation. The backend still owns scope, business rules, and numeric verification.

The LLM cannot:
- query arbitrary SQL
- mutate POS records
- bypass branch/user scope
- invent accepted figures without passing `_verify_answer_numbers()`

Important limitation: numeric verification checks that stated figures exist in approved evidence, but it is not a full semantic proof that every sentence is strategically correct. High-stakes recommendations still need regression/evaluation tests against realistic pharmacy datasets.

### Safety Refusal

The following request types are refused unconditionally, regardless of LLM configuration:

- Clinical advice, diagnosis, dosage
- Prescription overrides, controlled-drug guidance
- Dispensing approval
- Stock mutations (change stock, adjust stock, delete/void/refund sale)

The refusal message is returned as the answer with `refused: true` in the response.

### Branch Scoping

Users pinned to a branch (`current_user.branch_id != None`) always see only their branch. Org-level users can pass `branch_id` to scope to a single branch or `null` for all branches.

---

## 6. LLM Provider Layer

**File:** `backend/app/services/ai_llm_provider.py`

### Supported Providers

| Provider | API | Default Model |
|----------|-----|---------------|
| `openai` | OpenAI Chat Completions | `gpt-4o-mini` |
| `claude` | Anthropic Messages | `claude-3-5-haiku-latest` |
| `groq` | Groq OpenAI-compatible | `llama-3.3-70b-versatile` |
| `deterministic` | No external call | n/a |

### Tool-Use Loop

Both the OpenAI/Groq path (`_openai_tool_loop`) and the Anthropic path (`_claude_tool_loop`) run the same logic:

1. Send system prompt + user message + 10 registered tool schemas to the LLM.
2. If the LLM responds with a tool call, dispatch to `_make_tool_dispatcher()`.
3. The dispatcher returns pre-fetched data for the default period, or executes fresh queries for `today`/`yesterday`.
4. Send the tool result back to the LLM.
5. Repeat up to `MAX_TOOL_ITERATIONS = 5` times.
6. If the LLM returns a text answer, return it. If the loop exhausts, fall back to the deterministic answer.

### Registered Tool Schemas (10 tools)

| Tool | Data returned |
|------|--------------|
| `get_sales_summary` | Revenue, transaction count, item count |
| `get_branch_sales` | Per-branch breakdown ranked by revenue |
| `get_product_sales` | Top products by units sold |
| `get_inventory_summary` | Movement aggregates (received vs dispensed) |
| `get_sync_health` | Event counts, projection failures, duplicates, timestamps |
| `get_stock_risk` | Out-of-stock, low-stock, expired, near-expiry counts and lists |
| `get_stock_velocity` | Products ranked by daily sell rate with days remaining |
| `get_dead_stock` | Products with zero or very low sales |
| `get_revenue_comparison` | Current vs prior period per branch |
| `get_reconciliation` | Data consistency issues between snapshots and facts |

### Provider Policy

`AIProviderPolicyService.resolve_provider()` determines which provider to use at call time. It checks which API keys are present in the environment and returns the first available. Tenant-level policy (`AIExternalProviderSetting`) can restrict or prefer specific providers — an admin must explicitly consent before external AI processing is enabled for a tenant.

### Traceability and Verification

External provider responses return a `tool_trace` list. Each entry contains:
- `tool`: the registered tool name
- `arguments`: the arguments selected by the model
- `result`: the backend result returned to the model

After the model writes the final answer, `AIManagerService._verify_answer_numbers()` compares numeric claims in the final answer against the approved evidence in `tool_results` and `tool_trace`. If the answer contains an unsupported number, the response falls back to the deterministic answer and sets:

```json
{
  "verification": {
    "verified": false,
    "unsupported_numbers": ["..."],
    "fallback_reason": "unsupported_numeric_claims"
  },
  "fallback_used": true
}
```

This protects against the most dangerous LLM failure mode for this product: confident but unsupported business figures.

---

## 7. AIWeeklyReportService — Scheduled Reports

**File:** `backend/app/services/ai_weekly_report_service.py`

Generates and persists a structured weekly manager report for each active organization. Called by the scheduler on a configurable day/time, or manually via the API.

### Report Structure

Each report covers two windows:
- **Performance window:** 7 days ending at generation time (what happened last week)
- **Action window:** next Monday–Sunday (priorities for the coming week)

The report has four sections stored as JSON:

| Section | Contents |
|---------|----------|
| `performance_review` | Revenue, transactions, items, inventory movement |
| `branch_performance` | Per-branch sales ranked by revenue, top branch |
| `coming_week_action_plan` | Priority action items, low-stock and expiry batch lists |
| `sync_and_data_quality` | Sync health metrics, reconciliation issue summary |

### Idempotency

Reports are unique on `(organization_id, report_scope_key, action_period_start, action_period_end)`. If a report for the same org and action window already exists, `generate_for_organization()` returns the existing one without re-generating.

### Executive Summary

If an LLM is configured, it receives the full tool results and structured sections as a prompt and writes a natural-language executive summary. If not configured (or if it fails), a deterministic template summary is used instead — which also prepends a `DATA TRUST WARNING` if sync or reconciliation issues are present.

---

## 8. AIBriefingService and AIFindingService — Workbench Findings

**Files:** `ai_briefing_service.py`, `ai_finding_service.py`

`AIBriefingService.briefing()` is the on-demand version — returns findings immediately without persisting them. This is what drives the Telegram daily briefing and proactive alert detection.

`AIFindingService.upsert_findings()` persists findings into `ai_findings` for the owner's workbench. Each finding has a `fingerprint = "{branch_id}:{type}"` that uniquely identifies it per org. Updates are in-place for `open` and `snoozed` findings; `dismissed` and `resolved` findings are never overwritten.

Finding statuses:

| Status | Meaning |
|--------|---------|
| `open` | Active, awaiting review |
| `acknowledged` | Owner has seen it |
| `snoozed` | Suppressed until `snoozed_until` datetime |
| `dismissed` | Permanently closed, not a finding |
| `resolved` | Fixed and documented |

---

## 9. Telegram Integration

### Architecture

The Telegram integration has two traffic directions:

**Outbound (push):** Server → CEO's Telegram
- Proactive anomaly alerts every 45 minutes (configurable)
- Daily morning briefing at 08:00 (configurable)
- Weekly report delivery (manual or scheduled)

**Inbound (pull):** CEO's Telegram → Server
- CEO sends a message to the bot
- Telegram calls the webhook endpoint
- Server routes the message to `AIManagerService.answer()`
- Response sent back via `TelegramService.send_message()`

### Components

**`TelegramService`** (`telegram_service.py`) — thin HTTP adapter for the Telegram Bot API:
- `send_message(chat_id, text)` — sends HTML-formatted message, truncates at 4096 chars
- `format_alert(severity, title, summary, action_hint)` — formats a severity-emoji + bold-title alert
- `format_briefing(findings, date_label, scope_label)` — formats up to 8 findings into a morning briefing

**`TelegramAlertService`** (`telegram_alert_service.py`) — orchestration layer:
- `push_alerts_all_orgs()` — for each org with `telegram_enabled=True`, runs briefing, filters for `critical`/`high` findings, deduplicates by cooldown, sends
- `send_daily_briefing_all_orgs()` — sends full briefing including `medium` findings
- `route_ceo_message(chat_id, text)` — resolves chat_id → org_id via delivery settings, calls `AIManagerService.answer()`

**`/api/telegram/webhook`** (`telegram.py`) — public endpoint, no JWT auth:
- Verifies `X-Telegram-Bot-Api-Secret-Token` header if `TELEGRAM_WEBHOOK_SECRET` is set
- Returns 200 immediately (Telegram requires this within 5 seconds)
- Processes the message in a `BackgroundTask` with its own database session

### Alert Deduplication

`TelegramAlertLog` (`ai_telegram_alert_logs` table) stores one row per `(organization_id, alert_key)` where `alert_key = "{finding_type}:{branch_id}"`. Before sending any alert, the service checks `last_sent_at`. If less than `TELEGRAM_ALERT_COOLDOWN_HOURS` (default: 4) have passed, the alert is suppressed. Only `critical` and `high` severity findings generate push alerts; `medium` findings appear only in the daily briefing.

### Chat ID → Org Mapping

There is no separate mapping table. The system looks up all active `AIWeeklyReportDeliverySetting` rows and checks whether `chat_id` appears in the `telegram_chat_ids` JSON array. This is adequate for a small number of orgs and avoids schema complexity.

---

## 10. Delivery — Email and Telegram Reports

**File:** `backend/app/services/ai_report_delivery_service.py`

`AIReportDeliveryService.deliver()` sends a saved `AIWeeklyManagerReport` through configured channels. For each recipient:
1. A `AIWeeklyReportDelivery` row is created (channel, recipient, status=`pending`).
2. The report is sent via email (SMTP) or Telegram.
3. The row is updated to `sent` or `failed`.
4. Failed rows with `retryable=True` get a `next_retry_at` timestamp.

A scheduler job (`retry_weekly_ai_report_deliveries`) retries failed deliveries on a configurable interval.

---

## 11. Background Scheduler Jobs

All AI-related jobs are registered in `SchedulerService.start()` in `scheduler.py`. Each job opens its own `SessionLocal()` session — they do not share the request session.

| Job ID | Trigger | Enabled by |
|--------|---------|-----------|
| `push_telegram_alerts` | Interval, every 45 min | `TELEGRAM_ALERTS_ENABLED=True` + `TELEGRAM_BOT_TOKEN` |
| `send_daily_briefing` | Cron, `AI_DAILY_BRIEFING_HOUR:00` | `AI_DAILY_BRIEFING_ENABLED=True` |
| `generate_weekly_ai_reports` | Cron, configured day/hour/minute | `AI_WEEKLY_REPORTS_ENABLED=True` |
| `retry_weekly_ai_report_deliveries` | Interval, configurable | `AI_WEEKLY_REPORT_DELIVERY_RETRY_ENABLED=True` |

All jobs use lazy imports inside the static method body (`from app.services... import ...`) to avoid circular imports at module load time.

---

## 12. API Endpoints

Most AI management endpoints are under the `/api/ai-manager` prefix. The Telegram webhook is under `/api/telegram` because it is called directly by Telegram, not by an authenticated dashboard session.

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| `POST` | `/chat` | manager+ | Ask a question, get an answer, persist to session |
| `GET` | `/sessions` | manager+ | List chat sessions |
| `GET` | `/sessions/{id}/messages` | manager+ | Load messages from a session |
| `GET` | `/briefing` | view_reports+ | On-demand ranked findings |
| `GET` | `/findings` | view_reports+ | List persisted findings |
| `PATCH` | `/findings/{id}` | view_reports+ | Update finding status |
| `GET` | `/external-provider-settings` | admin | Read LLM provider policy |
| `PUT` | `/external-provider-settings` | admin | Update LLM provider policy |
| `POST` | `/weekly-reports/generate` | view_reports+ | Generate and persist a report |
| `GET` | `/weekly-reports` | view_reports+ | List saved reports |
| `GET` | `/weekly-reports/{id}` | view_reports+ | Fetch a saved report |
| `POST` | `/weekly-reports/{id}/review` | view_reports+ | Mark a report reviewed |
| `POST` | `/weekly-reports/{id}/deliver` | view_reports+ | Deliver a report by email/Telegram |
| `GET` | `/weekly-reports/{id}/deliveries` | view_reports+ | List delivery attempts |
| `GET` | `/weekly-report-delivery-settings` | admin | Read delivery recipients |
| `PUT` | `/weekly-report-delivery-settings` | admin | Update delivery recipients |
| `POST` | `/api/telegram/webhook` | (public, secret-token gated) | Receive CEO messages from Telegram |

---

## 13. Database Tables

| Table | Purpose |
|-------|---------|
| `ai_weekly_manager_reports` | Persisted weekly reports (one per org per action window) |
| `ai_weekly_report_deliveries` | Audited delivery attempts per report |
| `ai_weekly_report_delivery_settings` | Email/Telegram recipients per org scope |
| `ai_external_provider_settings` | Tenant consent and LLM provider policy |
| `ai_findings` | Persisted CEO workbench findings with lifecycle status |
| `ai_chat_sessions` | Persistent chat sessions per user |
| `ai_chat_messages` | Messages within sessions (user + assistant turns) |
| `ai_telegram_alert_logs` | Alert deduplication log (last sent time per org+key) |

---

## 14. Environment Variables

### LLM Providers

| Variable | Purpose |
|----------|---------|
| `AI_MANAGER_PROVIDER` | `deterministic` (default), `openai`, `claude`, `groq` |
| `AI_MANAGER_MODEL` | Override default model for configured provider |
| `AI_MANAGER_MAX_TOKENS` | Max tokens per LLM response |
| `AI_MANAGER_TIMEOUT_SECONDS` | HTTP timeout for external LLM calls |
| `OPENAI_API_KEY` | Required if provider is `openai` |
| `ANTHROPIC_API_KEY` | Required if provider is `claude` |
| `GROQ_API_KEY` | Required if provider is `groq` |

### Telegram

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | — | Bot token from BotFather. Required for all Telegram features. |
| `TELEGRAM_WEBHOOK_SECRET` | — | Shared secret to verify Telegram webhook calls. Optional but recommended. |
| `TELEGRAM_ALERTS_ENABLED` | `False` | Enable the 45-minute push alert job. |
| `TELEGRAM_ALERT_COOLDOWN_HOURS` | `4` | Minimum hours between repeated alerts for the same issue. |
| `TELEGRAM_ALERT_INTERVAL_MINUTES` | `45` | How often the alert scanner runs. |
| `AI_DAILY_BRIEFING_ENABLED` | `False` | Enable the daily morning Telegram briefing. |
| `AI_DAILY_BRIEFING_HOUR` | `8` | Hour (0–23, server timezone) to send the briefing. |
| `AI_DAILY_BRIEFING_PERIOD_DAYS` | `7` | Days of data the daily briefing covers. |

### Weekly Reports

| Variable | Default | Purpose |
|----------|---------|---------|
| `AI_WEEKLY_REPORTS_ENABLED` | `False` | Enable the weekly report generation job. |
| `AI_WEEKLY_REPORT_DELIVERY_ENABLED` | `False` | Automatically deliver after generating. |
| `AI_WEEKLY_REPORT_EMAIL_ENABLED` | `False` | Include email in auto-delivery. |
| `AI_WEEKLY_REPORT_DAY` | `sun` | Day of week to generate (e.g. `sun`). |
| `AI_WEEKLY_REPORT_HOUR` | `19` | Hour to generate. |
| `AI_WEEKLY_REPORT_MINUTE` | `0` | Minute to generate. |
| `ENABLE_BACKGROUND_SCHEDULER` | `True` | Master switch for all background jobs. |

---

## 15. Key Invariants

- The AI layer never calls `db.commit()` inside `AIManagerService.answer()` — it is read-only. Commits happen only in delivery, finding persistence, and alert log upserts.
- Telegram background tasks open their own `SessionLocal()` because the request session closes before the background task runs.
- The deterministic answer is always computed before attempting an LLM call. If the LLM fails for any reason, `fallback_used=True` is set and the deterministic answer is returned. The caller always gets a response.
- External AI processing requires explicit admin consent via `AIExternalProviderSetting`. The system logs the consenting user and timestamp in the audit trail.
- Prompts sent to external LLMs contain only aggregate reporting figures (counts, totals, dates). No patient names, prescription details, or individual transaction identifiers are included.
- External LLM answers expose tool-call traceability via `tool_trace`.
- Numeric claims in external LLM answers must be present in approved evidence, or the response falls back to the deterministic answer.

---

## 16. Current Gaps Before Client AI Rollout

The current AI layer is materially stronger than the original keyword-matched prototype, but it is not yet a finished client-grade AI product. Remaining work:

| Gap | Why it matters |
|-----|----------------|
| Live-provider evaluation suite | Unit tests mock provider behavior; the system still needs repeatable OpenAI/Claude/Groq evals on realistic pharmacy questions. |
| Broader tool coverage | Current tools cover core sales, stock, velocity, dead stock, trends, sync, and reconciliation. CEO questions about profit margin, stock value, supplier performance, cashier performance, refunds, voids, payment mix, and purchasing still need tools. |
| Stronger final-answer validation | Numeric verification catches unsupported figures, but it does not yet validate all comparative claims, causal claims, or action recommendations. |
| Branch/product natural-language resolution | Tools mainly accept scope from request context and simple periods. Questions like "compare East Legon with Osu today" need robust name/entity resolution. |
| Data trust badges per metric | The system returns trust warnings globally, but individual figures do not yet carry freshness/reconciliation confidence. |
| Operating-hours-aware alerts | "No sales" or branch silence should be judged against configured trading hours, holidays, and expected branch activity. |
| Operational runbook | Client rollout still needs provider-key rotation, Telegram webhook setup, alert test procedure, and fallback/offline behavior documented for installers. |
