# Dual-Mode Deployment Plan — Online-First + Offline-First

> **Created:** 2026-05-28 UTC
> **Status:** SUPERSEDED on 2026-06-07
> **Context:** Market feedback confirms city pharmacies want online-first features (customer retention, digital receipts, health follow-ups, real-time AI), while village pharmacies need a fully offline local installation. One codebase must serve both.
>
> The shared-database `online_pos` proposal in this document is historical.
> Current architecture uses one `operational_pos` runtime, hosted/offline feature
> flags, a dedicated operational database per pharmacy organization, and a
> central reporting plane. See
> `docs/architecture/unified-operational-runtime.md` and
> `docs/architecture/hosted-tenant-topology-and-backup.md`.

---

## 1. Problem Statement

The system was built offline-first: each pharmacy runs a local PostgreSQL database, and a sync outbox pushes events to the cloud for owner-level reporting. This design:

- Makes AI insights inconsistent (cloud data is always delayed)
- Makes customer-facing features impossible (receipts, follow-ups need live connectivity)
- Creates sync complexity (outbox, projection, reconciliation, business-time correction)
- Is the wrong model for city pharmacies with stable internet

However, village pharmacies with unreliable or no internet **still need** the offline-first model.

---

## 2. Product Tiers

### Tier 1 — PharmaLocal (Offline-First / Village)

| Attribute | Value |
|---|---|
| **Target** | Village/rural pharmacies with unreliable internet |
| **Database** | Local PostgreSQL on the pharmacy machine |
| **POS** | Full — works with zero internet |
| **AI** | Deterministic local insights only |
| **Sync** | Optional one-way to cloud when internet is available |
| **Customer features** | Not available |
| **Reports** | Local dashboard only |
| **Pricing model** | One-time or annual license |

**This is what exists today.** No architectural changes needed for this tier.

### Tier 2 — PharmaPro (Online-First / City)

| Attribute | Value |
|---|---|
| **Target** | City pharmacies with stable internet |
| **Database** | Supabase (cloud PostgreSQL) as primary |
| **POS** | Full — writes directly to cloud DB |
| **AI** | Full cloud AI with live data, no sync lag |
| **Sync** | Not needed — single database is the source of truth |
| **Customer features** | Registration, digital receipts, health follow-ups |
| **Reports** | Full cloud dashboard + AI + Telegram alerts |
| **Offline fallback** | Local transaction queue for network drops |
| **Pricing model** | Monthly subscription |

**This requires the changes below.** The cloud deployment stops being reports-only and becomes a full operational deployment for city clients.

---

## 3. Architecture Changes

### 3.1 New App Mode: `online_pos`

The existing `APP_MODE` system already has:
- `local_pos` — full POS, local database
- `cloud_reporting` — reports-only, rejects POS writes

Add a third mode:
- `online_pos` — full POS, cloud database, customer features enabled

```
APP_MODE=local_pos         → Village: local DB, full POS, optional sync
APP_MODE=online_pos        → City:   cloud DB, full POS, customer features, real-time AI
APP_MODE=cloud_reporting   → Vendor: reports only, no POS writes (owner dashboard)
```

**Implementation:**
- [ ] Add `online_pos` to `app_mode.py` accepted modes
- [ ] `online_pos` mode allows all POS writes (like `local_pos`)
- [ ] `online_pos` mode enables customer retention endpoints
- [ ] `online_pos` mode skips sync outbox (writes go directly to cloud DB)
- [ ] Frontend `VITE_APP_MODE=online_pos` shows POS + customer features in sidebar

### 3.2 Offline Fallback Queue (Online-First Clients Only)

When a city pharmacy loses internet mid-shift, the system must not freeze. This is simpler than the full sync outbox:

- Local browser queue (IndexedDB or localStorage) holds pending transactions
- When connectivity returns, queue flushes to the cloud DB automatically
- Queue is short-lived (minutes/hours, not days)
- UI shows clear "OFFLINE — transactions queued" banner
- Maximum offline window: configurable (default 4 hours)

**Implementation:**
- [ ] Add offline detection in the frontend (navigator.onLine + API heartbeat)
- [ ] Add IndexedDB transaction queue for POS sales
- [ ] Add auto-flush on reconnect with conflict detection
- [ ] Add offline status banner in the UI
- [ ] Add queue size and age monitoring
- [ ] Define max offline window and force logout/block after expiry

### 3.3 Multi-Tenant Online Database

