# Pharma POS AI — Master Architecture & Product Roadmap

> **Document type:** Founding blueprint — single source of truth for what we build and why.
> **Created:** 2026-05-29 (UTC)
> **Owner:** John (founder / vendor)
> **Status:** Authoritative. Supersedes the *target-state* sections of `DUAL_MODE_DEPLOYMENT_PLAN.md`, `ONLINE_FIRST_ARCHITECTURE.md`, and `HYBRID_CLOUD_PRODUCTION_ARCHITECTURE_PLAN.md`. Those remain valid as implementation references for what already exists.
> **Read alongside:** `MEMORY.md` (codebase truth), `docs/audits/2026-05-29-comprehensive-architecture-audit.md` (the honest baseline this plan responds to).

This document is deliberately decisive. Where there is a choice, it names one path and the reason. It is grounded in (a) the actual code in this repository, (b) a source-cited audit of that code, and (c) researched facts about how the companies that dominate pharmacy technology in Ghana and Africa actually operate. Sources are listed at the end. **No claim here is an assumption that could be checked and wasn't.**

---

## 0. How to use this document

- **Section 1–2** tell you where you honestly are today.
- **Section 3–9** define the target architecture and the engineering decisions, layer by layer.
- **Section 10** is the strategic part: what the market leaders do that you don't yet, and the wedge that makes you uniquely winnable in Ghana.
- **Section 11–12** cover compliance and the repository structure to grow into.
- **Section 13** is the phased roadmap with absolute dates and exit criteria — the part you execute against.
- **Section 14–17** are cost, risk, metrics, and open decisions.

If you only read one thing: **Section 3 (the North Star) and Section 13 (the roadmap).**

---

## 1. Brutally honest snapshot (2026-05-29)

From the source-cited audit. Grades are the audit's; the verdicts are what they mean for the business.

| Dimension | Grade | What it means for the business |
|---|---|---|
| Core POS (`local_pos`, village) | **B+** | Real, shippable. FEFO dispensing, transaction-safe sales, tamper-evident audit chain, append-only inventory ledger. This is your asset. |
| Online-First (`online_pos`, city) | **D** | Tenant isolation is application-level only — **no Row-Level Security**. Offline queue is browser IndexedDB (not durable). The `/api/auth/heartbeat` endpoint the frontend calls **does not exist**. Not safe to sell yet. |
| Cloud Reporting (vendor) | **B** | Write-guard works, projection pipeline is sound, data-trust layer exists. |
| AI-Native | **C** | Genuinely good *plumbing* (tool-use, deterministic fallback, numeric verification, Telegram push). But it summarizes the past — no forecasting, no RAG, no prediction. The "AI-native" label currently exceeds the implementation. |
| Customer Retention | **C+** | Good consent-aware foundation (receipts, follow-ups, analytics). No loyalty, no LTV, no personalization. |
| Database Architecture | **C+** | Correct money types and ledger. But global-unique `sku`/`barcode`/`email`/`username` **break the moment two pharmacies share a database**, integer PKs risk sync collisions, no RLS. |
| Scaling Readiness | **D** | Single process, synchronous SQLAlchemy, in-process scheduler, no cache/queue/read-replica. Fine for 5 village shops; not for city-scale online. |

**The strategic reading:** You have a strong *offline village POS* and a *half-built online city POS wearing an AI badge*. The roadmap's job is to (1) make the online tier actually safe, (2) make the offline story real instead of an in-shop server, (3) earn the "AI-native" claim, and (4) add the two or three things that the market leaders monetize and you don't.

### 1.1 Bugs that must die before any paying online customer (from the audit)
These are quoted because they are concrete and shipping today:
- **C-01** No RLS in `online_pos`; `product.sku`, `product.barcode`, `user.email`, `user.username` are globally unique → second pharmacy cannot reuse a SKU; any missed `WHERE` leaks across tenants.
- **C-02** Offline sales live only in browser IndexedDB; clearing browser data destroys paid-for sales; no offline invoice number; failed items silently abandoned after 3 tries.
- **C-03** `GET /api/auth/heartbeat` is called every 15s but doesn't exist → 404 → falls through to a full catalog query as the "heartbeat."
- **C-04** Verify `alembic upgrade head` on an empty DB; the customer-retention migration chain link is unconfirmed.

---

## 2. Who you are actually competing with (researched facts)

Forget generic SaaS. These are the companies setting customer expectations in your market.

**mPharma (Ghana-born, 9 countries).** Runs the **Bloom** platform: pharmacists enter prescriptions/inventory on **tablets**; mPharma's **cloud** forecasts demand, tracks expiry, and sets optimal stock levels across the whole network. They run **Vendor-Managed Inventory (VMI)**, know real-time medicine availability across 500+ pharmacies, and launched a **Bloom POS Mobile** app. Infrastructure is **AWS**. [1][2][3]

