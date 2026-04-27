# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read this file first before touching any module. It defines intent, boundaries, and wiring.
> Each subdirectory also has its own `CLAUDE.md` with module-specific detail — read both.

---

## Company Context

MML Consumer Products Ltd is a New Zealand-based distribution company (~400 SKUs, 5 brands: Volere, Annabel Langbein, Enkel, Enduro, Rufus & Coco) selling to major NZ/AU retail chains. Self-hosted Odoo 19.

**Architecture goal:** Each `mml_*` module is a standalone, independently installable Odoo app — a sellable SaaS product. All must be production-safe, auditable, and operable by a small non-technical ops team.

---

## Actual Directory Structure

```
mml.odoo.apps/
├── CLAUDE.md                            ← Root context (you are here)
├── mml_base/                            ← Platform layer (event bus, capability registry, billing ledger)
├── mml_roq_freight/                     ← Bridge: ROQ ↔ Freight schema bridge (auto_install)
├── mml_freight_3pl/                     ← Bridge: Freight ↔ 3PL schema bridge (auto_install)
├── mml.fowarder.intergration/           ← Freight forwarding modules
│   └── addons/
│       ├── mml_freight/                 ← Core freight orchestration (tender, quote, booking, tracking)
│       ├── mml_freight_dsv/             ← DSV carrier adapter (Generic API + XPress)
│       ├── mml_freight_knplus/          ← Kuehne+Nagel adapter
│       ├── mml_freight_mainfreight/     ← Mainfreight freight adapter
│       └── mml_freight_demo/            ← Demo data for freight
├── mml.3pl.intergration/                ← Mainfreight 3PL warehouse integration
│   └── addons/
│       ├── stock_3pl_core/              ← Forwarder-agnostic 3PL platform layer
│       └── stock_3pl_mainfreight/       ← Mainfreight implementation
├── mml.roq.model/
│   └── mml_roq_forecast/               ← Demand forecasting, ROQ calculation, 12-month shipment plan
├── mml_edi/                             ← EDI engine: mml_edi Odoo module + legacy .NET binaries
├── mml.barcodes/
│   └── mml_barcode_registry/            ← Barcode registry module
├── mml.forecasting/
│   ├── mml_forecast_core/               ← Core forecasting engine
│   └── mml_forecast_financial/          ← Financial forecasting layer
└── mml_petpro_storefront_user/          ← Min-priv RPC user for the headless petpro.co.nz storefront (groups + ACLs only)
```

**Note on typos:** `mml.fowarder.intergration` and `mml.3pl.intergration` are intentional directory names (typos preserved from original repo history).

### Storefront RPC convention

The headless `pet.pro.website` (Next.js) connects to Odoo as a *dedicated*
least-privilege user — `petpro_storefront@petpro.co.nz` — defined by the
`mml_petpro_storefront_user` module. **Do not** point the storefront at the
Odoo admin account. Operator runbook for switching credentials:
`docs/operations/2026-04-27-petpro-storefront-user-runbook.md`.

---

## Development Commands

### Install Python dependencies
```bash
pip install -r requirements.txt
# Per-workspace:
pip install -r mml.3pl.intergration/requirements.txt
pip install -r mml.roq.model/requirements.txt
```

### Run pure-Python tests (no Odoo needed — fast, use these during development)
```bash
# All pure-Python tests across the repo
pytest -m "not odoo_integration" -q

# Single workspace
pytest mml.3pl.intergration/ -m "not odoo_integration" -q
pytest mml.fowarder.intergration/ -m "not odoo_integration" -q
pytest mml.roq.model/ -m "not odoo_integration" -q
pytest mml.forecasting/ -m "not odoo_integration" -q

# Single test file
pytest mml.3pl.intergration/addons/stock_3pl_mainfreight/tests/test_route_engine.py -q
```

### Run Odoo integration tests (requires live Odoo database)
```bash
# Install/update modules
python odoo-bin -i stock_3pl_core,stock_3pl_mainfreight -d <db> --stop-after-init

# Run tests via odoo-bin
python odoo-bin --test-enable -u stock_3pl_core,stock_3pl_mainfreight -d <db> --stop-after-init
python odoo-bin --test-enable -d <db> --test-tags mml_roq_forecast
python odoo-bin --test-enable -d <db> --test-tags /mml_roq_forecast:TestAbcClassifier
```

---

## Test Infrastructure

The repo uses a **two-tier test strategy**:

| Tier | Marker | Runner | What it tests |
|------|--------|--------|---------------|
| Pure-Python structural | *(no marker)* | `pytest` | Parsing, builders, field defs, service logic — no Odoo needed |
| Odoo integration | `odoo_integration` | `odoo-bin --test-enable` | ORM operations requiring `self.env` |

The root `conftest.py` installs lightweight Odoo stubs (`odoo.models`, `odoo.fields`, `odoo.api`, `odoo.exceptions`, `odoo.http`, `odoo.tests`) into `sys.modules` so pure-Python tests can import Odoo model classes without a running Odoo instance. Tests inheriting from `odoo.tests.TransactionCase` are auto-marked `odoo_integration` and silently skipped under plain `pytest`.

Each workspace (`mml.fowarder.intergration/`, `mml.3pl.intergration/`, `mml.roq.model/`, `mml.edi/`, `mml.forecasting/`) has its own `pytest.ini` with the same marker definition so tests can be run from within that workspace directory.

---

## Platform Layer: `mml_base`

