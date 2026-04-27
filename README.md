# MML Odoo Apps — Module Monorepo

Odoo 19 modules for **MML Consumer Products Ltd**, a NZ-based distribution company (~400 SKUs, 5 brands). Each module is a standalone Odoo app — independently installable, independently billable. Built for internal MML operations with a SaaS distribution path.

---

## Repository Layout

```
mml.odoo.apps/                         ← This repo (mml.composer on GitHub)
│
├── mml_base/                          ← Platform layer — MUST be installed first
├── mml_roq_freight/                   ← Bridge: ROQ Demand ↔ Freight (auto_install)
├── mml_freight_3pl/                   ← Bridge: Freight ↔ 3PL (auto_install)
│
├── fowarder.intergration/             ← Freight domain (own git repo)
│   └── addons/
│       ├── mml_freight               ← Freight tender, booking, tracking
│       ├── mml_freight_dsv           ← DSV carrier adapter
│       ├── mml_freight_mainfreight   ← Mainfreight carrier adapter
│       ├── mml_freight_knplus        ← KN+ carrier adapter
│       └── mml_freight_demo          ← Demo data / sandbox
│
├── mainfreight.3pl.intergration/      ← 3PL domain (own git repo)
│   └── addons/
│       ├── stock_3pl_core            ← 3PL platform layer
│       └── stock_3pl_mainfreight     ← Mainfreight WMS adapter
│
├── briscoes.edi/                      ← EDI domain (own git repo)
│   └── mml.edi/
│       └── mml_edi                   ← EDI for retail partners (Briscoes, Harvey Norman, etc.)
│
├── barcodes/                          ← Barcode domain (own git repo)
│   └── mml_barcode_registry          ← GTIN lifecycle management and allocation
│
├── roq.model/                         ← ROQ demand module (to be superseded — see mml.forecasting)
│   └── mml_roq_forecast              ← Legacy ROQ demand engine
│
└── mml.forecasting/                   ← Forecasting suite (own git repo)
    ├── mml_forecast_core             ← Shared config, FX rates, origin ports, customer/supplier terms
    ├── mml_forecast_demand           ← ROQ demand engine (migrated from roq.model)
    └── mml_forecast_financial        ← P&L and cashflow financial forecasting
```

---

## mml_base — Platform Layer

**Install this first.** All operational mml_* modules depend on it.

`mml_base` provides the glue that lets modules communicate without direct imports. A module's Python code never calls another module's Python code — it emits events and looks up services.

| Model | Purpose |
|---|---|
| `mml.capability` | Modules declare what they provide on install; deregister on uninstall. Used by the service locator to decide whether a module is active. |
| `mml.registry` | Service locator. Call `env['mml.registry'].service('name')` to get a live service object, or a `NullService` (safe no-op) if the module is not installed. |
| `mml.event` | Persisted event ledger. Modules emit named events with payload. Bridge modules subscribe and react. Each emit is also a billing meter row. |
| `mml.event.subscription` | Idempotent subscription records — created on bridge install, removed on bridge uninstall. |
| `mml.license` | License cache for SaaS mode. Populated by `mml.composer` (external service). Currently a no-op stub. |
| `mml.platform.sync` | Cron-driven sync task placeholder — reserved for composer heartbeat. |

**Depends on:** `base`, `mail` only. No other mml_* module.

### NullService pattern

```python
# Safe to call whether or not mml_freight is installed:
freight_svc = self.env['mml.registry'].service('freight')
freight_svc.request_quote(shipment)   # returns None if module absent — no crash
```

When a peer module is not installed, every method on the `NullService` returns `None`. Callers never need to guard with `if module_installed`.

---

## Bridge Modules

Bridge modules handle `_inherit` requirements that cross module boundaries. They are `auto_install: True` — Odoo activates them automatically when both parents are present. Never install bridges manually.

### mml_roq_freight  (`auto_install` when `mml_roq_forecast` + `mml_freight` are both present)

Wires the ROQ demand engine to the freight booking workflow.

