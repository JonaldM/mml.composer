# Standalone App Structure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert all user-facing MML modules into standalone Odoo apps with independent home screen tiles and scoped Configuration submenus.

**Architecture:** Pure manifest and XML menu changes only — no new models, views, or Python. Each module gets `application = True` and a true top-level root menuitem (no `parent=`). `stock_3pl_core` menus are cleared; connector/queue config surfaces in the Mainfreight app's Configuration submenu.

**Design doc:** `docs/plans/2026-03-02-standalone-app-structure-design.md`

**Tech Stack:** Odoo 19 XML menus, `__manifest__.py`

---

## Task 1: `mml_edi` — Remove broken `web_icon` reference

**Files:**
- Modify: `briscoes.edi/mml.edi/views/menuitems.xml`

**Context:**
`mml_edi` is already a correctly structured standalone app (`application = True`, standalone root, dashboard, Configuration submenu). The only problem is `web_icon="mml_edi,static/description/icon.png"` on the root menuitem — the file doesn't exist, causing an Odoo startup warning. Remove the attribute. No icon this sprint.

**Step 1: Edit `menuitems.xml` — remove `web_icon`**

Current line 9–12:
```xml
<menuitem id="menu_edi_root"
          name="EDI"
          sequence="100"
          web_icon="mml_edi,static/description/icon.png"/>
```

Replace with:
```xml
<menuitem id="menu_edi_root"
          name="EDI"
          sequence="100"/>
```

**Step 2: Verify**

Upgrade the module and confirm no `web_icon` warning in the Odoo log:
```bash
python odoo-bin -u mml_edi -d <your_db> --stop-after-init --log-level=warn
```
Expected: no `StaticFileNotFound` or `web_icon` warning for `mml_edi`.

**Step 3: Commit**
```bash
git add briscoes.edi/mml.edi/views/menuitems.xml
git commit -m "fix(mml_edi): remove broken web_icon reference (icon deferred)"
```

---

## Task 2: `mml_roq_forecast` — Standalone app

**Files:**
- Modify: `roq.model/mml_roq_forecast/__manifest__.py`
- Modify: `roq.model/mml_roq_forecast/views/menus.xml`

**Context:**
`mml_roq_forecast` lacks `application = True` and its root menu is nested under a shared `menu_mml_operations_root` parent instead of being a true top-level. Fix both.

**Step 1: Add `application = True` to manifest**

In `__manifest__.py`, the current closing section is:
```python
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

Replace with:
```python
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
```

**Step 2: Promote `menu_roq_root` to true top-level**

Current `views/menus.xml` (full file):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_mml_operations_root"
              name="MML Operations"
              sequence="10"/>

    <menuitem id="menu_roq_root"
              name="ROQ Forecast"
              parent="menu_mml_operations_root"
              sequence="10"/>

    <menuitem id="menu_roq_order_dashboard"
              name="Order Dashboard"
              parent="menu_roq_root"
              action="action_roq_order_dashboard"
              sequence="5"/>

    <menuitem id="menu_roq_runs"
              name="ROQ Runs"
              parent="menu_roq_root"
              action="action_roq_forecast_run"
              sequence="10"/>

    <menuitem id="menu_roq_shipment_groups"
              name="Shipment Groups"
              parent="menu_roq_root"
              action="action_roq_shipment_group"
              sequence="20"/>

    <menuitem id="menu_roq_config"
              name="Configuration"
              parent="menu_roq_root"
              sequence="90"/>

    <menuitem id="menu_roq_freight_ports"
              name="Freight Ports"
              parent="menu_roq_config"
              action="action_roq_port"
              sequence="10"/>
</odoo>
```

Replace with (remove `menu_mml_operations_root` entirely; remove `parent=` from `menu_roq_root`):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_roq_root"
              name="ROQ Forecast"
              sequence="10"/>

    <menuitem id="menu_roq_order_dashboard"
              name="Order Dashboard"
              parent="menu_roq_root"
              action="action_roq_order_dashboard"
              sequence="5"/>

    <menuitem id="menu_roq_runs"
              name="ROQ Runs"
              parent="menu_roq_root"
              action="action_roq_forecast_run"
              sequence="10"/>

    <menuitem id="menu_roq_shipment_groups"
              name="Shipment Groups"
              parent="menu_roq_root"
              action="action_roq_shipment_group"
              sequence="20"/>

    <menuitem id="menu_roq_config"
              name="Configuration"
              parent="menu_roq_root"
              sequence="90"/>

    <menuitem id="menu_roq_freight_ports"
              name="Freight Ports"
              parent="menu_roq_config"
              action="action_roq_port"
              sequence="10"/>
