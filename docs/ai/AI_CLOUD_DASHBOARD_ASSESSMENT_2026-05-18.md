# AI Cloud Dashboard Assessment — 2026-05-18

**Context:** A Codex report was submitted identifying gaps and data correctness issues in the cloud AI layer. This document independently verifies each claim against actual code, notes where the Codex report and my prior analysis agree, and flags where one or both missed something. Priority order for fixes is given at the end.

---

## 1. Verification of Codex Claims

### Claim 1 — CloudSaleFact timestamps record projection time, not sale time

**Codex:** `CloudSaleFact.created_at` is set when the cloud projection row is created, not when the sale happened. The sale sync payload does not include the sale timestamp.

**Status: CONFIRMED — critical data integrity bug.**

Evidence:
- `backend/app/models/cloud_projection.py:26` — `created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)`. This is the database server clock at insert time, which is when the Render scheduler projects the event — potentially hours or days after the sale.
- `backend/app/api/endpoints/sales.py:487–508` — The sync payload includes `sale_id`, `invoice_number`, `pricing_mode`, `payment_method`, financial totals, `user_id`, and items. There is no `occurred_at`, `sale_created_at`, or `created_at` field. The sale model does have `created_at` (line 103 of `models/sale.py`), it is simply never put into the sync payload.

**Impact:** Any time-based query against `cloud_sale_facts.created_at` (revenue trends, period comparisons, "today's sales") is actually reporting when the sync ran, not when the sale happened. A sale made Monday that syncs Wednesday will appear in Wednesday's revenue. This makes the AI's period-based analysis unreliable for business decisions.

**Fix:** Add `occurred_at` to the sale sync payload from `db_sale.created_at`. Add `occurred_at` column to `CloudSaleFact`. Use `occurred_at` in all revenue window queries. Keep `created_at` as the ingestion timestamp only.

---

### Claim 2 — SALE_CREATED does not produce CloudInventoryMovementFact rows

**Codex:** `SALE_CREATED` projects the sale and adjusts snapshots, but does not create `CloudInventoryMovementFact` rows for each sold item.

**Status: CONFIRMED — missing audit trail.**

Evidence in `backend/app/services/cloud_projection_service.py`:
- `project_event()` at line 107: when `event_type == SALE_CREATED`, it calls `_project_sale_created()` (creates the sale fact) and `_apply_sale_stock_effect()` (decrements product/batch snapshots). It does NOT call `_project_inventory_event()`.
- `_project_inventory_event()` (line 226) is only called for events in `STOCK_EVENT_TYPES` (line 115), which is `{STOCK_RECEIVED, STOCK_ADJUSTED, STOCK_TAKE_COMPLETED, SALE_REVERSED}`. `SALE_CREATED` is absent from that set.
- `_movement_lines()` (line 146) has no branch for `SALE_CREATED`.

**Impact:** The cloud inventory movement table records stock received, adjustments, stock takes, and reversals — but not normal sales. The "Net Stock Movement" metric and AI inventory summaries therefore undercount how much stock left the pharmacy. Movement analytics (velocity, days-of-stock calculations) are structurally unreliable until this is fixed.

**Fix:** In `project_event()`, after calling `_apply_sale_stock_effect()`, generate one `CloudInventoryMovementFact` row per sale item with a negative `quantity_delta`. This mirrors what the local `InventoryMovement` ledger already records.

---

### Claim 3 — Batch matching in sale projection uses batch number, not batch ID

**Codex:** The sale sync payload does not include `batch_id`. Projection reduces batch stock by matching on `batch_number`, which is fragile.

**Status: CONFIRMED — silent match failure risk.**

Evidence:
- `backend/app/api/endpoints/sales.py:498–504` — Sale items in the sync payload include `batch_number` and `expiry_date`, but no `batch_id`.
- `backend/app/services/cloud_projection_service.py:439–445` — `_apply_sale_stock_effect()` reads `batch_number = item.get("batch_number")` and calls `_find_batch_by_number()`. If no batch snapshot exists yet with that number, the stock quantity is silently not decremented at the batch level (only the product-level snapshot is updated).
- `_find_batch_by_number()` (line 507) matches on `organization_id`, `branch_id`, `local_product_id`, and `batch_number`. It does not use `batch_id`, so if a batch snapshot was created with a placeholder name before the real batch sync arrived, the lookup can fail silently.

**Impact:** Batch-level stock figures in the cloud can diverge from reality. The reconciliation service may then flag phantom discrepancies. Expiry-risk calculations that rely on batch quantities are inaccurate.

**Fix:** Add `batch_id` to each item in the SALE_CREATED sync payload (`item["batch_id"] = record["batch_id"]` in `sales.py`). Update `_apply_sale_stock_effect()` to use `_get_batch_snapshot()` by ID when `batch_id` is present, falling back to number lookup only when it is absent.

---

### Claim 4 — Products arriving in sale events before a PRODUCT_CREATED event generate placeholder snapshots

**Codex:** If cloud sync is enabled after products already exist locally, the cloud may create placeholder product snapshots ("Product 1") when a sale arrives before the product event.

**Status: CONFIRMED — causes misleading stock names in the AI dashboard.**

Evidence:
- `backend/app/services/cloud_projection_service.py:458–473` — `_get_product_snapshot()` creates a placeholder with `name=f"Product {local_product_id}"` and `sku=f"product-{local_product_id}"` when no snapshot exists. This is the correct defensive pattern for event ordering, but it means the AI dashboard can show "Product 7" with real stock figures until the PRODUCT_CREATED event arrives and overwrites the name.
- There is no mechanism to flush or trigger a full-catalog snapshot sync after initial provisioning.

