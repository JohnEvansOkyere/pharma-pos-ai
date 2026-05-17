# Design System — Pharma POS AI

Reference for all UI decisions. Update this file whenever a design rule changes.

---

## 1. Typography

| Token | Value | Notes |
|---|---|---|
| Base font size | `13px` (html root) | Down from 17px. Matches DO/Paystack density. |
| Font stack | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial` | System font stack, no Google Fonts dependency |
| Line height | `leading-normal` (1.5) | Down from `leading-relaxed` |
| Page title | `text-base font-semibold` | Not bold h1, not `text-2xl` |
| Section header | `text-sm font-semibold` | Inside cards |
| Card label | `text-xs font-medium text-gray-500` | Metric label above value |
| Card value | `text-lg font-bold` | KPI numbers |
| Sidebar nav | `text-xs font-medium` | 12px, compact |
| Footer / meta | `10px` | Version strings, timestamps |

---

## 2. Color Palette

### Sidebar
| Token | Value |
|---|---|
| Background | `#1e3050` (deep navy, always — not toggled by dark mode) |
| Logo text | `#ffffff` |
| Nav item default | `rgba(255,255,255,0.55)` |
| Nav item hover | `rgba(255,255,255,0.90)` |
| Nav item active bg | `rgba(255,255,255,0.12)` |
| Nav item active text | `#ffffff` |
| Icon default | `rgba(255,255,255,0.45)` |
| Divider | `rgba(255,255,255,0.07)` |

### Brand (primary)
Indigo scale — `primary-600: #4F46E5` is the main action color.

### Light mode surface
| Element | Color |
|---|---|
| Page background | `bg-gray-50` |
| Card | `bg-white` border `border-gray-200` |
| Header | `bg-white` border `border-gray-200` |

### Dark mode surface
| Element | Color |
|---|---|
| Page background | `bg-gray-900` |
| Card | `bg-gray-800` border `border-gray-700` |
| Header | `bg-gray-800` border `border-gray-700` |

> **Sidebar is always `#1e3050` in both modes.**

---

## 3. Layout

| Token | Value |
|---|---|
| Sidebar width | `w-52` (208px) — down from 256px |
| Header height | `h-12` (48px) — down from `h-16` (64px) |
| Page padding | `p-4` (16px) — down from `p-6` (24px) |
| Card padding | `p-4` — default for most cards |
| Section gap | `gap-4` — between cards and columns |
| Page section gap | `space-y-4` — between dashboard sections |

---

## 4. Sidebar Behaviour

- Sidebar background is **always** `#1e3050` — it does not change in dark mode.
- Dark mode only affects the **main content area** (page bg, cards, header).
- Sidebar can be collapsed via the chevron button; the hamburger in the header restores it.
- Nav items are role-filtered: `adminOnly`, `adminOrManager`, or visible to all.

---

## 5. Dashboard Layout

Sections in order (top → bottom):

1. **Page header** — title + date + period filter (7D / 30D / 90D)
2. **Period KPI cards** — 4 cards in a row (revenue, items sold, profit, avg basket)
3. **Today at a glance** — single inline strip: today's revenue, sales count, avg basket, inventory value
4. **Critical Alerts banner** — shown only when low stock or expiring products exist
5. **Sales Trend chart** — dual-axis line chart (revenue + transactions), height 240px
6. **Top Products chart** — horizontal bar chart, height 280px
7. **Two-column row** — Category Performance + Inventory Health
8. **Two-column row** — Expiring Soon (≤30d) + Low Stock Alerts
9. **Quick Actions** — 4 buttons row

### Anti-patterns removed
- Duplicate KPI rows showing the same metrics twice
- Hardcoded fake growth percentages as a separate display row
- `text-2xl` / `text-lg` section headings (too large at 13px base)

---

## 6. Component Sizing Reference

### EnhancedKPICard
- Container: `card p-4`
- Icon container: `p-2 rounded`
- Icon: `h-4 w-4`
- Label: `text-xs font-medium text-gray-500`
- Value: `text-lg font-bold`
- Subtitle: `text-xs text-gray-400`
- Growth badge: `text-xs` with `h-3 w-3` arrow icon

### Nav item (Sidebar)
- Container: `px-3 py-2 rounded text-xs font-medium`
- Icon: `h-3.5 w-3.5 mr-2.5`
- Spacing between items: `space-y-0.5`

---

## 7. Inspiration References

- **DigitalOcean console** — sidebar density, nav item size, typography scale
- **Paystack dashboard** — sidebar color treatment, compact header, stat strip pattern
- Both use system font stacks, ~13px base, compact 48px headers, and dark-navy sidebars that don't change with dark mode.

---

## 8. Change Log

| Date | Change | Reason |
|---|---|---|
| 2026-05-17 | Initial design system — sidebar, typography, layout, dashboard | First client demo; UI felt too big and boring |