</odoo>
```

**Step 3: Verify**

```bash
python odoo-bin -u mml_roq_forecast -d <your_db> --stop-after-init --log-level=warn
```
Expected: module upgrades cleanly. In Odoo UI: "ROQ Forecast" appears as a top-level tile on the home screen (Apps switcher), not nested under "MML Operations".

**Step 4: Commit**
```bash
git add roq.model/mml_roq_forecast/__manifest__.py roq.model/mml_roq_forecast/views/menus.xml
git commit -m "feat(mml_roq_forecast): standalone Odoo app with top-level menu"
```

---

## Task 3: `mml_freight` — Standalone app with Configuration submenu

**Files:**
- Modify: `fowarder.intergration/addons/mml_freight/__manifest__.py`
- Modify: `fowarder.intergration/addons/mml_freight/views/menu.xml`

**Context:**
`mml_freight` has `application = False` and its root menu is nested under `stock.menu_stock_root` (Inventory). It needs to become a standalone app with its own tile. Active Shipments kanban becomes the landing page. Carriers and Contracts move into a Configuration submenu (reference data that ops users rarely touch).

**Step 1: Set `application = True` in manifest**

In `__manifest__.py`, current closing section:
```python
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

Replace with:
```python
    'installable': True,
    'auto_install': False,
    'application': True,
}
```

**Step 2: Restructure `views/menu.xml`**

Current file:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_freight_root" name="Freight" sequence="50"
              parent="stock.menu_stock_root" groups="stock.group_stock_user"/>

    <!-- Active shipments pipeline — kanban first, most-used -->
    <menuitem id="menu_freight_shipments" name="Active Shipments"
              parent="menu_freight_root" action="action_freight_booking_active" sequence="5"/>

    <!-- Quotations needing a decision — surfaced prominently -->
    <menuitem id="menu_pending_quotations" name="Pending Quotations"
              parent="menu_freight_root" action="action_pending_quotations" sequence="10"/>

    <menuitem id="menu_freight_tenders" name="All Tenders"
              parent="menu_freight_root" action="action_freight_tender" sequence="20"/>

    <menuitem id="menu_freight_bookings" name="All Bookings"
              parent="menu_freight_root" action="action_freight_booking" sequence="30"/>

    <menuitem id="menu_freight_carriers" name="Freight Carriers"
              parent="menu_freight_root" action="action_freight_carrier" sequence="40"/>

    <menuitem id="menu_freight_contracts" name="Carrier Contracts"
              parent="menu_freight_root" action="action_freight_carrier_contract" sequence="45"
              groups="stock.group_stock_manager"/>
</odoo>
```

Replace with:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Top-level app root — standalone tile, landing on Active Shipments kanban -->
    <menuitem id="menu_freight_root"
              name="Freight"
              sequence="50"
              action="action_freight_booking_active"
              groups="stock.group_stock_user"/>

    <!-- ── Operations ─────────────────────────────────────────────── -->
    <menuitem id="menu_freight_shipments"
              name="Active Shipments"
              parent="menu_freight_root"
              action="action_freight_booking_active"
              sequence="5"/>

    <menuitem id="menu_pending_quotations"
              name="Pending Quotations"
              parent="menu_freight_root"
              action="action_pending_quotations"
              sequence="10"/>

    <menuitem id="menu_freight_tenders"
              name="All Tenders"
              parent="menu_freight_root"
              action="action_freight_tender"
              sequence="20"/>

    <menuitem id="menu_freight_bookings"
              name="All Bookings"
              parent="menu_freight_root"
              action="action_freight_booking"
              sequence="30"/>

    <!-- ── Configuration ──────────────────────────────────────────── -->
    <menuitem id="menu_freight_config"
              name="Configuration"
              parent="menu_freight_root"
              sequence="90"
              groups="stock.group_stock_manager"/>

    <menuitem id="menu_freight_carriers"
              name="Freight Carriers"
              parent="menu_freight_config"
              action="action_freight_carrier"
              sequence="10"/>

    <menuitem id="menu_freight_contracts"
              name="Carrier Contracts"
              parent="menu_freight_config"
              action="action_freight_carrier_contract"
              sequence="20"
              groups="stock.group_stock_manager"/>
</odoo>
```

**Step 3: Verify**

```bash
python odoo-bin -u mml_freight -d <your_db> --stop-after-init --log-level=warn
```
Expected: module upgrades cleanly. In Odoo UI: "Freight" appears as a top-level home screen tile. Opening it lands on Active Shipments kanban. "Configuration" submenu visible to managers only, containing Carriers and Contracts.