**Field Intelligence / Shelf Life (Nigeria + Kenya, 700+ pharmacies).** A **subscription** inventory service with a **"pay-as-you-sell" consignment** model — pharmacies sell Shelf Life-supplied goods on consignment, avoiding expiry risk and the need for working-capital finance. Forecasting, QA, fulfillment, inventory in one subscription. [4][5][6]

**MedSoftwares (Ghana, "PharmaPOS").** Partnered with the **National Health Insurance Authority (NHIA)** to do **electronic NHIS claims** directly from the pharmacy POS — cutting reimbursement from **~45 days to under 14 days**, shipped as a free update to their POS users. [7]

**What this tells you:**
1. The leaders compete on **supply-chain intelligence and financing**, not on the till UI. The POS is the data-capture surface; the money is in **forecasting, VMI, consignment, and faster cash**.
2. **NHIS e-claims is a cash-flow feature pharmacies feel immediately** — and a Ghanaian competitor already ships it. This is the single most important "missing" capability for the Ghana market.
3. Everyone serious is **cloud + mobile/tablet**, not a server in the shop.

---

## 3. The North Star architecture

> One pooled, multi-tenant cloud backend. One offline-first client that is identical for city and village. Resilience lives in the client, never in a server inside the shop. The AI is grounded in deterministic services and earns its name with forecasting and retrieval.

```
   CITY pharmacy                 VILLAGE pharmacy
   (good internet)              (intermittent / none)
        │                              │
   ┌────▼──────────┐            ┌──────▼────────┐
   │ PWA (React)   │            │ PWA (React)   │   ← SAME build, SAME code.
   │ local SQLite  │            │ local SQLite  │     Offline-first ALWAYS.
   │ (PowerSync)   │            │ (PowerSync)   │     Tier = sync frequency,
   └────┬──────────┘            └──────┬────────┘     not a different product.
        │ continuous sync             │ opportunistic sync
        └──────────────┬──────────────┘
                       │  (mobile money / cards at the till)
            ┌──────────▼────────────┐
            │ PowerSync Service      │  SQLite ⇄ Postgres bidirectional sync
            └──────────┬────────────┘
            ┌──────────▼────────────┐
            │ FastAPI backend        │  pooled, multi-tenant, tenant-scoped,
            │ (stateless, versioned) │  async, circuit-broken AI, RLS-backed
            └──────────┬────────────┘
            ┌──────────▼────────────┐
            │ Managed Postgres       │  ONE cluster, RLS-enforced tenant
            │ (Supabase / DO)        │  isolation, composite-unique keys
            └─────┬───────────┬──────┘
                  │           │
        ┌─────────▼──┐   ┌────▼──────────────┐
        │ Reporting/ │   │ AI services        │  forecasting, RAG over catalog,
        │ analytics  │   │ (tool-use + push)  │  reorder, anomaly push (Telegram)
        │ read models│   └───────────────────┘
        └─────┬──────┘
        ┌─────▼─────────────────────┐
        │ Vendor fleet dashboard     │  monitor every pharmacy in one query
        │ (cloud_reporting mode)     │  (pooled DB → free aggregation)
        └───────────────────────────┘
                  ▲
   External rails: MTN MoMo / Hubtel / Paystack (payments) · NHIS CLAIM-it (e-claims) ·
                   Hubtel / Africa's Talking (SMS) · WhatsApp Business API
```

### 3.1 Five non-negotiable principles
1. **Offline is a client problem, not a deployment problem.** The shop never runs a server. The device holds a local SQLite mirror and syncs. This kills the "Docker stack per village" model and the fragile IndexedDB queue at once.
2. **One pooled database, isolation enforced by the database (RLS), not by remembering a `WHERE` clause.** Application filters are the first guard; RLS is the guarantee.
3. **The AI never invents operational numbers.** Keep the existing deterministic-first + numeric-verification design; layer real intelligence (forecasting, retrieval) *on top of* it, never replacing the guardrail.
4. **Money correctness and recoverability beat features.** FEFO, transaction-safety, audit chain, and per-tenant restore are sacred.
5. **Build toward the leaders' monetization (forecasting, NHIS cash-flow, VMI/consignment), not a prettier till.**

### 3.2 What stays, what changes
- **Keep:** the `APP_MODE` concept, FEFO, audit chain, inventory ledger, sync-event idempotency design, the AI tool-use + verification spine, consent-aware retention.
- **Change:** offline mechanism (IndexedDB queue → PowerSync local SQLite); tenant isolation (app-only → app + RLS + composite uniques + UUID surrogate keys for synced entities); scheduler (in-process → separate worker); AI (descriptive → predictive + retrieval); and add the market-defining features in §10.

---

## 4. Platform & technology decisions

Picked for a lean team in Ghana, building on your existing FastAPI/React/Postgres competence. The bias is **boring, managed, and right-sized** — not what a hyperscaler would run.