| Event emitted by | Handler in bridge | Action taken |
|---|---|---|
| `roq.shipment_group.confirmed` | `mml.roq.freight.bridge` | Creates a `freight.tender` via FreightService |
| `freight.booking.confirmed` | `mml.roq.freight.bridge` | Triggers ROQ lead-time stats update via ROQService |

### mml_freight_3pl  (`auto_install` when `mml_freight` + `stock_3pl_core` are both present)

Wires confirmed freight bookings to the 3PL inward order queue.

| Event emitted by | Handler in bridge | Action taken |
|---|---|---|
| `freight.booking.confirmed` | `mml.3pl.bridge` | Queues one inward order per linked PO via TPLService |

---

## Module Dependency Graph

```
Odoo core (base, mail, sale, purchase, stock, account)
         |
     mml_base
    /    |    \    \
   |     |     |    \
mml_freight  stock_3pl_core  mml_roq_forecast  mml_edi  mml_barcode_registry
   |    \           |              |
   |  mml_freight_dsv  stock_3pl_mainfreight    |
   |  mml_freight_mainfreight                   |
   |  mml_freight_knplus                        |
   |                                            |
   +-------- mml_roq_freight (bridge) ----------+
   |
   +-------- mml_freight_3pl (bridge) -------- stock_3pl_core


Odoo core (base, product, sale, purchase, account, mail)
         |
     mml_base
         |
  mml_forecast_core
    /           \
mml_forecast_demand   mml_forecast_financial
```

> **Note:** All modules — including the forecasting suite — depend on `mml_base`. `mml_forecast_core` declares `mml_base` in its `depends` list alongside `base`, `product`, `sale`, `purchase`, `account`, and `mail`.

---

## Install Order

Odoo resolves `depends` automatically, but this is the recommended explicit order for a fresh install.

```bash
DB=your_db_name
ODOO="python odoo-bin"

# ─── Step 1: Platform layer ───────────────────────────────────────────────
$ODOO -d $DB -i mml_base --stop-after-init

# ─── Step 2: Core operational modules (install in any order) ──────────────

# 3PL
$ODOO -d $DB -i stock_3pl_core,stock_3pl_mainfreight --stop-after-init

# Freight
$ODOO -d $DB -i mml_freight --stop-after-init
$ODOO -d $DB -i mml_freight_dsv --stop-after-init          # optional: DSV adapter
$ODOO -d $DB -i mml_freight_mainfreight --stop-after-init  # optional: Mainfreight adapter

# ROQ demand (legacy — use mml_forecast_demand for new installs)
$ODOO -d $DB -i mml_roq_forecast --stop-after-init

# EDI
$ODOO -d $DB -i mml_edi --stop-after-init

# Barcodes
$ODOO -d $DB -i mml_barcode_registry --stop-after-init

# ─── Step 3: Bridges (auto-install triggers automatically) ────────────────
# These activate themselves when both parents are detected.
# You can also force-install explicitly:
$ODOO -d $DB -i mml_roq_freight,mml_freight_3pl --stop-after-init

# ─── Step 4: Forecasting suite (independent of mml_base) ─────────────────
$ODOO -d $DB -i mml_forecast_core --stop-after-init
$ODOO -d $DB -i mml_forecast_demand --stop-after-init      # ROQ demand engine
$ODOO -d $DB -i mml_forecast_financial --stop-after-init   # P&L and cashflow
```

### Minimum install (forecasting only, no freight/3PL)

```bash
$ODOO -d $DB -i mml_base --stop-after-init
$ODOO -d $DB -i mml_forecast_core,mml_forecast_demand,mml_forecast_financial --stop-after-init
```

### Minimum install (EDI + barcodes only)

```bash
$ODOO -d $DB -i mml_base --stop-after-init
$ODOO -d $DB -i mml_edi,mml_barcode_registry --stop-after-init
```

---

## Module Reference

