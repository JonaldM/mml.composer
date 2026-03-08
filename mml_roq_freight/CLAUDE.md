# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read the root `mml.odoo.apps/CLAUDE.md` first — it defines project-wide conventions, test infrastructure, and the platform architecture this module plugs into.

---

## Module Role

`mml_roq_freight` is a **schema bridge** between `mml_roq_forecast` and `mml_freight`. It is `auto_install = True` and `application = False` — it activates automatically when both parent modules are installed, adds no UI, and must add no business logic beyond wiring.

**What it owns:**
- Two cross-FK fields (one on each side of the bridge): `roq.shipment.group.freight_tender_id` and `freight.tender.shipment_group_id`
- One `AbstractModel` event handler (`mml.roq.freight.bridge`) that calls into `mml.registry` — never calls parent module code directly
- Two `mml.event.subscription` registrations (installed via `post_init_hook`, cleaned up via `uninstall_hook`)

**Event flow:**
1. `roq.shipment_group.confirmed` → `_on_shipment_group_confirmed` → calls `FreightService.create_tender()` via registry, writes `freight_tender_id` back on the shipment group
2. `freight.booking.confirmed` → `_on_freight_booking_confirmed` → calls `ROQService.on_freight_booking_confirmed()` via registry (lead-time feedback)

---

## Key Constraints

- **No direct imports from `mml_roq_forecast` or `mml_freight` Python code.** All cross-module calls go through `self.env['mml.registry'].service('freight')` or `.service('roq')`.
- Fields added via `_inherit` use `ondelete='set null'` and `readonly=True` — they are owned by this bridge, not by the parent modules.
- `ir.model.access.csv` is intentionally empty — no new models with ACL requirements are introduced (the `AbstractModel` needs none).
- Errors in bridge handlers log a warning and post a chatter note on the shipment group; they do not raise — this prevents a freight service failure from blocking ROQ confirmation.

---

## Tests

```bash
# Pure-Python structural tests (no Odoo needed)
pytest mml_roq_freight/ -q

# Odoo integration tests (require live DB)
python odoo-bin --test-enable -u mml_roq_freight -d <db> --stop-after-init
```

Pure-Python tests (`test_bridge.py`) verify manifest shape and hook presence. Odoo integration tests (`@pytest.mark.odoo_integration`) verify field existence on both models and that subscriptions are registered with correct event types.

---

## Adding New Bridge Events

1. Add a handler method to `models/bridge_service.py` (same pattern as existing handlers).
2. Register the subscription in `hooks.py` `post_init_hook` — the `deregister_module` call in `uninstall_hook` covers all subscriptions automatically.
3. Add a structural test asserting the new event type appears in the registered subscriptions.

## Available Commands

- `/plan` — before adding new bridge events
- `/tdd` — write structural tests first; integration tests require live Odoo