All `mml_*` modules depend on `mml_base` + standard Odoo. **No direct cross-module Python imports between app modules.**

`mml_base` provides three integration components:

| Model | Purpose |
|-------|---------|
| `mml.capability` | Registry of what each installed module provides; queried before service calls to avoid hard deps |
| `mml.registry` | Service locator; returns `NullService` (no-op) if a module is not installed |
| `mml.event` | Persisted event ledger; doubles as billing meter (`company_id` + `instance_ref` on every event) |
| `mml.license` | License cache; communicates with `mml.composer` (external SaaS platform) |

`mml_base` is `application = False` — no menu, no UI, installed as a dependency.

---

## Module Descriptions

### `mml_freight` — Freight Forwarding Orchestrator
PO confirmed → freight tender → multi-carrier quote → booking → tracking → landed cost. Incoterm determines freight responsibility (EXW/FCA/FOB/FAS = MML tenders; CFR/CIF/DAP/DDP = seller handles). Carrier abstraction layer: each carrier is a provider module (`mml_freight_dsv`, `mml_freight_knplus`, etc.).

DSV uses two APIs: **DSV Generic** (Road/Air/Sea/Rail — OAuth2) and **DSV XPress** (courier — Service Auth + PAT). Webhooks at `/dsv/webhook/<carrier_id>`.

### `stock_3pl_core` — 3PL Platform Layer
Forwarder-agnostic platform: `3pl.connector` (warehouse/transport config), `3pl.message` (async queue, state machine, exponential backoff, dead-letter). Transport implementations: `RestTransport`, `SFTPTransport`, `HttpPostTransport`. `application = False`.

### `stock_3pl_mainfreight` — Mainfreight 3PL Implementation
Extends `stock_3pl_core` with Mainfreight-specific document builders (CSV/XML for SOH, INWH, product specs) and parsers (SO confirmations, inventory reports → `stock.quant` upsert). Custom fields use `x_mf_*` prefix on `stock.warehouse`, `stock.picking`, `sale.order`. Sprint 2 adds haversine-based warehouse routing engine.

### `mml_roq_forecast` — Demand Forecast & ROQ Engine
Three-layer system: (1) Per-SKU ABCD classification + SMA/EWMA/Holt-Winters demand forecast + safety stock; (2) ROQ `(s,S)` calculation + container fitting + pipeline optimisation; (3) Reactive consolidation + push/pull + 12-month shipment plan. Business logic in pure-Python `services/` classes (no `self.env`) — Odoo models are thin adapters.

### Bridge Modules
- `mml_roq_freight` — schema bridge between ROQ ↔ Freight (`auto_install`, `application = False`)
- `mml_freight_3pl` — schema bridge between Freight ↔ 3PL (`auto_install`, `application = False`)

### `mml.edi/`
**Contains two systems:** (1) `mml_edi` — the active Odoo 19 Python EDI module (customer-agnostic EDI engine). (2) Legacy .NET Framework 4.8 Windows service (`BriscoesEditOrder`) compiled binaries — polls EDIS VAN FTP (`post.edis.co.nz`) every 15 min, parses Briscoes POs, creates Odoo SOs via XML-RPC. Config entirely in `*.exe.config`. Source in a separate repo.

---

## Cross-Module Integration

Modules communicate via shared Odoo models, chatter (`mail.message`), and computed fields — never direct Python imports. The `mml.event` ledger in `mml_base` is the canonical cross-module signal.

| Trigger | Source | Consumer | Action |
|---------|--------|----------|--------|
| SO confirmed (EDI partner) | `mml_edi` | `stock_3pl_mainfreight` | Queue despatch to Mainfreight |
| Mainfreight despatch confirmed | `stock_3pl_mainfreight` | `mml_edi` | Generate & send ASN |
| PO confirmed (MML freight) | `purchase` | `mml_freight` | Create tender, request quotes |
| `freight.booking` confirmed | `mml_freight` | `stock_3pl_core` | Create `3pl.message` (inward_order) |
| Freight delivered | `mml_freight` | `stock_3pl_mainfreight` | Trigger inbound receipt |
| Invoice validated (EDI partner) | `account` | `mml_edi` | Generate & send EDI invoice |
| Freight landed cost finalised | `mml_freight` | `account` | Update product cost |

---

## Technical Standards

### Odoo Conventions
- Module prefix: `mml_` (or `stock_3pl_` for the 3PL platform)
- Model naming: `mml.freight.booking`, `3pl.message`, `mml.roq.forecast.run`
- Security: `ir.model.access.csv` + record rules per module
- Credentials: `ir.config_parameter` only — never hardcoded
- All external API requests/responses logged as `ir.attachment`
- Retry: exponential backoff, max 3 attempts, then dead-letter queue
- App modules: `application = True`, own root menuitem (no `parent=`), `web_icon` pointing to `static/description/icon.png`
- Platform/bridge modules: `application = False`, no menu

### ERP Agnosticism
Business logic lives in pure-Python `services/` classes (no `self.env`). Odoo models are thin adapters. This is intentional — future SAP/SAGE adapters call the same service layer.

## Available Commands

- `/plan` — implementation plan before adding models, services, or cross-module wiring
- `/tdd` — TDD workflow; write pure-Python tests first, then Odoo integration tests
- `/code-review` — quality and security review before module release
- `/build-fix` — diagnose pytest or `odoo-bin --test-enable` failures
- `/security-scan` — check for hardcoded credentials, ACL gaps, injection risks