| Module | Repo folder | `application` | Depends on | Purpose |
|---|---|---|---|---|
| `mml_base` | `mml_base/` | False | `base`, `mail` | Platform layer — event bus, service locator, capability registry |
| `mml_roq_freight` | `mml_roq_freight/` | False | `mml_roq_forecast`, `mml_freight` | Bridge: ROQ ↔ Freight (auto_install) |
| `mml_freight_3pl` | `mml_freight_3pl/` | False | `mml_freight`, `stock_3pl_core` | Bridge: Freight ↔ 3PL (auto_install) |
| `mml_freight` | `fowarder.intergration/addons/mml_freight/` | True | `mml_base`, `mail`, `purchase`, `stock`, `account` | Freight tender, quote, booking, tracking |
| `mml_freight_dsv` | `fowarder.intergration/addons/mml_freight_dsv/` | False | `mml_freight` | DSV carrier adapter |
| `mml_freight_mainfreight` | `fowarder.intergration/addons/mml_freight_mainfreight/` | False | `mml_freight` | Mainfreight freight adapter |
| `stock_3pl_core` | `mainfreight.3pl.intergration/addons/stock_3pl_core/` | True | `mml_base`, `stock`, `sale_management`, `purchase` | 3PL platform layer |
| `stock_3pl_mainfreight` | `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/` | False | `stock_3pl_core` | Mainfreight WMS adapter |
| `mml_edi` | `briscoes.edi/mml.edi/` | True | `mml_base`, `sale`, `account`, `stock`, `mail` | EDI for retail partners |
| `mml_barcode_registry` | `barcodes/mml_barcode_registry/` | True | `mml_base`, `stock`, `product`, `mail` | GTIN lifecycle management and allocation |
| `mml_roq_forecast` | `roq.model/mml_roq_forecast/` | True | `mml_base` | Legacy ROQ demand engine — superseded by `mml_forecast_demand` |
| `mml_forecast_core` | `mml.forecasting/mml_forecast_core/` | **True** | `mml_base`, `base`, `product`, `sale`, `purchase`, `account`, `mail` | Forecasting suite shared infra — FX rates, origin ports, config, terms |
| `mml_forecast_demand` | `mml.forecasting/mml_forecast_demand/` | False | `mml_forecast_core` | ROQ demand engine (migrated from `mml_roq_forecast`) |
| `mml_forecast_financial` | `mml.forecasting/mml_forecast_financial/` | False | `mml_base`, `mml_forecast_core`, `account` | P&L and cashflow financial forecasting |

---

## Forecasting Suite Detail

The `mml.forecasting` repo is a standalone git repository at `mml.forecasting/`. It depends on `mml_base` for the platform layer; `mml_forecast_core` is the shared forecasting infrastructure that both sub-modules depend on.

### Module roles

| Module | `application` | UI entry point |
|---|---|---|
| `mml_forecast_core` | True | "Forecasting" app tile — all suite menus live here |
| `mml_forecast_demand` | False | Adds "Demand Planning" submenu under Forecasting |
| `mml_forecast_financial` | False | Adds "Financial Planning" submenu under Forecasting |

### Key shared models (in mml_forecast_core)

| Model | Purpose |
|---|---|
| `forecast.config` | Top-level forecast record — scenario, horizon, FX rates, tax, supplier terms |
| `forecast.origin.port` | UN/LOCODE port with `transit_days_nz` (default CNSHA=22, CNNGB=20, CNSZX=18) |
| `forecast.supplier.term` | Per-forecast supplier config: deposit %, production lead days, origin port |
| `forecast.fx.rate` | Per-config FX rate (FCY → NZD) |
| `forecast.customer.term` | Customer payment timing rules for cashflow inflow projection |

### Demand interface contract

`mml_forecast_demand` exposes a standard interface on `roq.forecast.run`:

```python
run.get_demand_forecast(date_start: date, horizon_months: int) -> list[dict]
# Each dict: {product_id, partner_id, period_start, period_label, forecast_units, brand, category}
```

`mml_forecast_financial` calls this via `self.env.get('roq.forecast.run')` — no hard import.