**Step 4: Commit**
```bash
git add fowarder.intergration/addons/mml_freight/__manifest__.py fowarder.intergration/addons/mml_freight/views/menu.xml
git commit -m "feat(mml_freight): standalone Odoo app with Configuration submenu"
```

---

## Task 4: `stock_3pl_core` — Clear all menus

**Files:**
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_core/views/menu.xml`

**Context:**
`stock_3pl_core` is the forwarder-agnostic platform layer (`application = False`). Its connector/queue menus are being absorbed by `stock_3pl_mainfreight`'s Configuration submenu (Task 5). Clear this file now so Task 5 can reference the action IDs without menu conflicts.

**Important:** Clearing the menuitems removes the UI only. All models (`3pl.connector`, `3pl.message`), actions, and data remain untouched. The actions (`action_3pl_connector`, `action_3pl_message_all`, `action_3pl_message_dead`) are defined elsewhere in `stock_3pl_core` views — this task only removes the menu entries that pointed to them.

**Step 1: Clear all menuitems from `menu.xml`**

Current file:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <menuitem id="menu_3pl_root"
              name="3PL Integration"
              parent="stock.menu_stock_config_settings"
              sequence="100"/>

    <menuitem id="menu_3pl_connectors"
              name="Connectors"
              parent="menu_3pl_root"
              action="action_3pl_connector"
              sequence="10"/>

    <menuitem id="menu_3pl_messages"
              name="Message Queue"
              parent="menu_3pl_root"
              action="action_3pl_message_all"
              sequence="20"/>

    <menuitem id="menu_3pl_dead_letters"
              name="Dead Letters"
              parent="menu_3pl_root"
              action="action_3pl_message_dead"
              sequence="30"/>

</odoo>
```

Replace with (empty — menus now owned by adapter modules):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Menus for 3pl.connector, 3pl.message, and dead letters are defined
         by each adapter module (e.g. stock_3pl_mainfreight) in their own
         Configuration submenu. This keeps stock_3pl_core invisible as a
         platform library. -->
</odoo>
```

**Step 2: Verify**

```bash
python odoo-bin -u stock_3pl_core -d <your_db> --stop-after-init --log-level=warn
```
Expected: module upgrades cleanly. The "3PL Integration" item no longer appears under Inventory > Configuration. No errors — actions still exist, just no menu items pointing to them from core.

**Step 3: Commit**
```bash
git add mainfreight.3pl.intergration/addons/stock_3pl_core/views/menu.xml
git commit -m "refactor(stock_3pl_core): clear menus — config surfaces in adapter apps"
```

---

## Task 5: `stock_3pl_mainfreight` — Standalone app, absorb core menus

**Files:**
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/__manifest__.py`
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/views/menu_mf.xml`

**Context:**
`stock_3pl_mainfreight` has `application` missing from manifest (defaults to False). It also has a dual-root problem: `menu_3pl_ops_root` (correct standalone root) plus `menu_mf_root` (incorrectly nested under `stock_3pl_core.menu_3pl_root`). Fix both. Add a Configuration submenu that absorbs the connector/queue items cleared from `stock_3pl_core` in Task 4, and move Cross-Border Held in there too.

**Step 1: Add `application = True` to manifest**

In `__manifest__.py`, current closing section:
```python
    'installable': True,
    'auto_install': False,
}
```

Replace with:
```python
    'installable': True,
    'auto_install': False,
    'application': True,
}
```

**Step 2: Restructure `views/menu_mf.xml`**

Current file:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ── Root: 3PL Operations ─────────────────────────────────── -->
    <menuitem id="menu_3pl_ops_root"
              name="3PL Operations"
              sequence="52"/>

    <menuitem id="menu_mf_dashboard"
              name="Dashboard"
              parent="menu_3pl_ops_root"
              action="action_mf_kpi_dashboard"
              sequence="10"/>

    <menuitem id="menu_mf_pipeline"
              name="Order Pipeline"
              parent="menu_3pl_ops_root"
              action="action_mf_order_pipeline"
              sequence="20"/>

    <menuitem id="menu_mf_exceptions"
              name="Exception Queue"
              parent="menu_3pl_ops_root"
              action="action_mf_exceptions"
              sequence="30"/>

    <menuitem id="menu_mf_discrepancy"
              name="Inventory Discrepancy"
              parent="menu_3pl_ops_root"
              action="action_mf_discrepancy"
              sequence="40"/>

    <!-- ── Mainfreight sub-menu (config + cross-border) ─────────── -->
    <menuitem id="menu_mf_root"
              name="Mainfreight"
              parent="stock_3pl_core.menu_3pl_root"
              sequence="50"/>

    <menuitem id="menu_mf_cross_border"
              name="Cross-Border Held"
              parent="menu_mf_root"
              action="action_mf_cross_border_held"
              sequence="20"/>
</odoo>
```