| Layer | Decision | Why (not the alternative) |
|---|---|---|
| **Client** | React **PWA**, installable, offline-capable | Already React. PWA = no app-store friction; pharmacist opens a URL. The leaders use tablets/mobile — a PWA covers both. |
| **Local store + sync** | **PowerSync** (Postgres ⇄ local SQLite, bidirectional, first-class offline) | Researched: PowerSync is the only pluggable engine with **first-class offline + a write-back queue**, is production-ready, and has a documented Supabase pairing. ElectricSQL is read-path only (writes go through your API) — wrong for an offline *till* that must write offline. [8][9] |
| **Backend** | **FastAPI**, kept; migrate hot paths to **async SQLAlchemy** | No language churn buys you nothing. Async fixes the audit's thread-starvation finding (H-03). |
| **Database** | **Managed Postgres**, single pooled cluster. **Supabase** (gives Postgres + Auth + RLS + Storage and pairs with PowerSync) or **DigitalOcean Managed Postgres** | One DB → the vendor dashboard is one query (your "monitor all pharmacies" requirement is free). RLS is the isolation guarantee. |
| **Connection pooling** | **pgBouncer / Supavisor** in front of Postgres | Audit flagged no pooling proxy (Scaling 3/10). Mandatory before multi-tenant scale. |
| **Background work** | **Separate worker process** (own container) for scheduler + sync projection + SMS + AI batch | Audit H-08: in-process APScheduler starves the POS. Move it out. |
| **Hosting** | **DigitalOcean** (App Platform / Droplets) or stay on **Render** to start; Fly.io optional | Right-sized. AWS is what mPharma runs *at 500 pharmacies* — graduate to it under a compliance/scale contract, not before. |
| **Auth/identity** | Supabase Auth or keep current JWT, with `organization_id` + `branch_id` + role in the token | Isolation starts at the token, server-side, admin-provisioned (no self-registration — already your rule). |
| **Payments** | **Hubtel** (Ghana-built, MoMo + POS, GH₵25/mo + 1.95%) and/or **Paystack** (1.95%, no monthly, MoMo + cards). **MTN MoMo is mandatory** (~90% share, 20M+ wallets). | Researched. A Ghana pharmacy till without MoMo is unsellable. [10] |
| **SMS / WhatsApp** | **Hubtel** + **Africa's Talking** (already stubbed in `message_adapter.py`); WhatsApp via BSP (360dialog/Twilio) | Local last-mile beats Twilio-only. Adapters already exist; wire the real providers. |
| **NHIS e-claims** | Integrate **NHIA CLAIM-it** (offline-capable) export/submission | See §10.1 — the highest-value market feature. [7] |
| **AI models** | **Claude** (Opus/Sonnet) primary via existing provider layer; deterministic fallback always on | Provider layer already abstracts OpenAI/Claude/Groq. Keep keys server-side (already done). |
| **Observability** | **Sentry** (client + server) + Postgres metrics (Grafana Cloud / Better Stack later) | The offline client *will* surface edge cases; you need visibility. Skip Datadog cost until bigger. |

**The two decisions that define everything:** *(1) PowerSync local-SQLite offline-first client, and (2) one pooled RLS-enforced Postgres.* Everything else is swappable.

---

## 5. Database architecture

### 5.1 Tenancy model (target)
- **Pooled multi-tenant:** `Organization → Branch → Device → User`. Every operational row carries `organization_id` (NOT NULL after backfill) and `branch_id`.
- **Isolation in three layers:**
  1. **Application scoping** (exists today) — query filters by `current_user.organization_id`.
  2. **PostgreSQL RLS** (NEW, the guarantee) — `ENABLE ROW LEVEL SECURITY` on every tenant table; policies keyed off a session GUC `app.current_organization_id` set per request. A missed filter then returns nothing instead of leaking. *Closes audit C-01.*
  3. **Composite unique constraints** (NEW) — replace global uniques with `(organization_id, sku)`, `(organization_id, barcode)`, `(organization_id, email)`, `(organization_id, username)`. *Closes the SKU-collision half of C-01.*

> **Why pooled, not database-per-tenant:** at your scale (tens of pharmacies) and team size, one RLS-enforced pooled DB gives free fleet aggregation and one migration to run. Reserve **database-per-tenant ("silo")** for a future enterprise chain that contractually demands physical isolation — the "bridge" pattern. Don't build silo now.

### 5.2 Keys & sync-safety
- **Surrogate UUIDs** for every entity that syncs (sales, sale_items, products, batches, customers, inventory_movements, follow_ups). Audit flagged integer auto-increment PKs as a **sync-collision risk** between offline installs. Generate IDs **client-side** so an offline sale has a stable, globally-unique id and a deterministic invoice number *before* it ever reaches the server. *This also fixes C-02's "no offline invoice number."*
- Keep integer PKs only for non-synced, server-only tables (e.g., reporting projections).

### 5.3 Indexes (audit H-02 — add before scale)
Composite indexes for the real query shapes:
- `sales(organization_id, occurred_at DESC)` and `sales(organization_id, branch_id, occurred_at DESC)`
- `products(organization_id, is_active, name)` and a trigram/`pg_trgm` index for name/barcode search
- `customers(organization_id, phone)` (unique)
- `customer_follow_ups(organization_id, status, scheduled_at)`
- `inventory_movements(organization_id, product_id, event_type, occurred_at)`

