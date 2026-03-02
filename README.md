# MML Odoo Apps — Module Monorepo

Odoo 19 modules for **MML Consumer Products Ltd**, a NZ-based distribution company (~400 SKUs, 5 brands). This repository is the integration layer that connects the individual functional modules into a single operational platform.

---

## Repository Layout

```
mml.odoo.apps/
├── mml_base/              ← Platform layer — must be installed first
├── mml_roq_freight/       ← Bridge: ROQ ↔ Freight (auto_install)
├── mml_freight_3pl/       ← Bridge: Freight ↔ 3PL (auto_install)
├── roq.model/             ← mml_roq_forecast module (git subdir → mml.roq.odoo)
├── fowarder.intergration/ ← mml_freight + adapters (git subdir → mml.freight.fowarder)
├── mainfreight.3pl.intergration/ ← stock_3pl_core + stock_3pl_mainfreight (git subdir → mml.3pl.odoo)
└── briscoes.edi/          ← mml_edi module (git subdir → mml.edi.odoo)
```

---

## mml_base — Platform Layer

All modules depend on `mml_base`. It provides:

| Component | Purpose |
|-----------|---------|
| **Capability Registry** (`mml.capability`) | Modules declare what they can do on install; deregister on uninstall |
| **Service Locator** (`mml.registry`) | Retrieve a live service or a safe NullService when a module is not installed |
| **Event Bus** (`mml.event`) | Modules emit named events; bridge modules subscribe and react |
| **Event Subscriptions** (`mml.event.subscription`) | Idempotent subscription records; auto-removed on module uninstall |
| **Billing Ledger** (`mml.event`) | Each emit records quantity and billable unit for usage tracking |

### NullService pattern

When a module is not installed, `env['mml.registry'].service('name')` returns a `NullService` — an object whose every method returns `None`. Callers never need to check whether a peer module is installed; a `None` return is a safe no-op.

---

## Bridge Modules

Bridge modules handle unavoidable cross-module `_inherit` requirements and event wiring. They use `auto_install: True` so they activate only when both parent modules are present.

### mml_roq_freight

Connects `mml_roq_forecast` ↔ `mml_freight`:

| Event | Handler | Action |
|-------|---------|--------|
| `roq.shipment_group.confirmed` | `mml.roq.freight.bridge` | Creates `freight.tender` via FreightService |
| `freight.booking.confirmed` | `mml.roq.freight.bridge` | Triggers ROQ lead-time stats update via ROQService |

### mml_freight_3pl

Connects `mml_freight` ↔ `stock_3pl_core`:

| Event | Handler | Action |
|-------|---------|--------|
| `freight.booking.confirmed` | `mml.3pl.bridge` | Queues one inward order per linked PO via TPLService |

---

## Module Dependency Graph

```
                    mml_base
                    /  |  |  \
           mml_freight |  |  mml_roq_forecast
              |        |  |        |
       stock_3pl_core  |  |    mml_edi
                       |  |
              mml_roq_freight  (bridge — auto_install)
              mml_freight_3pl  (bridge — auto_install)
```

---

## Install Order

```bash
# 1. Platform
odoo-bin -d <db> -i mml_base --stop-after-init

# 2. Core modules (any order, independently installable)
odoo-bin -d <db> -i stock_3pl_core,stock_3pl_mainfreight --stop-after-init
odoo-bin -d <db> -i mml_freight,mml_freight_dsv --stop-after-init
odoo-bin -d <db> -i mml_roq_forecast --stop-after-init
odoo-bin -d <db> -i mml_edi --stop-after-init

# 3. Bridge modules (auto-install when both parents are present)
odoo-bin -d <db> -i mml_roq_freight,mml_freight_3pl --stop-after-init
```

---

## Related Repositories

| Repo | GitHub | Contents |
|------|--------|---------|
| `mml.composer` | [JonaldMan/mml.composer](https://github.com/JonaldMan/mml.composer) | This repo — mml_base + bridges |
| `mml.roq.odoo` | [JonaldMan/mml.roq.odoo](https://github.com/JonaldMan/mml.roq.odoo) | `mml_roq_forecast` |
| `mml.freight.fowarder` | [JonaldMan/mml.freight.fowarder](https://github.com/JonaldMan/mml.freight.fowarder) | `mml_freight` + carrier adapters |
| `mml.3pl.odoo` | [JonaldMan/mml.3pl.odoo](https://github.com/JonaldMan/mml.3pl.odoo) | `stock_3pl_core` + `stock_3pl_mainfreight` |
| `mml.edi.odoo` | [JonaldMan/mml.edi.odoo](https://github.com/JonaldMan/mml.edi.odoo) | `mml_edi` |

---

## Running Tests

```bash
# Pure-Python tests (no Odoo instance required)
cd mml.odoo.apps
pytest mml_base/ mml_roq_freight/ mml_freight_3pl/ -m "not odoo_integration" -v

# Odoo integration tests
odoo-bin --test-enable --stop-after-init -d testdb \
  -i mml_base,mml_roq_freight,mml_freight_3pl \
  --test-tags=mml_base,mml_roq_freight,mml_freight_3pl
```