City clients share the Supabase database. Each pharmacy's data must be isolated:

- The tenancy model (Organization → Branch → Device) already exists
- POS write endpoints must scope all queries to the authenticated user's organization
- Row-level security (RLS) in Supabase as a defense-in-depth layer

**Implementation:**
- [ ] Add organization_id scoping to all POS write endpoints in online_pos mode
- [ ] Add Supabase RLS policies for the core tables (sales, products, batches, inventory_movements)
- [ ] Verify tenant isolation with integration tests
- [ ] Ensure user provisioning is per-organization (already admin-controlled)

---

## 4. Customer Retention Module (Online-First Only)

> This module is the competitive differentiator for city pharmacies. It only activates in `online_pos` mode.

### 4.1 Customer Registration

- [ ] **Customer model:** `Customer` table with fields: name, phone, email, date_of_birth, gender, allergies (JSON), notes, registered_at, registered_by_user_id, organization_id, branch_id
- [ ] **Registration flow:** cashier registers customer at POS or via dedicated page
- [ ] **Customer search:** search by name, phone number at POS
- [ ] **Link to sale:** optional customer_id on `Sale` — links purchase history to a person
- [ ] **Customer profile page:** purchase history, last visit, total spend, preferred products
- [ ] **Privacy:** customer data stays within the organization's tenant scope

### 4.2 Digital Receipts

- [ ] **Receipt generation:** after sale completion, generate a formatted receipt
- [ ] **Delivery:** send receipt via SMS or WhatsApp to the customer's phone number
- [ ] **Receipt content:** pharmacy name, date, items purchased (name, quantity, price), total, payment method, cashier name
- [ ] **Receipt history:** customer can request re-send of past receipts
- [ ] **SMS/WhatsApp integration:** Twilio, Africa's Talking, or WhatsApp Business API adapter

### 4.3 Health Follow-Up

- [ ] **Follow-up scheduling:** after dispensing, optionally schedule a follow-up check
- [ ] **Follow-up triggers:** configurable per product category (e.g., antibiotics: follow up in 3 days)
- [ ] **Follow-up message:** automated SMS/WhatsApp: "Hi [name], how are you feeling after taking [drug]? Reply 1 for better, 2 for same, 3 for worse"
- [ ] **Response tracking:** log customer responses
- [ ] **Escalation:** if customer reports "worse", flag for pharmacist attention
- [ ] **Follow-up dashboard:** pharmacist view of pending and completed follow-ups

### 4.4 Customer Analytics (CEO Level)

- [ ] **Retention metrics:** repeat customers, visit frequency, average spend per customer
- [ ] **Churn detection:** customers who haven't returned in X days
- [ ] **Top customers:** ranked by spend, visit frequency
- [ ] **Product affinity:** what products each customer buys most
- [ ] **AI integration:** customer insights included in CEO AI chat and briefings

---

## 5. Feature Matrix

| Feature | PharmaLocal (Village) | PharmaPro (City) | Vendor Dashboard |
|---|---|---|---|
| POS / Sales | ✅ | ✅ | ❌ |
| Inventory / FEFO | ✅ | ✅ | ❌ |
| Stock Adjustments | ✅ | ✅ | ❌ |
| Audit Trail | ✅ | ✅ | ❌ |
| Local Reports | ✅ | ✅ | ❌ |
| Cloud Reports | Via sync | ✅ Real-time | ✅ |
| AI Chat | Deterministic | Full LLM + live data | ✅ |
| Customer Registration | ❌ | ✅ | ❌ |
| Digital Receipts | ❌ | ✅ | ❌ |
| Health Follow-ups | ❌ | ✅ | ❌ |
| Telegram Alerts | Via sync | ✅ Real-time | ✅ |
| Offline Capability | Full (primary) | Fallback queue | N/A |
| Sync Outbox | ✅ | Not needed | N/A |
| Backup/Restore | Local pg_dump | Supabase managed | N/A |
| Customer Analytics | ❌ | ✅ | ✅ Fleet-wide |

---

## 6. Implementation Phases

### Phase A: Foundation (Enable Online POS Mode)

> Make the deployed cloud app a functional POS for city clients, not just a reporting portal.

1. [x] Add `online_pos` app mode to backend and frontend
2. [x] Re-enable POS writes for `online_pos` mode (not `cloud_reporting`)
3. [ ] Add organization_id scoping to POS endpoints in online_pos mode
4. [x] Skip sync outbox in online_pos mode (writes are already in the cloud DB)
5. [x] Frontend: show full POS + cloud dashboard in online_pos mode
6. [ ] Test: verify POS works against Supabase in online_pos mode

