# MML Integration Platform — Architecture Design

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Cross-cutting refactor of all `mml_*` and `stock_3pl_*` modules

---

## Context & Motivation

The MML module suite currently has two hard dependency problems:

1. `mml_roq_forecast` → `mml_freight` (manifest + unguarded Python inheritance)
2. `mml_freight` → `stock_3pl_core` (manifest; Python already partially guarded)

The immediate need is phased rollout flexibility — install modules independently, connect them natively when co-installed. The longer-term need is SaaS distribution: these modules should be publishable independently and work across ERP platforms (Odoo first, SAP/SAGE later).

This design solves both with a single architecture: **a central integration platform built on an event bus, capability registry, and service locator, with a billing ledger as a first-class citizen.**

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  MML PLATFORM  (central SaaS — future)                          │
│  License mgmt · Event ledger · Billing · Multi-instance UI      │
└───────────────────────────┬──────────────────────────────────────┘
                            │  HTTPS (events out, grants in)
┌───────────────────────────▼──────────────────────────────────────┐
│  mml_base  (Odoo module — built now)                            │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Capability       │  │ Service Locator   │  │ Event Bus      │  │
│  │ Registry         │  │ (+ NullService)   │  │ (+ Ledger)     │  │
│  └─────────────────┘  └──────────────────┘  └────────────────┘  │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐                      │
│  │ Platform Client  │  │ License Cache     │                      │
│  │ (stub → API)     │  │ (mml.license)     │                      │
│  └─────────────────┘  └──────────────────┘                      │
└──────┬───────────┬──────────────┬───────────────┬───────────────┘
       │           │              │               │
  mml_roq     mml_freight   stock_3pl_core    mml_edi
       │           │
  mml_roq_freight  │          ← schema bridge (auto_install: True)
               mml_freight_3pl ← schema bridge (auto_install: True)
```

**Principle:** Every `mml_*` module depends on `mml_base` and standard Odoo. No `mml_*` module depends on another `mml_*` module directly. Schema bridges handle the unavoidable Odoo model inheritance requirements.

---

## Component 1: Capability Registry (`mml.capability`)

Each module declares what it provides on install and withdraws on uninstall via manifest hooks.

### Model fields
```
mml.capability
  name          Char    — e.g. 'freight.tender.create'
  module        Char    — e.g. 'mml_freight'
  company_id    Many2one res.company
  active        Boolean
```

### Registration (in each module's `post_init_hook`)
```python
env['mml.capability'].register([
    'freight.tender.create',
    'freight.booking.confirm',
    'freight.quote.request',
])
```

### Deregistration (in each module's `uninstall_hook`)
```python
env['mml.capability'].deregister_module('mml_freight')
```

### Query
```python
if self.env['mml.capability'].has('freight.tender.create'):
    # safe to call freight service
```

---

## Component 2: Service Locator (`mml.registry`)

Each module registers a service class that wraps its public API. Other modules retrieve services through the registry. If the target module is not installed, the registry returns a `NullService` instance — a silent no-op that returns `None` for all calls. Call sites never need to check installation state.

### Service registration (on module install)
```python
# mml_freight/hooks.py
from odoo.addons.mml_freight.services.freight_service import FreightService

def post_init_hook(env):
    env['mml.registry'].register('freight', FreightService)
```

### Service interface (example)
```python
# mml_freight/services/freight_service.py
class FreightService:
    def __init__(self, env):
        self.env = env

    def create_tender(self, shipment_group_vals: dict) -> int | None:
        """Create a freight.tender from a shipment group. Returns tender ID."""
        ...

    def get_booking_lead_time(self, booking_id: int) -> int | None:
        """Return actual transit days for a confirmed booking."""
        ...
```

### Call site (in mml_roq_forecast)
```python
svc = self.env['mml.registry'].service('freight')
tender_id = svc.create_tender({'origin': self.name, 'lines': [...]})
# tender_id is None if mml_freight not installed — no crash, no check needed
```

---

## Component 3: Event Bus + Ledger (`mml.event`)

Events are **persisted**, not fire-and-forget. The event record is simultaneously the integration signal, the audit trail, and the billing ledger entry.

### Model fields
```
mml.event
  company_id          Many2one  res.company       (required)
  instance_ref        Char      — identifies Odoo instance (from ir.config_parameter)
  event_type          Char      — e.g. 'freight.booking.confirmed'
  source_module       Char      — e.g. 'mml_freight'
  res_model           Char      — optional: related record model
  res_id              Integer   — optional: related record ID
  payload_json        Text      — arbitrary metadata (JSON string)
  quantity            Float     — units for billing (e.g. 5 order lines)
  billable_unit       Char      — e.g. 'edi_order_line', 'freight_booking'
  synced_to_platform  Boolean   — False until platform client confirms receipt
  timestamp           Datetime  — auto-set on create