---

## Submodule layout

Five of the directories above are **git submodules** of separate sister repos.
The parent (this repo) pins each to a specific commit; the sub-repos are
where day-to-day development happens.

| Submodule path | Sub-repo |
|---|---|
| `mml.3pl.intergration` | [JonaldM/mml.3pl.odoo](https://github.com/JonaldM/mml.3pl.odoo) |
| `mml.fowarder.intergration` | [JonaldM/mml.freight.fowarder](https://github.com/JonaldM/mml.freight.fowarder) |
| `mml.forecasting` | [JonaldM/mml.forecasting](https://github.com/JonaldM/mml.forecasting) |
| `mml.roq.model` | [JonaldM/mml.roq.odoo](https://github.com/JonaldM/mml.roq.odoo) |
| `mml_edi` | [JonaldM/mml.edi.odoo](https://github.com/JonaldM/mml.edi.odoo) |

```bash
# Clone fresh
git clone --recurse-submodules https://github.com/JonaldM/mml.composer.git

# Or, if already cloned:
git submodule update --init --recursive
```

Per-submodule changes go through the sub-repo's own PR first; the parent then
bumps the pointer in a follow-up commit. Full workflow:
[`docs/operations/submodules-howto.md`](docs/operations/submodules-howto.md).

---

## Related Repositories

| Repo | GitHub | What's in it |
|---|---|---|
| `mml.odoo.apps` | (this repo) | `mml_base`, bridge modules, dev monorepo |
| `mml.forecasting` | [JonaldM/mml.forecasting](https://github.com/JonaldM/mml.forecasting) | Forecasting suite (`mml_forecast_*`) |
| `mml.freight.fowarder` | [JonaldM/mml.freight.fowarder](https://github.com/JonaldM/mml.freight.fowarder) | `mml_freight` + carrier adapters |
| `mml.3pl.odoo` | [JonaldM/mml.3pl.odoo](https://github.com/JonaldM/mml.3pl.odoo) | `stock_3pl_core` + `stock_3pl_mainfreight` |
| `mml.edi.odoo` | [JonaldM/mml.edi.odoo](https://github.com/JonaldM/mml.edi.odoo) | `mml_edi` |
| `mml.composer` | [JonaldM/mml.composer](https://github.com/JonaldM/mml.composer) | SaaS platform: license server, billing engine, multi-instance dashboard |

> `mml.roq.odoo` (legacy ROQ repo) is archived. Development continues in `mml.forecasting/mml_forecast_demand`.

---

## Running Tests

```bash
# Pure-Python unit tests (no Odoo instance required)
cd mml.odoo.apps
pytest mml_base/ mml_roq_freight/ mml_freight_3pl/ -m "not odoo_integration" -v

# Odoo integration tests — platform layer
odoo-bin --test-enable --stop-after-init -d testdb \
  -i mml_base,mml_roq_freight,mml_freight_3pl \
  --test-tags=mml_base,mml_roq_freight,mml_freight_3pl

# Forecasting suite tests
cd mml.forecasting
odoo-bin --test-enable --stop-after-init -d testdb \
  -i mml_forecast_core,mml_forecast_demand,mml_forecast_financial \
  --test-tags=mml_forecast_core,mml_forecast_demand,mml_forecast_financial
```

---

## Architecture Principles

1. **No direct cross-module Python imports.** Modules communicate via `mml.event` (emit/subscribe) and `mml.registry` (service locator). The forecasting suite uses `env.get()` guards instead.

2. **NullService everywhere.** If a peer module is not installed, service calls return `None` — never crash.

3. **Bridge modules are thin.** Bridges contain only event subscriptions and `_inherit` field additions. Business logic lives in the parent modules.

4. **Every mml_* app is independently installable.** A customer can buy just EDI, just freight, just forecasting — no forced bundle.

5. **`mml_base` is the only shared dependency for operational modules.** The forecasting suite is intentionally isolated from `mml_base` so it can be sold standalone without dragging in the event bus infrastructure.
