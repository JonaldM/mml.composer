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
| `mml.event` | Persisted event ledger. Modules emit named events with a JSON payload. Each row is also a billing meter entry (`company_id` + `instance_ref` on every event). |
| `mml.event.subscription` | Idempotent subscription records — created on bridge install, removed on bridge uninstall. Bridge modules register handlers here; the event bus dispatches to them at runtime. |
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
    event_name='shipment_group.confirmed',
    payload={'shipment_group_id': self.id},
    source_model='roq.shipment.group',
    source_id=self.id,
)

# Subscribe (in a bridge module's hooks.py):
self.env['mml.event.subscription'].register(
    event_name='shipment_group.confirmed',
    handler_module='mml_roq_freight',
    handler_method='_on_shipment_group_confirmed',
)
```

Handler methods must follow the naming convention `_on_<event_name_underscored>` and live on an Odoo model in the subscribing module. Bridge modules are the correct place for subscriptions — not the emitting module.

---

## Capability registry

```python
# On module install (hooks.py):
env['mml.capability'].register('freight.quote.request')

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
└── tests/
    └── (Odoo integration tests — require odoo-bin --test-enable)
```

---

## Installation

```bash
odoo-bin -d <db> -i mml_base --stop-after-init
```

All other `mml_*` operational modules declare `mml_base` in their `depends` list. Odoo resolves the dependency automatically — `mml_base` will always be installed first.

---

## Running tests

All `mml_base` tests are Odoo integration tests (they test ORM-level behaviour of the event bus and registry). Run via `odoo-bin`:

```bash
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