```

### Emission (one line from any module)
```python
self.env['mml.event'].emit(
    'freight.booking.confirmed',
    quantity=1,
    billable_unit='freight_booking',
    res_model='freight.booking',
    res_id=self.id,
    payload={'booking_ref': self.name, 'carrier': self.carrier_id.name},
)
```

### Subscriptions (`mml.event.subscription`)
Registered on module install, removed on uninstall:
```python
env['mml.event.subscription'].register(
    event_type='roq.shipment_group.confirmed',
    handler_model='mml.freight.service',
    handler_method='on_shipment_group_confirmed',
    module='mml_roq_freight',  # bridge module that owns this subscription
)
```

The event bus dispatcher runs as part of the emit call (synchronous) and also via a cron (5-minute catchup for any missed dispatches).

### Billable event types (initial set)

| Event type | billable_unit | Notes |
|---|---|---|
| `edi.order.processed` | `edi_order` | Per inbound EDI PO |
| `edi.order_line.processed` | `edi_order_line` | Per line on inbound EDI PO |
| `edi.asn.sent` | `edi_asn` | Per despatch advice sent |
| `edi.invoice.sent` | `edi_invoice` | Per EDI invoice sent |
| `freight.tender.created` | `freight_tender` | Per tender request |
| `freight.booking.confirmed` | `freight_booking` | Per confirmed booking |
| `roq.forecast.run` | `roq_run` | Per full forecast execution |
| `roq.po.raised` | `roq_po_line` | Per PO line raised from ROQ |
| `3pl.despatch.sent` | `3pl_despatch` | Per outbound despatch order |
| `3pl.receipt.confirmed` | `3pl_receipt` | Per inbound receipt confirmed |

---

## Component 4: Platform Client (stub → real API)

The platform client is a single service class on `mml_base`. Today it is a no-op stub. When the central SaaS platform is built, the stub is replaced — zero changes to any other module.

```python
# mml_base/services/platform_client.py

class PlatformClientBase:
    """No-op stub. Replace with RemotePlatformClient when platform is live."""

    def sync_events(self, events) -> None:
        pass  # no-op

    def validate_license(self, license_key: str) -> dict:
        return {'valid': True, 'tier': 'internal', 'modules': ['*']}
```

A cron job on `mml_base` runs every 15 minutes, finds `mml.event` records where `synced_to_platform = False`, and calls `platform_client.sync_events(...)`.

---

## Component 5: License Model (`mml.license`)

Stores the locally-cached license grant. Validated against the platform periodically; used locally for capability gating at module install time and optionally at runtime.

```
mml.license
  org_ref           Char    — organisation identifier from platform
  license_key       Char    — secret key
  tier              Char    — 'internal' | 'starter' | 'growth' | 'enterprise'
  module_grants     Text    — JSON list of permitted module names
  floor_amount      Float   — monthly minimum (e.g. 1000.00)
  currency_id       Many2one
  seat_limit        Integer — 0 = unlimited
  valid_until       Date
  last_validated    Datetime
```

---

## Component 6: Schema Bridges

Two thin bridge modules handle Odoo model inheritance — unavoidable because `_inherit` requires the parent module to be installed. Bridges contain **schema only** (field declarations, view extensions). All logic goes through the service locator and event bus.

### `mml_roq_freight`
- `depends: ['mml_roq_forecast', 'mml_freight']`
- `auto_install: True`
- Adds `freight_tender_id` (Many2one `freight.tender`) to `roq.shipment.group`
- Extends `freight.tender` with `shipment_group_id` (Many2one `roq.shipment.group`)
- Registers event subscription: `roq.shipment_group.confirmed` → `FreightService.on_shipment_group_confirmed`
- Registers event subscription: `freight.booking.confirmed` → `ROQService.on_freight_booking_confirmed` (lead-time feedback)

### `mml_freight_3pl`
- `depends: ['mml_freight', 'stock_3pl_core']`
- `auto_install: True`
- Registers event subscription: `freight.booking.confirmed` → `TPLService.on_freight_booking_confirmed` (queue inward order)
- No new fields needed (the 3PL handoff is pure behaviour, not schema)

---

## ERP Agnosticism — The SAP/SAGE Play

Business logic services have **no ORM dependency**. They accept and return plain Python dicts/dataclasses. Odoo models are thin adapters:

```
mml_freight/
  services/
    freight_tender_service.py    ← pure Python, no self.env
    freight_quote_ranker.py      ← pure Python
    freight_booking_service.py   ← pure Python
  models/
    freight_tender.py            ← Odoo adapter: hydrate → call service → persist
