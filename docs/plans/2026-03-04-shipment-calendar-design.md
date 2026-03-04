# Shipment Planning Calendar — Design

**Date:** 2026-03-04
**Module:** `mml_roq_forecast` (extended in-place, no new module)
**Status:** Approved

---

## Problem

Procurement planners need a visual timeline of all incoming shipments — planned and confirmed — to ensure adequate spacing, spot coverage gaps, and act on consolidation opportunities. Currently, shipment groups are managed via kanban and list views with no temporal context.

---

## Goals

1. Show planned and confirmed shipments on a calendar grouped by delivery date to warehouse
2. Allow drag-and-drop rescheduling of planned (draft/confirmed) shipments
3. Surface consolidation opportunities when shipments are rescheduled significantly
4. Enable raising draft POs directly from the calendar
5. Show live freight status (ETA, last tracking event) when `mml_freight` is installed
6. Degrade gracefully when `mml_freight` is not installed

---

## Non-Goals

- No auto-creation of freight tenders from this view (too early — 8+ months horizon)
- No custom OWL calendar component (standard Odoo calendar view only)
- No per-SKU visibility on the calendar (SKUs are contained within groups, not shown)

---

## Architecture

### Module placement

All changes land in `mml_roq_forecast`. No new module.

### Primary calendar model

**`roq.shipment.group`** — one calendar event per shipment group.

- `date_stop` → `target_delivery_date` (ETA at warehouse — what the planner cares about)
- `date_start` → `target_ship_date` (ETD — start of the transit window)
- Events span their transit window on the calendar

### Freight status integration

New computed fields on `roq.shipment.group`:

```python
freight_eta: Datetime        # from freight.booking via mml.registry.service('freight')
freight_status: Char         # latest tracking event status
freight_last_update: Datetime
```

Populated via `mml.registry.service('freight')`. Returns empty if `mml_freight` not installed — no conditional XML needed. Calendar card uses `invisible="not freight_eta"`.

### Warehouse receiving capacity

New fields on `stock.warehouse` (in existing `stock_warehouse_ext.py`):

```python
roq_weekly_capacity_cbm: Float    # max CBM arriving per week
roq_weekly_capacity_teu: Float    # max TEU arriving per week (1 TEU = 1×20GP; 40GP/40HQ = 2 TEU)
roq_capacity_unit: Selection([('cbm', 'CBM'), ('teu', 'TEU')])
```

Container → TEU mapping: `20GP = 1.0`, `40GP = 2.0`, `40HQ = 2.0`, `LCL = 0` (weight-based, exempt).

### Forward plan context (coverage map)

Forward plan lines (`roq.forward.plan.line`) are **not** rendered on the calendar. Instead, a standalone **Coverage Map** view is accessible via a button in the calendar control panel. It is implemented as a list view on a new `roq.warehouse.week.load` computed model (or aggregated via a pivot view — see implementation plan).

**Primary axis:** warehouse receiving load over time.

- Rows: warehouses
- Columns: rolling 8-week window
- Each cell: scheduled CBM (or TEU) arriving that week vs. warehouse weekly capacity
- Cell colour:
  - **Green** — < 70% of capacity
  - **Amber** — 70–90% of capacity
  - **Red** — > 90% of capacity

This is the primary saturation signal. The planner sees Hamilton week 12 is red → drags a shipment earlier or later → cell recalculates → consolidation wizard fires if the move lands near a same-supplier group.

This is a read-only computed summary. Not draggable.

---

## Calendar Layout

### Display modes

- **Month view** (default) — procurement planning horizon
- **Week view** — near-term operational detail

### Event colour by state

| State | Colour |
|---|---|
| `draft` | Grey |
| `confirmed` | Blue |
| `tendered` | Amber |
| `booked` | Green |
| `delivered` | Muted green (read-only) |

### Calendar card content

- Shipment group name (SG-2026-0042)
- Destination warehouse abbreviations (HLZ · CHC or AKL · AUS for multi-warehouse groups)
- Supplier(s): first supplier name + overflow count if consolidated ("Supplier A +2")
- Container type + fill % (40HQ · 87%)
- Freight ETA + last status if `mml_freight` installed ("ETA 12 Mar · In Transit")
- OOS risk warning badge if any SKU in group has `oos_risk_flag = True`

