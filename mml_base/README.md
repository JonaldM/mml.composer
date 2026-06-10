# mml_base — Platform Layer

**Module:** `mml_base`
**Application:** No (`application = False` — no UI, installed as a dependency)
**Depends on:** `base`, `mail`

Platform glue for all MML Odoo modules. Provides an event bus, a service locator, and a capability registry so modules can communicate without direct Python imports. Install this before any other `mml_*` module.

---

## What it provides

| Model | Purpose |
|---|---|
| `mml.capability` | Registry of what each installed module declares it can do. Populated on install via `hooks.py`. Checked by the service locator before delegating service calls. |
| `mml.registry` | Service locator. Call `env['mml.registry'].service('name')` to get a live service object. Returns a `NullService` safe no-op if the module is not installed — callers never need to guard with `if module_installed`. |
| `mml.event` | Persisted event ledger. Modules emit named events with a JSON payload. Each row is also a billing meter entry (`company_id` + `instance_ref` on every event). For events that can replay, `emit_idempotent(dedupe_key=…)` is enforced by a partial UNIQUE index (created by `init()` on fresh install **and** by the 19.0.1.1.0 migration on upgrade). Creates run via `sudo()` so non-admin business users can emit. |
| `mml.event.subscription` | Idempotent subscription records — created on bridge install, removed on bridge uninstall. Bridge modules register handlers here; the event bus dispatches to them at runtime. Each handler runs in its own Postgres savepoint — a failing handler is rolled back and recorded without breaking the emitter or other subscribers. |
| `mml.event.dispatch.failure` | Triage log: one row per handler invocation that raised inside its savepoint (error class, message, full traceback, resolved flag). Settings → Technical → MML Dispatch Failures. |
| `mml.license` | License cache for SaaS mode. Populated by `mml.composer` (external service). No-op stub until `mml.composer` is deployed. |
| `mml.platform.sync` | Reserved placeholder for composer heartbeat cron. |

---

## NullService pattern

```python
# Safe to call whether or not mml_freight is installed:
freight_svc = self.env['mml.registry'].service('freight')
freight_svc.request_quote(shipment)   # returns None if module absent — never raises

# Test if a service is available:
if not freight_svc.available():
    return  # module not installed
```

`NullService` implements `.is_null() → True`, `.available() → False`, and returns `None` for any method call. Callers can check `available()` when they need to branch, or just call the method directly if `None` is an acceptable no-op result.

---

## Event bus

```python
# Emit an event (any module):
self.env['mml.event'].emit(
    'roq.shipment_group.confirmed',
    quantity=1,
    billable_unit='shipment_group',
    res_model='roq.shipment.group',
    res_id=self.id,
    payload={'ref': self.name},
    source_module='mml_roq_forecast',
)

# Billing-safe variant for anything that can fire twice (retries, replays,
# cron reruns) — duplicate keys return the original event, no new row:
self.env['mml.event'].emit_idempotent(
    'freight.booking.confirmed',
    dedupe_key=f'mml_freight:freight.booking:{booking.id}:confirmed',
    quantity=1,
    billable_unit='freight_booking',
    res_model='freight.booking',
    res_id=booking.id,
    source_module='mml_freight',
)

# Subscribe (in a bridge module's post_init_hook):
env['mml.event.subscription'].register(
    event_type='roq.shipment_group.confirmed',
    handler_model='mml.roq.freight.bridge',
    handler_method='_on_shipment_group_confirmed',
    module='mml_roq_freight',
)
```

Handler method names are security-enforced: dispatch only calls methods matching
`^_on_[a-z0-9_]+$` (lowercase + digits, e.g. `_on_3pl_inbound_queued`) on the
subscribed Odoo model. Bridge modules are the correct place for subscriptions —
not the emitting module.

---

## Capability registry

```python
# On module install (post_init_hook) — takes a LIST plus the owning module:
env['mml.capability'].register(
    ['freight.quote.request', 'freight.booking.create'],
    module='mml_freight',
)

# Before making a service call in another module:
if env['mml.capability'].has('freight.quote.request'):
    svc.request_quote(...)
```

---

## `post_init_hook` — Instance identity

On first install, `mml_base` seeds a UUID into `ir.config_parameter` under the key `mml.instance_ref`. This UUID is written on every `mml.event` row and used by `mml.composer` for per-instance billing and multi-instance dashboards.

---

## Module structure

```
mml_base/
├── __manifest__.py
├── __init__.py
├── hooks.py            ← post_init_hook: seeds instance UUID, registers capabilities
├── models/
│   ├── mml_capability.py
│   ├── mml_registry.py
│   ├── mml_event.py
│   ├── mml_event_subscription.py
│   ├── mml_license.py
│   └── mml_platform_sync.py
├── services/
│   └── null_service.py ← NullService: is_null(), available(), __getattr__ → None
├── security/
│   └── ir.model.access.csv
├── data/
│   └── ir_cron_data.xml ← Platform sync cron (installed inactive)
├── migrations/
│   ├── 19.0.1.1.0/      ← partial UNIQUE index on mml_event.dedupe_key (upgrades)
│   └── 19.0.1.1.1/      ← re-registers platform rows on -u (post_init only runs on -i)
└── tests/
    ├── test_*.py        ← Odoo integration tests (odoo-bin --test-enable)
    └── test_pure_*.py   ← pure-Python tests (plain pytest, no Odoo needed)
```

---

## Installation

```bash
odoo-bin -d <db> -i mml_base --stop-after-init
```

All other `mml_*` operational modules declare `mml_base` in their `depends` list. Odoo resolves the dependency automatically — `mml_base` will always be installed first.

---

## Running tests

`mml_base` carries both test tiers: pure-Python tests (dispatch isolation, handler
regex, emit signatures, registry constants — plain `pytest`, no Odoo needed) and
Odoo integration tests (ORM-level event bus / registry behaviour — live DB):

```bash
# Pure-Python (no Odoo required):
pytest mml_base -m "not odoo_integration" -q

# Odoo integration:
odoo-bin --test-enable -u mml_base -d <db> --stop-after-init --test-tags=mml_base
```

---

## SaaS integration

`mml_base` includes a `PlatformClientBase` stub. When `mml.composer` is deployed, this stub is replaced by a `ComposerAPIClient` that:

1. Forwards every `mml.event` row to the composer via HTTPS POST.
2. Receives license grants back and populates `mml.license`.

No changes to any other module are required when the swap is made — the stub pattern is designed for this.

---

## Architecture notes

- **No cross-module Python imports.** `mml_base` knows nothing about `mml_freight`, `mml_edi`, or any other module. It provides the infrastructure; modules use it without `mml_base` knowing.
- **`application = False`.** No menuitem, no home screen tile. Installed as a dependency; users never interact with it directly.
- **`_ALLOWED_SERVICE_PREFIXES`** in `mml_registry.py` is an allowlist controlling which module namespaces may register services: `odoo.addons.mml_` and `odoo.addons.stock_3pl_`.