### 5.4 Integrity hardening
- DB-level `CHECK` constraints: `quantity > 0`, `discount <= subtotal`, `total_amount >= 0` (defense behind the app validation already in `sales.py`).
- `updated_at` via **Postgres trigger**, not ORM `onupdate` (audit H-01) — so bulk/raw updates don't leave it NULL.
- Consider `SaleItem.quantity` as `Numeric` if any product is dispensed fractionally (audit M-01); confirm with the pharmacies first.

### 5.5 Money & time (already mostly right — keep)
- `Numeric(12,2)` for all money (good). All timestamps timezone-aware UTC; **business windows use `coalesce(occurred_at, created_at)`** (decision 3.16). Fix the one naive `datetime.now()` in the local today-summary (audit H-04).

---

## 6. Backend architecture

### 6.1 Service shape
- Keep the **endpoints → services → models** layering. Services already encode the business rules the AI relies on — that's the asset that makes tool-use safe.
- **Async the hot paths** (sales create, product search, catalog) on async SQLAlchemy; leave cold admin paths sync if needed. Raise pool size + put pgBouncer in front in the interim (audit H-03).
- **Stateless backend** so you can run 2+ instances behind a load balancer. The scheduler must NOT live in the API process (see §6.3) or you get duplicate jobs when you scale out.

### 6.2 API discipline
- **Version the API** (`/api/v1/...`) — audit M-09. Offline clients in the field will lag the server; you need to evolve without breaking installed PWAs.
- **Rate-limit beyond login** (audit M-10): product search, sale create, AI chat.
- **Tighten CORS** to real methods/headers and known origins (audit M-05).
- Add **`GET /api/v1/auth/heartbeat`** returning 200 — *closes C-03*. The PWA online-detector stops hammering the catalog.

### 6.3 Background worker (new, separate process/container)
Move out of the API process: cloud projection, sync reconciliation, Telegram alerts, follow-up dispatch, AI weekly reports, forecasting batch jobs. It gets its **own DB pool**. Use APScheduler in that worker now; graduate to a real queue (RQ/Celery + Redis) when job volume justifies it. *Closes audit H-08.*

### 6.4 AI call safety
- **Circuit breaker + timeout** around LLM calls (audit H-05): after N consecutive timeouts, skip the LLM for a cool-down and serve the deterministic answer. AI must never be able to delay a checkout.
- Run AI in the worker / a separate pool for push briefings; the interactive chat path keeps its short timeout and deterministic fallback.

---

## 7. Offline-first & sync architecture (the biggest change)

**Replace** the IndexedDB queue (`offlineQueue.ts`) and the in-shop-server model with a **PowerSync local SQLite** mirror on every client.

### 7.1 How it works
- The PWA reads/writes a **local SQLite** database always (online or offline). The till never waits on the network.
- **PowerSync Sync Rules** define per-tenant "buckets" — a device only ever syncs **its own organization's** rows (isolation reinforced at the sync layer, on top of RLS).
- Writes go to a **durable local upload queue** and replicate to Postgres when connectivity returns. This is durable storage, not browser cache — *closes C-02*.
- City = continuous sync; village = opportunistic sync when a signal appears. **Same code path.**

### 7.2 The genuinely hard part: stock conflicts
A pharmacy is not a notes app — two devices (or one offline device over hours) can sell the **same batch** down past zero. Decide the policy explicitly:
- **Server is the authority on stock.** Client-side stock counts are advisory; the **server re-validates against batches with `with_for_update()`** at sync time (the logic already exists in `sales.py`).
- **Allow the sale, flag the oversell.** A completed cash sale is real money already taken — never silently drop it. If sync reveals the batch went negative, **accept the sale, drive stock negative, and raise a reconciliation exception** for the pharmacist (an "oversold while offline" worklist). This matches the audit's instinct that financial data must never be lost.
- **FEFO re-allocation on sync:** if the client guessed a batch that's now empty, the server re-allocates to the next-expiry batch and records the correction in the inventory ledger.
- **Client-side provisional decrement:** the offline client SHOULD decrement local stock optimistically so a single device doesn't oversell itself (today's `online_pos` does not — a known gap). Cross-device oversell is handled by the server rule above.
- **Max offline window:** keep the planned configurable limit (e.g., 24–72h) after which the client warns and then blocks new sales until it syncs, bounding divergence.

### 7.3 Service Worker
Ship a real Service Worker so the PWA shell, catalog, and app assets load with zero network (audit noted its absence). PowerSync handles data; the Service Worker handles the app itself.

---

## 8. The AI-native layer — how to actually earn the name

Today the AI is a **well-guarded Q&A wrapper over historical projections** (tool-use, deterministic-first, numeric verification, Telegram push). That plumbing is genuinely good — **keep all of it**. "AI-native" means the AI must also **predict, retrieve, and act**, not just summarize. Build these *on top of* the existing verification guardrail so nothing can fabricate a number.