### Drag behaviour

- **Draggable**: `draft`, `confirmed` states only
- **Locked**: `tendered`, `booked`, `delivered` — carrier data is live, do not allow UI override

### Search filters

Standard Odoo search bar. Filter by: warehouse, supplier, container type, state.

---

## Recalculation on Drag

Server method: `action_reschedule(new_delivery_date)` on `roq.shipment.group`.

### Step 1 — Date update

- Set `target_delivery_date` = dropped date
- Shift `target_ship_date` by same delta (preserve transit duration)

### Step 2 — OOS re-check (always)

- Call `push_pull.py` service for all SKUs in group
- Recalculate weeks-of-cover at new delivery date
- Update `oos_risk_flag` on affected `roq.shipment.group.line` records
- If any SKU now OOS risk → warning badge on calendar card

### Step 3 — Consolidation proximity check (shift > 5 days only)

- Query for other `draft`/`confirmed` shipment groups:
  - Same supplier(s) / FOB port
  - Within ±21 days of new `target_delivery_date`
- If found → return action opening lightweight wizard:
  > *"SG-2026-0041 (same supplier, 14 days away) could be consolidated. Consolidate now?"*
- **Yes** → runs `consolidation_engine.py`
- **No** → dismiss, keep both groups

### Step 4 — Audit trail

- `mail.message` posted on shipment group: old date → new date, user, push/pull delta in days

### Configuration parameters (`ir.config_parameter`)

| Key | Default | Purpose |
|---|---|---|
| `roq.calendar.reschedule_threshold_days` | `5` | Minimum shift to trigger consolidation check |
| `roq.calendar.consolidation_window_days` | `21` | Search window for nearby groups |

---

## Confirm from Calendar

### Popover buttons by state

**`draft` groups:**
- **"Raise Draft POs"** — calls `roq_raise_po_wizard` logic programmatically (no dialog). Creates one draft `purchase.order` per supplier, links via `po_ids`, transitions group `draft` → `confirmed`. Card turns blue.
- **"Open"** — navigates to full shipment group form

**`confirmed` groups:**
- **"View POs"** — opens linked POs list filtered to this group
- **"Open"** — navigates to full shipment group form

**`tendered`/`booked` groups (read-only popover):**
- Freight ETA, carrier name, last tracking event
- **"View Booking"** — link to `freight.booking` form (only if `mml_freight` installed)

---

## Files to Create / Modify

| File | Action |
|---|---|
| `mml_roq_forecast/views/roq_shipment_calendar_views.xml` | New — calendar view + coverage map view |
| `mml_roq_forecast/views/roq_reschedule_wizard_views.xml` | New — consolidation suggestion wizard |
| `mml_roq_forecast/views/menus.xml` | Add calendar menu entry |
| `mml_roq_forecast/models/roq_shipment_group.py` | Add freight computed fields; `action_reschedule()`; `write()` override |
| `mml_roq_forecast/models/roq_reschedule_wizard.py` | New — `roq.reschedule.wizard` TransientModel |
| `mml_roq_forecast/models/roq_warehouse_week_load.py` | New — `roq.warehouse.week.load` computed model for coverage map |
| `mml_roq_forecast/models/stock_warehouse_ext.py` | Add `roq_weekly_capacity_cbm`, `roq_weekly_capacity_teu`, `roq_capacity_unit` |
| `mml_roq_forecast/__manifest__.py` | Add new files to `data` list |

---

## Degradation Matrix

| Scenario | Behaviour |
|---|---|
| `mml_freight` not installed | `freight_eta`, `freight_status` return empty. Calendar card omits freight section. "View Booking" button hidden. |
| `mml_freight` installed, no booking linked | Fields empty (booking not yet created — normal for `draft`/`confirmed` groups) |
| `mml_freight` installed, booking exists | Full ETA + status shown on card and in popover |

---

## Out of Scope (Future)

- Gantt / resource view (Odoo Enterprise feature — revisit if we take Enterprise licence)
- Per-SKU timeline drilldown
- Freight tender creation from calendar
- Multi-warehouse split view
