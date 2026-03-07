# mml_roq_freight — ROQ ↔ Freight Bridge

**Module:** `mml_roq_freight`
**Application:** No (`application = False`)
**`auto_install`:** Yes — activates automatically when both `mml_roq_forecast` and `mml_freight` are installed
**Depends on:** `mml_roq_forecast`, `mml_freight`

A thin bridge module. Contains only event subscriptions and `_inherit` field additions. All business logic lives in the parent modules.

---

## What it does

`mml_roq_forecast` and `mml_freight` are independent modules with no direct Python imports between them. This bridge wires them together via the `mml_base` event bus.

| Event emitted by | Handler in bridge | Action |
|---|---|---|
| `roq.shipment_group.confirmed` (from `mml_roq_forecast`) | `_on_shipment_group_confirmed` | Creates a `freight.tender` via FreightService, linking all POs in the shipment group |
| `freight.booking.confirmed` (from `mml_freight`) | `_on_freight_booking_confirmed` | Triggers ROQ lead-time stats update via ROQService so actual transit times feed back into future safety-stock calculations |

---

## `auto_install` behaviour

This module is never manually installed. Odoo activates it as soon as it detects that both `mml_roq_forecast` and `mml_freight` are present in the database. It deactivates (and its subscriptions are removed) if either parent is uninstalled.

```bash
# Force-install explicitly (only if auto_install has not already triggered):
odoo-bin -d <db> -i mml_roq_freight --stop-after-init
```

---

## Module structure

```
mml_roq_freight/
├── __manifest__.py
├── __init__.py
├── hooks.py          ← post_init_hook: registers event subscriptions
├── models/
│   └── roq_freight_bridge.py  ← _on_shipment_group_confirmed, _on_freight_booking_confirmed
├── security/
│   └── ir.model.access.csv
└── tests/
    └── (Odoo integration tests)
```

---

## Design rule

Bridges must stay thin:
- No new `_name` models — only `_inherit` extensions.
- No business logic — delegate to `FreightService` and `ROQService` via the service locator.
- No direct Python imports of the parent modules — use `self.env['mml.registry'].service(...)`.

---

## Related

- [`mml_roq_forecast`](../mml.roq.model/README.md) — emits the shipment group event
- [`mml_freight`](../mml.fowarder.intergration/README.md) — receives the freight tender
- [`mml_freight_3pl`](./mml_freight_3pl/README.md) — the other bridge (Freight ↔ 3PL)
- [`mml_base`](../mml_base/README.md) — event bus infrastructure