### 8.1 Keep (the trust spine)
- Deterministic answer always computed first; LLM explains/prioritizes (decision 3.27).
- **Numeric verification**: reject LLM prose whose figures aren't in approved tool evidence, fall back to deterministic (decision 3.29). This is your moat against hallucinated business numbers — never remove it.
- Push-first Telegram briefings + anomaly alerts (decision 3.28).
- Server-side provider selection, keys server-side (decision 3.22).

### 8.2 Add — predictive (the leaders' core, see mPharma Bloom forecasting)
1. **Demand forecasting per product per branch.** Start deterministic and explainable: moving average + seasonality + trend (e.g., Holt-Winters / simple exponential smoothing) computed in the worker from `CloudInventoryMovementFact` sale movements. This is the foundation for reorder and VMI.
2. **Reorder-point engine** using forecast demand + supplier **lead time** + safety stock → concrete "order N units of X by date Y." Today's `get_stock_velocity` is days-of-stock only; this turns it into an action. Surface as a new AI tool `get_reorder_plan`.
3. **Expiry-risk forecasting:** combine batch expiry + forecast velocity to flag "this batch will expire before you can sell it" → clearance/return action *before* it's dead stock.

### 8.3 Add — retrieval (RAG)
4. **Catalog + knowledge retrieval** using **pgvector** in the same Postgres. Embed the product catalog and a curated, **non-clinical** knowledge base (formulary names, pack sizes, generic↔brand mapping, supplier info). Enables: natural-language product search ("the blood-pressure generic we stock"), brand/generic substitution lookups at the till, and grounded AI answers about *your* catalog. **Hard guardrail:** the AI gives no clinical/dosage advice — `_is_disallowed_request` already refuses this; keep it strict and extend the refusal list.

### 8.4 Add — personalization & action
5. **Personalized retention:** follow-up and re-engagement messages templated from the customer's actual purchase history (chronic-refill reminders by computed refill date), not the current generic template. Consent rules unchanged.
6. **Agentic reorder drafts:** the AI *drafts* a purchase order from the reorder engine; a human approves. Never auto-mutates stock (the read-only safety note stays true for the chat assistant; write actions go through explicit, audited, human-approved endpoints).

### 8.5 AI guardrails that must scale with capability
- Every new AI tool returns **deterministic service output**; the LLM only narrates.
- Forecasts are labeled as estimates with confidence; the numeric verifier is extended to treat forecast outputs as approved evidence so they pass verification while staying clearly flagged as predictions.
- All AI-suggested *actions* (reorder, clearance, message campaigns) are **proposals requiring human approval**, logged in the audit chain.

---

## 9. Customer retention & growth

You have the consent-aware spine (registration, receipts, follow-ups, churn/at-risk analytics, SMS adapters). Grow it into a retention engine:
- **Loyalty / points** tied to `customer_id` on sales (schema already links sales→customer).
- **Customer Lifetime Value (LTV)** and **RFM segmentation** (recency/frequency/monetary) computed in the worker; feed the AI and the vendor dashboard.
- **Re-engagement campaigns** for at-risk/churned segments (consent-gated, opt-out honored via provider webhooks — currently noted as not-yet-implemented in `message_adapter.py`; build the STOP/UNSUBSCRIBE webhook).
- **WhatsApp** channel (higher open rates than SMS in Ghana) via a BSP, reusing the adapter interface.
- **Digital receipts as an acquisition loop:** every receipt is a branded touchpoint; add a refill reminder CTA.

---

## 10. What you're missing that the dominators monetize — and your unique wedge

This is the section that decides whether you build a nicer till or a business pharmacies can't churn from.

### 10.1 NHIS electronic claims — build this; it is the Ghana wedge
Researched fact: a Ghanaian competitor (MedSoftwares "PharmaPOS") integrated **NHIA CLAIM-it** to cut pharmacy reimbursement from **~45 days to <14 days**. [7] CLAIM-it is **offline-capable** and supports export-to-file or direct submission. [7]
- **Why it wins:** NHIS is a huge share of Ghana pharmacy revenue; faster reimbursement is *cash in the owner's pocket*, felt every cycle. It is the rare feature a pharmacy will switch software for.
- **How it fits you:** your POS already captures the dispensing data a claim needs. Add an **NHIS claim builder** that validates against NHIS rules and **exports/submits via CLAIM-it** — and because your client is offline-first, claims can be prepared offline and submitted when connected, which suits village shops perfectly.
- **Priority:** highest-value market feature after the online tier is safe.

### 10.2 Demand forecasting & smart reorder (mPharma Bloom's core)
Covered in §8.2. The leaders' platforms are *forecasting engines with a POS attached*. This is what justifies a subscription over a one-time license.