Replace with (remove nested `menu_mf_root`; add Configuration submenu with connector/queue/cross-border):
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ── Root: 3PL Operations (standalone app tile) ────────────── -->
    <menuitem id="menu_3pl_ops_root"
              name="3PL Operations"
              sequence="52"/>

    <!-- ── Operations ─────────────────────────────────────────────── -->
    <menuitem id="menu_mf_dashboard"
              name="Dashboard"
              parent="menu_3pl_ops_root"
              action="action_mf_kpi_dashboard"
              sequence="10"/>

    <menuitem id="menu_mf_pipeline"
              name="Order Pipeline"
              parent="menu_3pl_ops_root"
              action="action_mf_order_pipeline"
              sequence="20"/>

    <menuitem id="menu_mf_exceptions"
              name="Exception Queue"
              parent="menu_3pl_ops_root"
              action="action_mf_exceptions"
              sequence="30"/>

    <menuitem id="menu_mf_discrepancy"
              name="Inventory Discrepancy"
              parent="menu_3pl_ops_root"
              action="action_mf_discrepancy"
              sequence="40"/>

    <!-- ── Configuration (managers only) ─────────────────────────── -->
    <menuitem id="menu_3pl_config"
              name="Configuration"
              parent="menu_3pl_ops_root"
              sequence="90"
              groups="stock.group_stock_manager"/>

    <menuitem id="menu_3pl_connectors"
              name="Connectors"
              parent="menu_3pl_config"
              action="stock_3pl_core.action_3pl_connector"
              sequence="10"/>

    <menuitem id="menu_3pl_messages"
              name="Message Queue"
              parent="menu_3pl_config"
              action="stock_3pl_core.action_3pl_message_all"
              sequence="20"/>

    <menuitem id="menu_3pl_dead_letters"
              name="Dead Letters"
              parent="menu_3pl_config"
              action="stock_3pl_core.action_3pl_message_dead"
              sequence="30"/>

    <menuitem id="menu_mf_cross_border"
              name="Cross-Border Held"
              parent="menu_3pl_config"
              action="action_mf_cross_border_held"
              sequence="40"/>
</odoo>
```

**Note on action references:** The actions `action_3pl_connector`, `action_3pl_message_all`, `action_3pl_message_dead` are defined in `stock_3pl_core`. When referencing them from another module, prefix with the module name: `stock_3pl_core.action_3pl_connector`. Verify these IDs exist in `stock_3pl_core/views/` before running the upgrade.

**Step 3: Verify action IDs exist in stock_3pl_core**

Before running the upgrade, confirm these action `id` values exist in `stock_3pl_core` view XML files:
```bash
grep -r "action_3pl_connector\|action_3pl_message_all\|action_3pl_message_dead" mainfreight.3pl.intergration/addons/stock_3pl_core/views/
```
Expected: each ID found in at least one `<record id="..." model="ir.actions.*">` definition.

**Step 4: Upgrade both modules together**

Both modules must be upgraded together since core's menus were removed in Task 4:
```bash
python odoo-bin -u stock_3pl_core,stock_3pl_mainfreight -d <your_db> --stop-after-init --log-level=warn
```
Expected: both upgrade cleanly. In Odoo UI: "3PL Operations" appears as a top-level home screen tile. Configuration submenu (managers only) contains Connectors, Message Queue, Dead Letters, Cross-Border Held.

**Step 5: Commit**
```bash
git add mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/__manifest__.py mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/views/menu_mf.xml
git commit -m "feat(stock_3pl_mainfreight): standalone app, absorb connector/queue menus from core"
```

---

## Final Verification

After all 5 tasks, run a full upgrade of all changed modules:
```bash
python odoo-bin -u mml_edi,mml_roq_forecast,mml_freight,stock_3pl_core,stock_3pl_mainfreight -d <your_db> --stop-after-init --log-level=warn
```

Check the Odoo home screen shows 4 MML tiles:
```
[ EDI ]   [ ROQ Forecast ]   [ Freight ]   [ 3PL Operations ]
```

Each tile opens to:
- **EDI** → Order review dashboard
- **ROQ Forecast** → Order dashboard
- **Freight** → Active Shipments kanban
- **3PL Operations** → KPI dashboard

Managers see a **Configuration** submenu in each app. Non-manager users do not.