**Impact:** If a pharmacy is provisioned after it already has months of products and sales, the first synced events are likely sales, not product creations. The cloud dashboard will show placeholder names for all products until staff happen to update those products locally, triggering a PRODUCT_UPDATED event.

**Fix:** Add a one-time "snapshot sync" job (or a manual trigger in the vendor admin panel) that emits PRODUCT_CREATED and PRODUCT_BATCH_CREATED events for all existing products and batches when cloud sync is first enabled. This is distinct from the ongoing outbox sync.

---

### Claim 5 — The AI is summarizing, not managing

**Codex:** AI gathers a few tool results and writes a response. It does not persist findings, rank tasks, track decisions, learn from ignored advice, or follow up.

**Status: CONFIRMED — and this is the biggest strategic gap.**

Evidence matches my prior assessment:
- `backend/app/services/ai_manager_service.py:379` — `_compose_answer()` is a 7-branch keyword if/elif. It matches terms like "risk", "sync", "branch", "inventory" and returns a pre-written string template. The LLM (if configured) receives the deterministic string plus raw Python dicts and is asked to rephrase.
- The LLM prompt (`_provider_prompt()` at line 443) has no system message, no role, no business context, no output format. It receives `"organization_id=1, branch_id=None, period_days=30"` and `{'sales_count': 47, ...}`. There is no structure guiding what a useful pharmacy manager response looks like.
- No `ai_findings`, `ai_recommendations`, or `ai_decision_log` tables exist. Nothing is persisted between sessions.
- Chat messages are not persisted (`chatMessages` is React state only). Each session starts blank.

---

## 2. What the Codex Report Identified That My Analysis Missed

| Issue | Codex Identified | My Prior Analysis | Verdict |
|---|---|---|---|
| Sale timestamp wrong (projection time ≠ sale time) | Yes | No | **Missed — real bug** |
| Missing movement facts for SALE_CREATED | Yes (exact code) | Directional only ("movement analytics are unreliable") | **Codex more precise** |
| batch_id absent from sale payload, batch matched by number | Yes | Mentioned batch data issues, not this specific gap | **Codex more precise** |
| Placeholder product problem on initial sync | Yes | Not mentioned | **Missed** |
| Architecture recommendation (findings/recommendations/decision_log tables) | Yes | Not mentioned | **Missed — valuable** |

---

## 3. What My Analysis Identified That the Codex Report Did Not Emphasize

| Issue | My Analysis | Codex |
|---|---|---|
| LLM prompt has no system context or role framing | Explicit | Implied only |
| No conversation history passed to LLM | Explicit | Not mentioned |
| Branch names are numeric IDs everywhere in the UI | Explicit | Not mentioned |
| Weekly reports require manual trigger; no auto-generation | Explicit | Not mentioned |
| Suggested prompts are too operational for CEO use | Explicit | Not mentioned |
| Days-of-stock-remaining not calculated anywhere | Explicit | Not mentioned (implied by velocity work) |

---

## 4. Where Both Agree

- The sync/projection infrastructure is architecturally correct and worth keeping.
- The AI chat is read-only and deterministic-first — good safety properties.
- Weekly report structure (tool_results collection) is solid, just not surfaced well.
- The LLM is correctly optional with deterministic fallback.
- The biggest strategic gap is proactive intelligence: the system answers questions instead of telling the CEO what to act on.

---

## 5. Priority Fix Order

### P0 — Data correctness (must fix before any AI analysis is trustworthy)

1. **Add `occurred_at` to sale sync payload** — one field (`db_sale.created_at`), one column on `CloudSaleFact`, update all window queries to use it.
2. **Create movement facts for SALE_CREATED** — add per-item `CloudInventoryMovementFact` rows in `_apply_sale_stock_effect()`.
3. **Add `batch_id` to sale item sync payload** — use it in `_apply_sale_stock_effect()` instead of name lookup.
4. **Add initial snapshot sync job** — one-time catalog flush for pharmacies provisioning after existing data.

### P1 — AI trust gates

5. Add a trust check before the AI gives strong business advice: if `sync_health.projection_failed_count > 0` or `last_received_at` is more than 24 hours ago or reconciliation has critical issues, the AI must qualify its answers with the trust state.

### P2 — Intelligence layer

6. Add deterministic analyzers: days-of-stock-remaining (current stock ÷ daily velocity from movement facts), week-over-week revenue comparison, dead stock detection from cloud data, branch anomaly detection.
7. Add `ai_findings` table: persisted risk/opportunity records with severity, evidence, affected entity, data freshness, and status.
8. Add `ai_recommendations` table with action, expected impact, due date, and decision state (accepted/snoozed/ignored/done).

### P3 — CEO dashboard experience

9. Auto-generate daily briefing widget at top of cloud dashboard: top 5 actions, money at risk, stock to buy now, branches behaving abnormally.
10. Fix LLM prompt: add pharmacy-context system message, structured output format, output length constraint.
11. Pass last 6 chat messages to LLM for conversation continuity.
12. Add branch human names to the Organization/Branch model and display them instead of IDs.

---

## 6. Summary Verdict

The Codex report is accurate and goes deeper than my prior analysis on the data correctness issues (timestamps, movement facts, batch ID). Both analyses reach the same conclusion on the strategic gap: the AI layer needs to become proactive and persistent, not just a chat window over aggregated numbers.

**The cloud data is not yet trustworthy enough for strong business decisions.** P0 fixes are required before P2 intelligence work begins, otherwise the AI will be confidently wrong.

---

*Report written: 2026-05-18 | Author: Claude Sonnet 4.6 | Files examined: `cloud_projection.py`, `cloud_projection_service.py`, `sales.py`, `ai_manager_service.py`, `ai_insights.py`, `ai_llm_provider.py`, `ai_weekly_report_service.py`*