### 10.3 Vendor-Managed Inventory / consignment ("pay-as-you-sell")
mPharma runs VMI; Field Intelligence runs consignment so pharmacies avoid expiry risk and working-capital strain. [1][4]
- **Your version:** because you sit on real-time multi-pharmacy sales + stock data, you can offer **supplier-facing reorder aggregation** and, later, a **consignment program** (sell-then-pay). This turns you from a software vendor into a **supply-chain + fintech** player — the actual moat in this market. Long-horizon, but design the data model so it's possible (you already have org/branch/movement facts).

### 10.4 Mobile money at the till
MoMo is ~90% of the market. [10] A pharmacy POS that reconciles MoMo payments automatically (Hubtel/Paystack/MoMo API) removes manual cash-up pain. Table stakes, not a differentiator — but its *absence* is disqualifying.

### 10.5 Your unique angle (defensible, and not just "me too")
Combine three things the incumbents don't unify:
1. **True offline-first that's identical online and offline** (PowerSync) — mPharma's tablet model assumes connectivity; you serve the village shop *and* the city shop with one product.
2. **An AI that is trustworthy by construction** (numeric verification + deterministic fallback) — most "AI" pharmacy pitches can't promise their numbers are real. You can.
3. **NHIS cash-flow + forecasting + retention in one offline-capable box**, priced for the independent Ghanaian pharmacy, not the enterprise chain.

That triangle — *offline-anywhere + provably-honest AI + NHIS cash acceleration* — is a positioning no current player occupies.

---

## 11. Security, compliance & data protection (Ghana)

Researched facts about **Ghana's Data Protection Act, 2012 (Act 843)** [11]:
- **Mandatory registration** (§27): a data controller processing personal data **must register with the Data Protection Commission**; registration is **valid 2 years**, then renewed. → **Action: register as a data controller before onboarding paying customers handling customer data.**
- **Health data is "special personal data"** — processing is **prohibited without explicit consent** (or narrow medical/legal grounds). → Your consent model (`sms_consent`, `whatsapp_consent`, `consent_recorded_at`, health notes never sent in messages) is on the right track; make **explicit consent at registration** a hard requirement and record it.
- **Implement opt-out** (STOP/UNSUBSCRIBE webhook) — currently a known gap in `message_adapter.py`.

Engineering security (from audit):
- **RLS** (the big one — §5.1).
- Move auth token off `localStorage` toward `httpOnly` cookies where the deployment allows (audit M-04); low risk on kiosk, real risk on shared browsers.
- Keep: bcrypt, JWT, login rate-limit, secret-key validation, no public registration, per-device sync tokens (decision 3.12), tamper-evident audit chain.
- Per-tenant **backup & restore** with tracked **restore drills** (already a model) — extend to the pooled cloud DB; a pharmacy must be restorable independently.

---

## 12. Target repository structure

Evolve toward this; it separates the API, the worker, the AI, and the client cleanly so they scale and deploy independently.

```
pharma-pos-ai/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/        # versioned API
│   │   ├── core/                    # config, app_mode, security, money, tenancy(RLS session)
│   │   ├── db/                      # async engine, session, RLS GUC helper
│   │   ├── models/                  # UUID surrogate keys on synced entities
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── pos/                 # sales, inventory (FEFO), stock
│   │   │   ├── retention/           # customers, receipts, follow-ups, loyalty, LTV
│   │   │   ├── ai/                  # tool-use, verification, forecasting, RAG, reorder
│   │   │   ├── claims/              # NHIS claim builder + CLAIM-it export  (NEW)
│   │   │   ├── payments/            # Hubtel / Paystack / MoMo adapters     (NEW)
│   │   │   ├── messaging/           # SMS/WhatsApp adapters (+ opt-out webhook)
│   │   │   └── sync/                # reconciliation, projection, snapshots
│   │   └── main.py                  # stateless API only (no scheduler)
│   ├── worker/                      # SEPARATE process: scheduler, projection,
│   │   └── jobs/                    #   forecasting, alerts, follow-ups, reports
│   ├── alembic/
│   └── tests/                       # incl. tenant-isolation + offline-sync tests
├── frontend/                        # React PWA
│   ├── src/
│   │   ├── db/                      # PowerSync schema + local SQLite           (NEW)
│   │   ├── sync/                    # PowerSync connector, conflict UI          (NEW)
│   │   ├── pages/  components/  stores/  services/  hooks/
│   │   └── sw/                      # Service Worker                            (NEW)
├── powersync/                       # Sync Rules (per-tenant buckets)           (NEW)
├── infra/                           # docker-compose, pgBouncer, deploy config
└── docs/                            # this file is the index of intent
```

---

## 13. The phased roadmap

Dates are targets from 2026-05-29. Each phase has an **exit gate** — do not start the next phase until the gate is green. **Phase 0 is mandatory and blocks selling the online tier.**

