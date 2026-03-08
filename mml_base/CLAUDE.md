# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read the root `../CLAUDE.md` first — it defines the full platform architecture, dev commands, and cross-module integration rules. This file covers only what is specific to `mml_base`.

---

## Module Role

`mml_base` is the platform layer all `mml_*` modules depend on. It has no UI, no menu, and `application = False`. It provides four integration primitives:

| Model | What it does |
|-------|-------------|
| `mml.capability` | Registry of named capabilities declared by each module. Other modules call `has()` before assuming a feature is available. |
| `mml.registry` (AbstractModel) | Service locator. Returns a live service instance or `NullService` — callers never check whether a module is installed. |
| `mml.event` | Persisted, append-only event ledger. Every record carries `company_id` + `instance_ref` for billing. |
| `mml.event.subscription` | Pub/sub table. Modules subscribe in `post_init_hook`; events fan-out to handlers via `dispatch()`. |
| `mml.license` | License cache. Stores the current tier + module grants + billing floor. |
| `mml.platform.sync` (AbstractModel) | Cron target that pushes unsynced events to mml.composer. Currently a no-op stub. |

---

## Key Design Constraints

**Handler method names are security-enforced.** `mml.event.subscription.dispatch()` rejects any `handler_method` that does not match `^_on_[a-z_]+$`. All event handler methods across every module must follow that naming convention.

**Service locator never raises.** `mml.registry.service('some_service')` returns `NullService` (all calls silently return `None`) when the module is not installed. Callers must not test the return type — they call it and move on.

**In-process cache, DB-backed re-hydration.** `mml.registry` keeps a module-level `_SERVICE_REGISTRY` dict for fast lookups. On Odoo worker fork, the dict is empty; the first miss loads the class path from `ir.config_parameter` (key prefix `mml_registry.service.`) and caches it.

**Platform sync is a stub.** `PlatformClientBase.sync_events()` always returns `False` and logs a debug message. The cron job `cron_mml_platform_sync` ships with `active=False`. When `mml.composer` is live, replace `PlatformClientBase` with `ComposerAPIClient` — nothing else changes.

**`mml.instance_ref` config param.** Every emitted event reads `ir.config_parameter` key `mml.instance_ref` to tag itself. Set this per-instance for multi-tenant billing.

---

## Adding a New Module that Uses mml_base

### 1. Declare capabilities in `post_init_hook`
```python
def post_init_hook(env):
    env['mml.capability'].register(
        ['my_module.do_thing', 'my_module.other_thing'],
        module='my_module',
    )
```

### 2. Subscribe to events in `post_init_hook`
```python
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='my.model',
        handler_method='_on_freight_booking_confirmed',  # MUST match ^_on_[a-z_]+$
        module='my_module',
    )
```

### 3. Register a service in `post_init_hook`
```python
    from odoo.addons.my_module.services.my_service import MyService
    env['mml.registry'].register('my_service', MyService)
```

### 4. Clean up in `uninstall_hook`
```python
def uninstall_hook(env):
    env['mml.capability'].deregister_module('my_module')
    env['mml.event.subscription'].deregister_module('my_module')
    env['mml.registry'].deregister('my_service')
```

### 5. Emit events from business logic
```python
self.env['mml.event'].emit(
    'my_module.thing_happened',
    quantity=1,
    billable_unit='thing',
    res_model=self._name,
    res_id=self.id,
    payload={'ref': self.name},
    source_module='my_module',
)
```

### 6. Call a service without hard-importing the provider
```python
svc = self.env['mml.registry'].service('freight_service')
svc.do_thing(...)  # silently no-ops if mml_freight is not installed
```

---

## Tests

All tests in `tests/` extend `TransactionCase` and require a live Odoo database (`odoo_integration` marker). There are no pure-Python tests in this module — the models are thin enough that meaningful tests require the ORM.

```bash
# Run mml_base integration tests
python odoo-bin --test-enable -u mml_base -d <db> --stop-after-init
python odoo-bin --test-enable -d <db> --test-tags /mml_base
```

---

## Security ACLs

`security/ir.model.access.csv` grants:
- `base.group_user` — read-only on `mml.capability`, `mml.event`, `mml.event.subscription`, `mml.license`
- `base.group_system` — full CRUD on all four

`mml.license.license_key` is additionally restricted to `base.group_system` via `groups=` on the field.

## Available Commands

- `/plan` — before adding new platform primitives or changing the event bus contract
- `/tdd` — all tests here require live Odoo; use `/tdd` to plan test structure first
- `/security-scan` — review ACL definitions and handler method allowlists
