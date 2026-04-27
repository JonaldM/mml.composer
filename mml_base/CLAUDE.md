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
| `mml.event.subscription` | Pub/sub table. Modules subscribe in `post_init_hook`; events fan-out to handlers via `dispatch()`. Each handler runs in its own Postgres savepoint — see "Handler isolation" below. |
| `mml.event.dispatch.failure` | Triage log: one row per handler invocation that raised inside its savepoint. Read-only for `base.group_user`, full CRUD for `base.group_system`. |
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

## Handler isolation

`mml.event.subscription.dispatch()` runs every subscribed handler for an event type sequentially **inside its own Postgres SAVEPOINT** (`with self.env.cr.savepoint():`). The contract:

| Producer module A emits | What happens to A's `mml.event` row | What happens to handler in module B |
|-------------------------|-------------------------------------|-------------------------------------|
| Handler succeeds | Persisted | DB writes persisted |
| Handler raises | **Persisted** (unaffected) | Savepoint rolled back; row written to `mml.event.dispatch.failure`; dispatch continues with next handler |

Why this matters: producer module A is billed for emitting the event. A bug in some unrelated module B's handler must NOT roll back A's billing record. Before this change, a single failing handler would tear down the entire transaction including the `mml.event.create()`. Now failures are sandboxed per-subscriber.

The handler-method allowlist (`^_on_[a-z_]+$`) is still enforced **before** invocation — rejected subscriptions never enter a savepoint and never log a failure row.

### Triaging failures

System admins see failed dispatches under **Settings → Technical → MML Dispatch Failures**. Each row records:

- The originating `mml.event` (Many2one, cascade-delete)
- The `mml.event.subscription` whose handler raised
- `error_class`, `error_message`, full Python `traceback`
- A `resolved` toggle for triage workflow

### Retry workflow

There is currently **no automatic retry**. To replay a failure:

1. Open the failure form and read the traceback to confirm the underlying bug is fixed.
2. Re-emit the original event manually:
   ```python
   failure = env['mml.event.dispatch.failure'].browse(<id>)
   env['mml.event.subscription'].dispatch(failure.event_id)
   ```
   This re-runs **every** handler, so use it carefully — handlers that already succeeded the first time will run again. Future iteration: a `retry()` button on the form view that targets only the originating subscription.
3. Mark the row resolved.

### Internal contract

The two methods on `MmlEventSubscription` that implement isolation are intentional broad-`except` sites:

- `_dispatch_one(event, sub)` — wraps a single handler in a savepoint, logs failures.
- `_log_dispatch_failure(event, sub, exc)` — guards the failure-log `create()` itself; if writing the log fails we log to the Python logger and continue rather than crash dispatch.

`tests/test_event_dispatch_exceptions.py` allowlists exactly these two functions; bare `except Exception` anywhere else in `mml_event_subscription.py` will fail CI.

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
