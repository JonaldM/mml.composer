# mml_freight_3pl — Freight ↔ 3PL Bridge

**Module:** `mml_freight_3pl`
**Application:** No (`application = False`)
**`auto_install`:** Yes — activates automatically when both `mml_freight` and `stock_3pl_core` are installed
**Depends on:** `mml_freight`, `stock_3pl_core`

A thin bridge module. Contains only event subscriptions and `_inherit` field additions. All business logic lives in the parent modules.

---

## What it does

`mml_freight` and `stock_3pl_core` are independent modules with no direct Python imports between them. This bridge wires them together via the `mml_base` event bus.

| Event emitted by | Handler in bridge | Action |
|---|---|---|
| `freight.booking.confirmed` (from `mml_freight`) | `_on_freight_booking_confirmed` | Queues one `3pl.message` (document_type=`inward_order`) per linked PO via `TPLService.queue_inward_order()` |

---

## Why one inward order per PO (not one per booking)

Mainfreight's system matches inward orders to Odoo purchase receipts at the PO level — one receipt per PO. A consolidated booking may cover multiple POs (e.g. a ROQ shipment group with three supplier POs on the same container). The bridge loops over `booking.po_ids` and queues a separate inward order for each, ensuring Mainfreight can match each delivery to the correct receipt in Odoo.

---

## `auto_install` behaviour

Odoo activates this module automatically when both `mml_freight` and `stock_3pl_core` are present. It deactivates and its subscriptions are removed if either parent is uninstalled.

```bash
# Force-install explicitly (only if auto_install has not already triggered):
odoo-bin -d <db> -i mml_freight_3pl --stop-after-init
```

---

## Module structure

```
mml_freight_3pl/
├── __manifest__.py
├── __init__.py
├── hooks.py          ← post_init_hook: registers event subscriptions
├── models/
│   └── freight_3pl_bridge.py  ← _on_freight_booking_confirmed
├── tests/
│   └── (Odoo integration tests)
```

---

## Design rule

Bridges must stay thin:
- No new `_name` models — only `_inherit` extensions.
- No business logic — delegate to `TPLService` via the service locator.
- No direct Python imports of parent modules — use `self.env['mml.registry'].service('3pl')`.

---

## Related

- [`mml_freight`](../mml.fowarder.intergration/README.md) — emits the booking confirmed event
- [`stock_3pl_core`](../mml.3pl.intergration/README.md) — provides TPLService and the message queue
- [`mml_roq_freight`](./mml_roq_freight/README.md) — the other bridge (ROQ ↔ Freight)
- [`mml_base`](../mml_base/README.md) — event bus infrastructure