### Phase B: Offline Fallback (Network Resilience)

> City POS must not freeze when internet drops.

1. [x] Implement offline detection (navigator.onLine + API heartbeat)
2. [x] Build IndexedDB transaction queue (`offlineQueue.ts`)
3. [x] Implement auto-flush on reconnect (OfflineBanner + flush())
4. [x] Add offline status UI banner (OfflineBanner.tsx)
5. [ ] Add configurable max offline window (deferred — define timeout policy)
6. [ ] Test: simulate network drop during sale, verify queue and recovery

### Phase C: Customer Retention Module

> The upsell feature that differentiates PharmaPro from competitors.

1. [x] Design and create `Customer` model and migration
2. [x] Build customer registration flow (POS + dedicated page)
3. [x] Link customers to sales (optional customer_id on Sale)
4. [x] Integrate SMS/WhatsApp delivery adapter (StubAdapter; plug in real provider via SMS_PROVIDER env var)
5. [x] Build digital receipt generation and delivery (dispatched after sale via message adapter)
6. [x] Build health follow-up scheduling and automation (hourly scheduler job; PENDING → SENT)
7. [x] Build customer profile page with purchase history
8. [x] Build follow-up dashboard for pharmacists

### Phase D: Customer Analytics

> Turn customer data into CEO-level intelligence.

1. [x] Build retention and churn metrics (`CustomerAnalyticsService.summary()` — total/new/repeat/at-risk/churned)
2. [x] Build customer ranking and product affinity (top customers by spend, top products by distinct customer reach)
3. [x] Integrate customer insights into AI chat tools (`get_customer_analytics` tool in `TOOL_SCHEMAS` + `_compose_answer` keyword routing)
4. [x] Add customer analytics to CEO briefings and Telegram alerts (daily briefing now appends retention block in online_pos mode)
5. [x] Add customer analytics to vendor dashboard (`CustomerAnalyticsPage.tsx` with period selector, KPI tiles, lifecycle funnel, consent panel, affinity table)

---

## 7. Migration Path for Existing Clients

### Village clients (current installs)
- **No change.** They continue with `APP_MODE=local_pos` and local PostgreSQL.
- Optional sync to cloud continues to work as before.

### New city clients
- Deploy with `APP_MODE=online_pos` pointing at Supabase.
- No local database install needed.
- Provision organization, branch, and users through the vendor admin panel.
- Customer retention module enabled from day one.

### Existing village clients upgrading to city (future)
- Migrate local data to Supabase (one-time dump and import).
- Switch `APP_MODE` from `local_pos` to `online_pos`.
- Disable sync outbox.
- Enable customer retention module.
- This is a supported but non-trivial migration — needs a documented runbook.

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| City POS downtime if Supabase is down | Offline fallback queue (Phase B) |
| Multi-tenant data leaks | Organization_id scoping + Supabase RLS |
| SMS/WhatsApp delivery costs | Per-message pricing passed to pharmacy client |
| Customer data privacy (NCA/DPA compliance) | Data stays within tenant scope, consent at registration |
| Increased Supabase usage costs | Plan sizing per client count, monitor usage |
| Complexity of two deployment modes in one codebase | Clean separation via APP_MODE, feature flags per mode |

---

## 9. Open Questions

1. **SMS/WhatsApp provider:** Which provider works best in Ghana? (Africa's Talking, Twilio, Hubtel, or WhatsApp Business API directly?)
2. **Customer consent:** What consent flow is required under Ghana data protection law for health follow-up messages?
3. **Offline window:** How long should city pharmacies operate offline before forcing a reconnect? (Recommendation: 4 hours)
4. **Pricing model:** Monthly subscription per branch? Per device? Flat rate per pharmacy?
5. **Supabase plan:** Which Supabase tier supports the expected city client volume?

---

## 10. Success Criteria

- [ ] A city pharmacy can run full POS against Supabase with no local database
- [ ] When internet drops, the POS queues sales and recovers automatically
- [ ] Customers can be registered and linked to purchases
- [ ] Digital receipts are delivered via SMS/WhatsApp after purchase
- [ ] Health follow-up messages are sent automatically and responses tracked
- [ ] AI chat answers questions with zero sync delay for online clients
- [ ] Village pharmacies continue to work exactly as they do today
- [ ] No data leaks between tenants in the shared cloud database