### Phase 0 — Stop the bleeding (target: by 2026-06-19) 🔴 BLOCKER
*Make the existing online tier safe and honest. Small, surgical, high-leverage.*
- Add `GET /api/v1/auth/heartbeat` (C-03).
- Composite unique constraints `(organization_id, sku|barcode|email|username)` (C-01a).
- Verify `alembic upgrade head` on an empty DB; fix the customer-retention chain link (C-04).
- Close the unscoped read endpoints (categories, suppliers, notifications) flagged in `ONLINE_FIRST_ARCHITECTURE.md §8`.
- Add the **tenant-isolation integration test** (two orgs, assert zero cross-visibility on every list endpoint).
- Fix the naive `datetime.now()` in the local today-summary (H-04); exclude `*.db` from Docker build (H-07).
- **Exit gate:** two-org isolation test passes; fresh DB migrates clean; heartbeat returns 200; no global-unique collisions possible.

### Phase 1 — Real multi-tenancy + scale floor (target: 2026-07-31)
- **PostgreSQL RLS** on all tenant tables, GUC set per request (C-01b).
- **UUID surrogate keys** + client-generated IDs/invoice numbers for synced entities (sync-collision + offline-invoice fix).
- Composite **indexes** (H-02); DB `CHECK` constraints; `updated_at` triggers (H-01).
- **pgBouncer/Supavisor**; async SQLAlchemy on hot paths; API **versioning**; CORS tightening; broader rate limits.
- Split the **worker process** out of the API (H-08); circuit breaker on LLM (H-05).
- **Exit gate:** RLS proven (penetration test: forged `organization_id` leaks nothing); load test sustains target concurrent tills without pool starvation.

### Phase 2 — Offline-first done right (target: 2026-09-15)
- Integrate **PowerSync**: local SQLite mirror, per-tenant Sync Rules, durable write queue. Retire the IndexedDB queue (C-02).
- Implement the **stock-conflict policy** (§7.2): server-authoritative re-validation, accept-and-flag oversell worklist, FEFO re-allocation on sync, client-side provisional decrement, max-offline-window.
- Ship the **Service Worker** for true offline app shell.
- **Exit gate:** kill the network mid-sale on two devices selling the same batch → both sales survive, stock reconciles, oversell is flagged not lost; clearing browser data loses nothing (durable queue verified).

### Phase 3 — Payments + NHIS (the revenue wedge) (target: 2026-11-15)
- **MoMo + card** at the till via **Hubtel/Paystack** with automatic payment reconciliation.
- **NHIS claim builder + CLAIM-it export/submission** (§10.1), offline-capable.
- **Exit gate:** a real pharmacy completes a MoMo sale and submits a validated NHIS claim from the system; reimbursement-cycle improvement measured against their old process.

### Phase 4 — Earn "AI-native" (target: 2026-12-31)
- **Demand forecasting** + **reorder-point engine** (`get_reorder_plan` tool) + **expiry-risk forecasting** (§8.2).
- **pgvector RAG** over catalog + non-clinical knowledge; natural-language product search; generic/brand substitution (§8.3).
- **Personalized retention** (refill reminders) + **LTV/RFM segmentation** (§9).
- Extend numeric verification to label/accept forecast evidence; all AI actions are human-approved proposals.
- **Exit gate:** forecast-driven reorder plan beats the current days-of-stock heuristic on a back-test; AI catalog search answers real pharmacist queries; zero unverified numbers reach users.

### Phase 5 — Platform / moat (2027, design-for now)
- **Supplier-facing reorder aggregation**; foundations for **VMI / consignment** ("pay-as-you-sell") (§10.3).
- Loyalty program; WhatsApp channel; vendor fleet analytics deepened.
- **Exit gate:** at least one supplier integration live; consignment pilot with one pharmacy.

---

## 14. Cost model (order-of-magnitude, lean start)

| Item | Early (≤10 pharmacies) | Notes |
|---|---|---|
| Managed Postgres (Supabase/DO) | low monthly tier | one pooled cluster |
| PowerSync | free/low tier to start | usage-based as you grow |
| Backend + worker hosting (Render/DO) | low monthly | two small services |
| Payments | **0 fixed** (Paystack) or GH₵25/mo (Hubtel) + ~1.95%/txn | passed through to/factored into pricing |
| SMS/WhatsApp | per-message | bill to pharmacy or bundle |
| LLM (Claude) | usage-based, capped | deterministic fallback bounds cost; circuit breaker caps spend |
| Sentry/monitoring | free/low tier | |

