# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read the root `mml.odoo.apps/CLAUDE.md` first — it defines platform architecture, test strategy, and cross-module conventions.

---

## Module Purpose

`mml_freight_3pl` is a **schema bridge** (`auto_install = True`, `application = False`) that wires `mml_freight` and `stock_3pl_core` together when both are installed. It has no UI, no views, and adds no standalone menu.

**Single responsibility:** When a `freight.booking` is confirmed, queue one `3pl.inward_order` message per linked purchase order and emit a billable `3pl.inbound.queued` event.

---

## Architecture

```
freight.booking confirmed
        │
        ▼ mml.event (event bus in mml_base)
        │
        ▼ mml.event.subscription (registered by post_init_hook)
        │
        ▼ mml.3pl.bridge._on_freight_booking_confirmed()
        │
        ├── mml.registry.service('3pl')       ← NullService if stock_3pl_core not active
        │       └── svc.queue_inward_order(po.id) → 3pl.message
        │
        └── mml.event.emit('3pl.inbound.queued') ← billable meter event
```

Key design points:
- **No direct import of `stock_3pl_mainfreight`** — the bridge uses `mml.registry` service locator, so it degrades gracefully if only `stock_3pl_core` is installed without an implementation.
- Billing event (`3pl.inbound.queued`) is only emitted when `queue_inward_order` returns a non-`None` message ID.
- The subscription is registered/deregistered entirely via `post_init_hook` / `uninstall_hook` — no data XML required.

---

## Files

| File | Purpose |
|------|---------|
| `__manifest__.py` | `auto_install`, depends on `mml_freight` + `stock_3pl_core` |
| `hooks.py` | Registers/deregisters `mml.event.subscription` on install/uninstall |
| `models/mml_3pl_bridge.py` | `mml.3pl.bridge` AbstractModel — event handler |
| `tests/test_bridge.py` | Pure-Python structural tests + `@pytest.mark.odoo_integration` suite |

---

## Running Tests

```bash
# Pure-Python (no Odoo needed)
pytest mml_freight_3pl/ -q

# Odoo integration (requires live DB with mml_freight + stock_3pl_core installed)
python odoo-bin --test-enable -u mml_freight_3pl -d <db> --stop-after-init
```

---

## Extension Guidelines

- **Adding a new trigger event:** Add a handler method on `mml.3pl.bridge` and register a new subscription in `post_init_hook` / deregister in `uninstall_hook`. One subscription per event type.
- **Adding a new billable unit:** Emit via `mml.event.emit()` with `billable_unit=` matching the unit defined in `mml_base` billing config.
- **No ORM fields should be added here** — this module owns no database tables. Schema additions belong in `mml_freight` or `stock_3pl_core`.

## Available Commands

- `/plan` — before adding new bridge events or wiring
- `/tdd` — structural tests first; integration tests require live Odoo
