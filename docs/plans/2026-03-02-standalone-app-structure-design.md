# Standalone App Structure — Design

**Date:** 2026-03-02
**Status:** Approved
**Scope:** UI/manifest restructure — no model changes, no new views, no icons

---

## Goal

Each user-facing `mml_*` module becomes a standalone Odoo app with its own home screen tile,
independent install, and scoped Configuration submenu. Mirrors how Odoo's own apps (Sales,
Inventory, Accounting) work. Supports future SaaS distribution where each module is a
separately billable, independently installable product.

---

## What Changes

### Modules becoming standalone apps

| Module | App Name | Landing Page | Changes |
|---|---|---|---|
| `mml_edi` | EDI | Existing order review dashboard | Remove broken `web_icon` reference |
| `mml_roq_forecast` | ROQ Forecast | Existing order dashboard | `application: True`, promote root menu |
| `mml_freight` | Freight | Active Shipments kanban | `application: True`, standalone root, Configuration submenu |
| `stock_3pl_mainfreight` | Mainfreight 3PL | Existing KPI dashboard | `application: True`, absorb core menus |

### Modules unchanged (intentionally invisible)

| Module | Reason |
|---|---|
| `mml_base` | Platform library — no user-facing UI |
| `mml_roq_freight` | Bridge module — `auto_install`, no UI |
| `mml_freight_3pl` | Bridge module — `auto_install`, no UI |
| `stock_3pl_core` | Agnostic platform layer — menus cleared, config surfaced in adapter apps |

---

## Architecture Decisions

### Icons deferred
No `web_icon` attributes on any root menuitem this sprint. Odoo renders a default grey tile.
Add `web_icon` in a future branding sprint when real PNGs are ready. `mml_edi`'s existing
broken `web_icon` reference is removed.

### `stock_3pl_core` stays invisible
`stock_3pl_core` remains `application = False` with no menus. The connector/queue UI that
previously lived in `stock_3pl_core/views/menu.xml` moves to `stock_3pl_mainfreight`'s
Configuration submenu.

This is future-proof: models (`3pl.connector`, `3pl.message`) stay in `stock_3pl_core` and
remain forwarder-agnostic. A future adapter (e.g. `stock_3pl_fedex`) would have its own app
tile and its own Configuration submenu pointing to the same models. Same pattern as Odoo's
`delivery` + `delivery_dhl` relationship.

### `mml_freight` landing page
The existing Active Shipments kanban (`action_freight_booking_active`) is wired as the default
action on the `menu_freight_root` menuitem. No new views needed.

### `mml_freight` Configuration submenu
Carriers and Carrier Contracts move from the main nav into a Configuration submenu, consistent
with how Odoo's own apps treat reference data setup.

### `stock_3pl_mainfreight` dual-root resolved
Currently has two root menuitems: `menu_3pl_ops_root` (standalone) and `menu_mf_root` (nested
under `stock_3pl_core.menu_3pl_root`). The nested `menu_mf_root` is removed. `menu_3pl_ops_root`
becomes the sole root, absorbing the connector/queue config in a new Configuration submenu.

---

## File Changes (7 files, 0 new files)

| File | Change |
|---|---|
| `briscoes.edi/mml.edi/views/menuitems.xml` | Remove `web_icon` from `menu_edi_root` |
| `roq.model/mml_roq_forecast/__manifest__.py` | Add `'application': True` |
| `roq.model/mml_roq_forecast/views/menus.xml` | Remove `menu_mml_operations_root` def; remove `parent=` from `menu_roq_root` |
| `fowarder.intergration/addons/mml_freight/__manifest__.py` | `'application': False` → `True` |
| `fowarder.intergration/addons/mml_freight/views/menu.xml` | Standalone root + landing action + Configuration submenu |
| `mainfreight.3pl.intergration/addons/stock_3pl_core/views/menu.xml` | Clear all menuitems |
| `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/__manifest__.py` | Add `'application': True` |
| `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/views/menu_mf.xml` | Remove nested root; add Configuration submenu with connector/queue items |

---

## Out of Scope

- No new views, models, or security changes
- No dashboard builds
- No icons or branding
- No changes to adapter modules (`mml_freight_dsv`, `mml_freight_demo`, etc.)
- No changes to bridge modules or `mml_base`

---

## Final Home Screen State

After this sprint, the Odoo home screen shows 4 MML app tiles:

```
[ EDI ]   [ ROQ Forecast ]   [ Freight ]   [ Mainfreight 3PL ]
```

Each with:
- Own top-level root menuitem
- Own dashboard / landing page
- Own Configuration submenu (manager-gated)
- `application = True` — independently installable