**Pricing direction:** monthly **subscription per pharmacy/branch** (the leaders' model — Field Intelligence is subscription, mPharma is VMI/network). Avoid one-time licenses for the online tier; recurring value (forecasting, NHIS, retention) justifies recurring revenue. Village `local_pos` can stay a license + optional sync if the market demands it.

---

## 15. Risks & kill-criteria

| Risk | Mitigation | Kill / pivot signal |
|---|---|---|
| Multi-tenant data leak | RLS + composite uniques + isolation tests (Phase 0–1) | Any real cross-tenant leak in production → halt online onboarding until RLS proven |
| Offline sale data loss | PowerSync durable queue + accept-and-flag policy (Phase 2) | Any irrecoverable paid sale → Phase 2 incomplete, do not scale |
| NHIS integration harder than expected | Start with CLAIM-it **export** (offline file) before direct submission | If CLAIM-it integration is closed/unavailable, partner or pivot to export-only |
| "AI-native" stays a label | Phase 4 forecasting/RAG with verification | If forecasts don't beat heuristics on back-test, keep deterministic and drop the predictive claim — never market unimplemented AI (CLAUDE.md rule) |
| Scope sprawl across 3 modes | One codebase, mode flags, shared services; this doc gates phases | If maintaining 3 modes stalls core POS correctness, cut `online_pos` features, protect `local_pos` |
| Lean-team ops overload | Managed everything; separate worker; no k8s/AWS until forced | Ops toil > feature time for 2 sprints → simplify infra |

---

## 16. Success metrics (what "winning" looks like)

- **Reliability:** zero lost sales offline; zero cross-tenant leaks; FEFO/audit integrity 100%.
- **Market fit:** NHIS reimbursement cycle measurably shorter for pilot pharmacies; MoMo reconciliation removes manual cash-up.
- **AI value:** reorder plans reduce stockouts and dead stock vs. baseline; AI numbers verified 100% (no hallucinated figures shipped).
- **Retention (yours):** pharmacies don't churn because forecasting + NHIS + retention compound switching cost.
- **Business:** recurring subscription revenue per branch; path to supplier/consignment revenue.

---

## 17. Open decisions (need your input)

1. **Primary cloud:** Supabase (fastest path, pairs with PowerSync, includes Auth) vs. DigitalOcean Managed Postgres (you mentioned DO). Recommendation: **Supabase to start**, DO if/when you need control.
2. **Payments:** Hubtel (Ghana-built, POS-oriented, monthly fee) vs. Paystack (no monthly, MoMo+cards) vs. both. Recommendation: **Paystack first** (no fixed cost), add Hubtel if pharmacies want its POS hardware/ecosystem.
3. **NHIS scope:** export-to-CLAIM-it first vs. direct submission integration. Recommendation: **export first** (lower integration risk), then direct.
4. **Pricing:** subscription per branch vs. per device vs. flat per pharmacy. Recommendation: **per branch**.
5. **Village tier future:** keep `local_pos` as a distinct offline product, or fold everyone onto the PowerSync offline-first client (which is offline-capable anyway)? Recommendation: **converge on one offline-first client**; `local_pos` becomes "syncs rarely," not a separate architecture.

---

## Sources

1. *Inside mPharma's Journey: Fixing Pharmacy Supply Chains at Scale* — Today Africa. https://todayafrica.co/inside-mpharmas-journey/
2. *mPharma Launches Mobile POS For Pharmacies* — TechLabari. https://techlabari.com/mpharma-lauches-mobile-pos-for-pharmacies/
3. *How mPharma Uses the Power of AWS Cloud* — TechLabari. https://techlabari.com/how-mpharma-uses-the-power-of-aws-cloud-in-its-mission-to-provide-healthcare-in-africa/ ; mPharma + AWS — MyJoyOnline. https://www.myjoyonline.com/mpharma-revolutionises-healthcare-delivery-in-africa-with-aws-partnership/
4. *Field Intelligence targets 11 African cities to expand its pharmacy inventory-management service* — TechCrunch. https://techcrunch.com/2021/07/28/field-intelligence-targets-11-african-cities-to-expand-its-pharmacy-inventory-management-service/
5. *Shelf Life Stocking Up Pharmacies Across East and West Africa* — Field. https://field.inc/news/nigeria-expansion/
6. *Field Intelligence is digitizing Africa's pharmaceutical supply* — Quartz Africa. https://qz.com/africa/2081055/field-intelligence-is-digitizing-africas-pharmaceutical-supply
7. *MedSoftwares Partners with NHIS Ghana for Seamless Insurance Claims* — MedSoftwares. https://www.medsoftwares.com/news/partnership-nhis-ghana ; *NHIS CLAIM-it*. https://claimit.nhia.gov.gh/
8. *ElectricSQL vs PowerSync* — PowerSync. https://powersync.com/blog/electricsql-vs-powersync
9. *Offline-First Apps Made Simple: Supabase + PowerSync* — PowerSync. https://www.powersync.com/blog/offline-first-apps-made-simple-supabase-powersync
10. *Mobile Money Integration for Ghana* — Faciotech. https://blog.faciotech.com/mobile-money-payment-integration-ghana ; *Hubtel Developer Portal*. https://developers.hubtel.com/ ; *Paystack — Pay with transfer*. https://support.paystack.com/en/articles/2128642
11. *Data Protection Act, 2012 (Act 843)* — NITA (full text). https://nita.gov.gh/wp-content/uploads/2017/12/Data-Protection-Act-2012-Act-843.pdf ; Data Protection Commission — Registration. https://dataprotection.org.gh/registration/

---

*This blueprint is grounded in the repository as of 2026-05-29 and the audit at `docs/audits/2026-05-29-comprehensive-architecture-audit.md`. Update this document when a phase exit gate is met or a §17 decision is made; log the change in `MEMORY.md` per the repository's memory protocol.*