```

This means:
- Services are testable without Odoo (plain `pytest`, no `odoo-bin`)
- Future `mml_roq_sap` module is a different adapter calling the same services
- Services can be extracted into a standalone Python package when the platform matures

---

## Billing Model

### Structure
```
Organization (license holder)
  └── Instance A (Odoo production)    ← instance_ref = 'mml-prod'
  └── Instance B (Odoo staging)       ← instance_ref = 'mml-staging'
  └── Instance C (future SAP adapter) ← instance_ref = 'mml-sap'

All instances share one floor credit per billing period.
Events from all instances aggregate into one bill.
```

### Monthly billing calculation (done on platform, not in Odoo)
```
subtotal     = sum(event.quantity × unit_rate for event in period_events)
floor        = license.floor_amount  (e.g. $1,000 NZD)
module_fee   = sum(module_monthly_rate for module in active_modules)
seat_fee     = seat_count × seat_rate  (if seat billing enabled)
base_charges = module_fee + seat_fee

billable     = max(subtotal, floor) + base_charges
```

The floor applies as a commitment: if event usage is below the floor, the customer pays the floor. Above it, they pay actual usage. Module and seat fees are additive on top.

### Implementation phasing
- **Now:** `mml.event` ledger records all events. `mml.billing.period` rolls up monthly totals. Platform client is a no-op stub.
- **When SaaS launches:** Swap stub for `RemotePlatformClient`. Events sync to central platform. Billing computed there.
- **Seat billing:** Optional; enabled per license. Count `res.users` with `mml_*` group memberships.

---

## Dependency Matrix (after refactor)

| Module | Depends on | Optional awareness via |
|---|---|---|
| `mml_base` | `mail`, `base` | — |
| `mml_roq_forecast` | `mml_base`, `base`, `sale`, `purchase`, `stock`, `stock_landed_costs` | service locator |
| `mml_freight` | `mml_base`, `mail`, `stock`, `account`, `purchase`, `delivery`, `stock_account` | service locator |
| `stock_3pl_core` | `mml_base`, `mail`, `stock`, `sale_management`, `purchase` | service locator |
| `mml_edi` | `mml_base`, `sale`, `account`, `stock`, `mail` | service locator |
| `mml_roq_freight` | `mml_roq_forecast`, `mml_freight` | — (bridge, auto-installs) |
| `mml_freight_3pl` | `mml_freight`, `stock_3pl_core` | — (bridge, auto-installs) |

---

## What Changes in Existing Modules

| Module | Change |
|---|---|
| `mml_roq_forecast` | Remove `mml_freight` from manifest `depends`. Delete `freight_tender_ext.py`. Guard or remove freight M2o in `roq_shipment_group.py`. Add `mml_base` to `depends`. Register capabilities + service on install. |
| `mml_freight` | Remove `stock_3pl_core` from manifest `depends`. Remove guarded 3PL code from `freight_booking.py` (moves to bridge). Add `mml_base` to `depends`. Register capabilities + service on install. |
| `stock_3pl_core` | Add `mml_base` to `depends`. Register capabilities + service on install. |
| `mml_edi` | Add `mml_base` to `depends`. Register capabilities + service on install. Emit billable events. |
| All modules | Extract business logic into `services/` pure-Python classes. |

---

## Out of Scope (this design)

- Central SaaS platform build (future)
- SAP / SAGE adapters (future)
- Multi-instance dashboard (future)
- Stripe/billing integration (future)
- `mml_roq_freight` and `mml_freight_3pl` bridge content beyond field declarations (implementation detail)
