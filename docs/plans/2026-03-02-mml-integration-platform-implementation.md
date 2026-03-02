# MML Integration Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the MML module suite so every `mml_*` module is independently installable, connected via a shared `mml_base` event bus, capability registry, and service locator — with a billing event ledger built in from day one.

**Architecture:** A new `mml_base` Odoo module provides three components: a capability registry (what's installed), a service locator (NullService pattern for safe cross-module calls), and a persisted event bus that doubles as a billing meter. Two thin schema bridge modules (`mml_roq_freight`, `mml_freight_3pl`) handle the unavoidable Odoo model inheritance requirements; all business logic flows through `mml_base`. Business logic services are extracted into pure Python classes with no ORM dependency, enabling future SAP/SAGE adapters.

**Tech Stack:** Odoo 19, Python 3.12, standard Odoo ORM, pytest (pure Python services), odoo-bin --test-enable (ORM integration tests)

**Design doc:** `docs/plans/2026-03-02-mml-integration-platform-design.md`

---

## Phasing

- **Phase 0** — Build `mml_base` (Tasks 1–8)
- **Phase 1** — Decouple `mml_freight` from `stock_3pl_core` (Tasks 9–12)
- **Phase 2** — Decouple `mml_roq_forecast` from `mml_freight` (Tasks 13–16)
- **Phase 3** — Wire remaining modules to `mml_base` (Tasks 17–18)
- **Phase 4** — Create schema bridge modules (Tasks 19–21)

Each phase is independently deployable. Finish Phase 0 and test before moving on.

---

## Phase 0 — Build `mml_base`

---

### Task 1: Scaffold `mml_base` module

**Files:**
- Create: `mml_base/__manifest__.py`
- Create: `mml_base/__init__.py`
- Create: `mml_base/models/__init__.py`
- Create: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p mml_base/models
mkdir -p mml_base/security
mkdir -p mml_base/tests
touch mml_base/__init__.py
touch mml_base/models/__init__.py
touch mml_base/tests/__init__.py
```

**Step 2: Write manifest**

`mml_base/__manifest__.py`:
```python
{
    'name': 'MML Base Platform',
    'version': '19.0.1.0.0',
    'summary': 'Event bus, capability registry, service locator, and billing ledger for MML modules',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mail', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

**Step 3: Write `__init__.py`**

`mml_base/__init__.py`:
```python
from . import models
```

**Step 4: Create empty access CSV (will be populated as models are added)**

`mml_base/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

**Step 5: Commit**

```bash
git add mml_base/
git commit -m "feat(mml_base): scaffold module"
```

---

### Task 2: `mml.capability` — capability registry model

**Files:**
- Create: `mml_base/models/mml_capability.py`
- Modify: `mml_base/models/__init__.py`
- Modify: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/test_capability.py`

**Step 1: Write the failing test**

`mml_base/tests/test_capability.py`:
```python
from odoo.tests.common import TransactionCase


class TestCapabilityRegistry(TransactionCase):

    def test_register_and_has(self):
        """register() stores capability; has() returns True for it."""
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        self.assertTrue(self.env['mml.capability'].has('freight.tender.create'))

    def test_has_returns_false_for_unknown(self):
        """has() returns False for a capability that was never registered."""
        self.assertFalse(self.env['mml.capability'].has('nonexistent.capability'))

    def test_deregister_module_removes_all(self):
        """deregister_module() removes all capabilities registered by that module."""
        self.env['mml.capability'].register(
            ['freight.tender.create', 'freight.booking.confirm'],
            module='mml_freight',
        )
        self.env['mml.capability'].deregister_module('mml_freight')
        self.assertFalse(self.env['mml.capability'].has('freight.tender.create'))
        self.assertFalse(self.env['mml.capability'].has('freight.booking.confirm'))

    def test_register_is_idempotent(self):
        """Registering the same capability twice does not create duplicates."""
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        count = self.env['mml.capability'].search_count([
            ('name', '=', 'freight.tender.create'),
        ])
        self.assertEqual(count, 1)
```

**Step 2: Run test — verify it fails**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestCapabilityRegistry --stop-after-init
```
Expected: ImportError or model not found.

**Step 3: Write the model**

`mml_base/models/mml_capability.py`:
```python
from odoo import fields, models, api


class MmlCapability(models.Model):
    _name = 'mml.capability'
    _description = 'MML Capability Registry'

    name = fields.Char(required=True, index=True)
    module = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_name_module', 'UNIQUE(name, module)', 'Capability already registered for this module'),
    ]

    @api.model
    def register(self, capabilities: list[str], module: str) -> None:
        """Register a list of capability names for a module. Idempotent."""
        existing = self.search([('module', '=', module)]).mapped('name')
        to_create = [
            {'name': cap, 'module': module}
            for cap in capabilities
            if cap not in existing
        ]
        if to_create:
            self.create(to_create)

    @api.model
    def deregister_module(self, module: str) -> None:
        """Remove all capabilities registered by a module."""
        self.search([('module', '=', module)]).unlink()

    @api.model
    def has(self, capability: str) -> bool:
        """Return True if the capability is registered by any installed module."""
        return bool(self.search_count([('name', '=', capability)]))
```

**Step 4: Wire into `__init__.py` and access CSV**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
```

`mml_base/security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mml_capability_user,mml.capability user,model_mml_capability,base.group_user,1,0,0,0
access_mml_capability_system,mml.capability system,model_mml_capability,base.group_system,1,1,1,1
```

**Step 5: Run tests — verify pass**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestCapabilityRegistry --stop-after-init
```
Expected: 4 tests PASS.

**Step 6: Commit**

```bash
git add mml_base/models/mml_capability.py mml_base/models/__init__.py mml_base/security/ir.model.access.csv mml_base/tests/test_capability.py
git commit -m "feat(mml_base): add mml.capability registry"
```

---

### Task 3: `mml.registry` — service locator with NullService

**Files:**
- Create: `mml_base/services/__init__.py`
- Create: `mml_base/services/null_service.py`
- Create: `mml_base/models/mml_registry.py`
- Modify: `mml_base/models/__init__.py`
- Modify: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/test_registry.py`

**Step 1: Write failing tests**

`mml_base/tests/test_registry.py`:
```python
from odoo.tests.common import TransactionCase


class _StubFreightService:
    def __init__(self, env):
        self.env = env

    def create_tender(self, vals):
        return 42


class TestServiceRegistry(TransactionCase):

    def test_registered_service_is_returned(self):
        """service() returns the registered service instance."""
        self.env['mml.registry'].register('freight', _StubFreightService)
        svc = self.env['mml.registry'].service('freight')
        self.assertIsInstance(svc, _StubFreightService)

    def test_unregistered_service_returns_null(self):
        """service() returns a NullService when the service is not registered."""
        svc = self.env['mml.registry'].service('nonexistent')
        # NullService must not raise — all attribute access returns None
        result = svc.any_method_name()
        self.assertIsNone(result)

    def test_null_service_chained_calls_return_none(self):
        """NullService supports attribute chaining without raising."""
        from odoo.addons.mml_base.services.null_service import NullService
        svc = NullService()
        self.assertIsNone(svc.create_tender({'lines': []}))
        self.assertIsNone(svc.get_booking_lead_time(99))

    def test_deregister_reverts_to_null(self):
        """deregister() removes the service; subsequent calls return NullService."""
        self.env['mml.registry'].register('freight', _StubFreightService)
        self.env['mml.registry'].deregister('freight')
        svc = self.env['mml.registry'].service('freight')
        self.assertIsNone(svc.create_tender({}))
```

**Step 2: Run test — verify fails**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestServiceRegistry --stop-after-init
```

**Step 3: Write NullService**

`mml_base/services/__init__.py`: (empty)

`mml_base/services/null_service.py`:
```python
class NullService:
    """
    Returned by mml.registry when the requested service module is not installed.
    All method calls return None silently — callers never need to check installation state.
    """

    def __getattr__(self, name):
        return lambda *args, **kwargs: None
```

**Step 4: Write the registry model**

`mml_base/models/mml_registry.py`:
```python
from odoo import api, models

# In-process service registry — survives within a worker process lifetime.
# Populated via register() calls in each module's post_init_hook.
_SERVICE_REGISTRY: dict[str, type] = {}


class MmlRegistry(models.AbstractModel):
    _name = 'mml.registry'
    _description = 'MML Service Locator'

    @api.model
    def register(self, service_name: str, service_class: type) -> None:
        """Register a service class under a name. Called from post_init_hook."""
        _SERVICE_REGISTRY[service_name] = service_class

    @api.model
    def deregister(self, service_name: str) -> None:
        """Remove a service. Called from uninstall_hook."""
        _SERVICE_REGISTRY.pop(service_name, None)

    @api.model
    def service(self, service_name: str):
        """
        Return an instance of the registered service, or a NullService.
        The returned object is always safe to call — no existence check needed.
        """
        from odoo.addons.mml_base.services.null_service import NullService
        cls = _SERVICE_REGISTRY.get(service_name)
        if cls is None:
            return NullService()
        return cls(self.env)
```

**Step 5: Wire into `__init__.py` and access CSV**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
from . import mml_registry
```

Add to `mml_base/security/ir.model.access.csv` — AbstractModel needs no ACL row (no table).

**Step 6: Run tests — verify pass**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestServiceRegistry --stop-after-init
```
Expected: 4 PASS.

**Step 7: Commit**

```bash
git add mml_base/services/ mml_base/models/mml_registry.py mml_base/models/__init__.py mml_base/tests/test_registry.py
git commit -m "feat(mml_base): add service locator with NullService"
```

---

### Task 4: `mml.event` — persisted event ledger

**Files:**
- Create: `mml_base/models/mml_event.py`
- Modify: `mml_base/models/__init__.py`
- Modify: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/test_event.py`

**Step 1: Write failing tests**

`mml_base/tests/test_event.py`:
```python
from odoo.tests.common import TransactionCase


class TestEventBus(TransactionCase):

    def test_emit_creates_record(self):
        """emit() creates a persisted mml.event record."""
        before = self.env['mml.event'].search_count([])
        self.env['mml.event'].emit(
            'freight.booking.confirmed',
            quantity=1,
            billable_unit='freight_booking',
        )
        after = self.env['mml.event'].search_count([])
        self.assertEqual(after, before + 1)

    def test_emit_sets_fields_correctly(self):
        """emit() populates all fields on the created record."""
        self.env['mml.event'].emit(
            'freight.booking.confirmed',
            quantity=2,
            billable_unit='freight_booking',
            res_model='freight.booking',
            res_id=99,
            payload={'ref': 'FBK-001'},
        )
        event = self.env['mml.event'].search([
            ('event_type', '=', 'freight.booking.confirmed'),
        ], limit=1)
        self.assertEqual(event.quantity, 2)
        self.assertEqual(event.billable_unit, 'freight_booking')
        self.assertEqual(event.res_model, 'freight.booking')
        self.assertEqual(event.res_id, 99)
        self.assertIn('FBK-001', event.payload_json)
        self.assertFalse(event.synced_to_platform)

    def test_emit_tags_company(self):
        """emit() always tags the event with the current company."""
        self.env['mml.event'].emit('test.event', quantity=1, billable_unit='test')
        event = self.env['mml.event'].search([('event_type', '=', 'test.event')], limit=1)
        self.assertEqual(event.company_id, self.env.company)
```

**Step 2: Run test — verify fails**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestEventBus --stop-after-init
```

**Step 3: Write the model**

`mml_base/models/mml_event.py`:
```python
import json
from datetime import datetime
from odoo import api, fields, models


class MmlEvent(models.Model):
    _name = 'mml.event'
    _description = 'MML Event Ledger'
    _order = 'timestamp desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    instance_ref = fields.Char(compute='_compute_instance_ref', store=True)
    event_type = fields.Char(required=True, index=True)
    source_module = fields.Char()
    res_model = fields.Char()
    res_id = fields.Integer()
    payload_json = fields.Text()
    quantity = fields.Float(default=1.0)
    billable_unit = fields.Char()
    synced_to_platform = fields.Boolean(default=False, index=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.depends()
    def _compute_instance_ref(self):
        ref = self.env['ir.config_parameter'].sudo().get_param('mml.instance_ref', default='')
        for rec in self:
            rec.instance_ref = ref

    @api.model
    def emit(
        self,
        event_type: str,
        *,
        quantity: float = 1.0,
        billable_unit: str = '',
        res_model: str = '',
        res_id: int = 0,
        payload: dict | None = None,
        source_module: str = '',
    ) -> 'MmlEvent':
        """Create and persist a billable event. Call from any mml_* module."""
        return self.create({
            'event_type': event_type,
            'quantity': quantity,
            'billable_unit': billable_unit,
            'res_model': res_model,
            'res_id': res_id,
            'payload_json': json.dumps(payload or {}),
            'source_module': source_module,
        })
```

**Step 4: Wire into `__init__.py` and access CSV**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
from . import mml_registry
from . import mml_event
```

Add to `mml_base/security/ir.model.access.csv`:
```csv
access_mml_event_user,mml.event user,model_mml_event,base.group_user,1,0,0,0
access_mml_event_system,mml.event system,model_mml_event,base.group_system,1,1,1,1
```

**Step 5: Run tests — verify pass**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestEventBus --stop-after-init
```
Expected: 3 PASS.

**Step 6: Commit**

```bash
git add mml_base/models/mml_event.py mml_base/models/__init__.py mml_base/security/ir.model.access.csv mml_base/tests/test_event.py
git commit -m "feat(mml_base): add mml.event persisted event ledger"
```

---

### Task 5: `mml.event.subscription` — subscribe and dispatch

**Files:**
- Create: `mml_base/models/mml_event_subscription.py`
- Modify: `mml_base/models/mml_event.py` (wire dispatch into emit)
- Modify: `mml_base/models/__init__.py`
- Modify: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/test_event_subscription.py`

**Step 1: Write failing tests**

`mml_base/tests/test_event_subscription.py`:
```python
from unittest.mock import patch
from odoo.tests.common import TransactionCase


class TestEventSubscription(TransactionCase):

    def test_subscription_is_dispatched_on_emit(self):
        """Emitting an event calls registered handler methods."""
        called_with = []

        # Patch the handler to capture calls
        with patch.object(
            type(self.env['mml.event.subscription']),
            '_dispatch',
            side_effect=lambda event: called_with.append(event.event_type),
        ):
            self.env['mml.event.subscription'].register(
                event_type='test.dispatched',
                handler_model='mml.event.subscription',
                handler_method='_noop_handler',
                module='test_module',
            )
            self.env['mml.event'].emit('test.dispatched', quantity=1, billable_unit='test')

        self.assertIn('test.dispatched', called_with)

    def test_no_dispatch_for_unsubscribed_event(self):
        """Emitting an event with no subscribers does not raise."""
        # Should not raise
        self.env['mml.event'].emit('test.no_subscriber', quantity=1, billable_unit='test')

    def test_deregister_module_removes_subscriptions(self):
        """deregister_module() removes all subscriptions for that module."""
        self.env['mml.event.subscription'].register(
            event_type='test.removable',
            handler_model='mml.event.subscription',
            handler_method='_noop_handler',
            module='temp_module',
        )
        self.env['mml.event.subscription'].deregister_module('temp_module')
        count = self.env['mml.event.subscription'].search_count([
            ('module', '=', 'temp_module'),
        ])
        self.assertEqual(count, 0)
```

**Step 2: Run test — verify fails**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestEventSubscription --stop-after-init
```

**Step 3: Write subscription model**

`mml_base/models/mml_event_subscription.py`:
```python
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MmlEventSubscription(models.Model):
    _name = 'mml.event.subscription'
    _description = 'MML Event Subscription'

    event_type = fields.Char(required=True, index=True)
    handler_model = fields.Char(required=True)
    handler_method = fields.Char(required=True)
    module = fields.Char(required=True)

    @api.model
    def register(
        self,
        event_type: str,
        handler_model: str,
        handler_method: str,
        module: str,
    ) -> None:
        """Register a handler for an event type. Called from post_init_hook."""
        exists = self.search_count([
            ('event_type', '=', event_type),
            ('handler_model', '=', handler_model),
            ('handler_method', '=', handler_method),
        ])
        if not exists:
            self.create({
                'event_type': event_type,
                'handler_model': handler_model,
                'handler_method': handler_method,
                'module': module,
            })

    @api.model
    def deregister_module(self, module: str) -> None:
        """Remove all subscriptions registered by a module."""
        self.search([('module', '=', module)]).unlink()

    @api.model
    def dispatch(self, event) -> None:
        """Find all subscriptions for event.event_type and call their handlers."""
        subscriptions = self.search([('event_type', '=', event.event_type)])
        for sub in subscriptions:
            try:
                model = self.env.get(sub.handler_model)
                if model is not None:
                    getattr(model, sub.handler_method)(event)
            except Exception:
                _logger.exception(
                    'Event handler %s.%s failed for event %s (id=%s)',
                    sub.handler_model,
                    sub.handler_method,
                    event.event_type,
                    event.id,
                )

    def _noop_handler(self, event):
        """Placeholder handler used in tests."""
        pass

    def _dispatch(self, event):
        """Internal — allows patching in tests."""
        self.dispatch(event)
```

**Step 4: Wire dispatch into `mml.event.emit()`**

Modify `mml_base/models/mml_event.py` — add dispatch call at the end of `emit()`:
```python
    @api.model
    def emit(self, event_type, *, quantity=1.0, billable_unit='',
             res_model='', res_id=0, payload=None, source_module=''):
        event = self.create({
            'event_type': event_type,
            'quantity': quantity,
            'billable_unit': billable_unit,
            'res_model': res_model,
            'res_id': res_id,
            'payload_json': json.dumps(payload or {}),
            'source_module': source_module,
        })
        self.env['mml.event.subscription'].dispatch(event)
        return event
```

**Step 5: Wire into `__init__.py` and access CSV**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
from . import mml_registry
from . import mml_event
from . import mml_event_subscription
```

Add to `mml_base/security/ir.model.access.csv`:
```csv
access_mml_event_sub_user,mml.event.subscription user,model_mml_event_subscription,base.group_user,1,0,0,0
access_mml_event_sub_system,mml.event.subscription system,model_mml_event_subscription,base.group_system,1,1,1,1
```

**Step 6: Run all mml_base tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_base --stop-after-init
```
Expected: All prior tests + 3 new PASS.

**Step 7: Commit**

```bash
git add mml_base/models/mml_event_subscription.py mml_base/models/mml_event.py mml_base/models/__init__.py mml_base/security/ir.model.access.csv mml_base/tests/test_event_subscription.py
git commit -m "feat(mml_base): add event subscription dispatcher"
```

---

### Task 6: `mml.license` — license cache model

**Files:**
- Create: `mml_base/models/mml_license.py`
- Modify: `mml_base/models/__init__.py`
- Modify: `mml_base/security/ir.model.access.csv`
- Create: `mml_base/tests/test_license.py`

**Step 1: Write failing tests**

`mml_base/tests/test_license.py`:
```python
from odoo.tests.common import TransactionCase


class TestLicense(TransactionCase):

    def test_get_or_create_returns_record(self):
        """get_current() returns a license record (creates one if none exists)."""
        lic = self.env['mml.license'].get_current()
        self.assertIsNotNone(lic)

    def test_default_tier_is_internal(self):
        """Default license tier is 'internal' for fresh installations."""
        lic = self.env['mml.license'].get_current()
        self.assertEqual(lic.tier, 'internal')

    def test_module_permitted_internal_allows_all(self):
        """Internal tier permits all modules (wildcard)."""
        lic = self.env['mml.license'].get_current()
        self.assertTrue(lic.module_permitted('mml_freight'))
        self.assertTrue(lic.module_permitted('mml_roq_forecast'))
```

**Step 2: Run test — verify fails**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestLicense --stop-after-init
```

**Step 3: Write the model**

`mml_base/models/mml_license.py`:
```python
import json
from odoo import api, fields, models


class MmlLicense(models.Model):
    _name = 'mml.license'
    _description = 'MML License Cache'

    org_ref = fields.Char()
    license_key = fields.Char()
    tier = fields.Selection([
        ('internal', 'Internal'),
        ('starter', 'Starter'),
        ('growth', 'Growth'),
        ('enterprise', 'Enterprise'),
    ], default='internal', required=True)
    module_grants_json = fields.Text(default='["*"]')
    floor_amount = fields.Float(default=0.0)
    currency_id = fields.Many2one('res.currency')
    seat_limit = fields.Integer(default=0, help='0 = unlimited')
    valid_until = fields.Date()
    last_validated = fields.Datetime()

    @api.model
    def get_current(self):
        """Return the active license record, creating a default if none exists."""
        lic = self.search([], limit=1)
        if not lic:
            lic = self.create({'tier': 'internal'})
        return lic

    def module_permitted(self, module_name: str) -> bool:
        """Return True if this license grants access to the given module."""
        grants = json.loads(self.module_grants_json or '["*"]')
        return '*' in grants or module_name in grants
```

**Step 4: Wire into `__init__.py` and access CSV**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
from . import mml_registry
from . import mml_event
from . import mml_event_subscription
from . import mml_license
```

Add to `mml_base/security/ir.model.access.csv`:
```csv
access_mml_license_system,mml.license system,model_mml_license,base.group_system,1,1,1,1
```

**Step 5: Run tests — verify pass**

```bash
odoo-bin --test-enable -d testdb --test-tags /mml_base:TestLicense --stop-after-init
```
Expected: 3 PASS.

**Step 6: Commit**

```bash
git add mml_base/models/mml_license.py mml_base/models/__init__.py mml_base/security/ir.model.access.csv mml_base/tests/test_license.py
git commit -m "feat(mml_base): add mml.license cache model"
```

---

### Task 7: Platform client stub + event sync cron

**Files:**
- Create: `mml_base/services/platform_client.py`
- Create: `mml_base/models/mml_platform_sync.py`
- Modify: `mml_base/models/__init__.py`
- Create: `mml_base/data/ir_cron.xml`
- Modify: `mml_base/__manifest__.py`

**Step 1: Write platform client stub**

`mml_base/services/platform_client.py`:
```python
import logging

_logger = logging.getLogger(__name__)


class PlatformClientBase:
    """
    No-op stub. When the central SaaS platform is built, replace with
    RemotePlatformClient that POSTs events to the platform API.
    Zero changes to callers required.
    """

    def sync_events(self, events) -> bool:
        """Push unsynced events to the platform. Returns True on success."""
        _logger.debug('PlatformClientBase.sync_events: stub, %d events ignored', len(events))
        return True

    def validate_license(self, license_key: str) -> dict:
        """Validate license key against the platform. Returns grant dict."""
        return {'valid': True, 'tier': 'internal', 'modules': ['*']}
```

**Step 2: Write sync model (cron target)**

`mml_base/models/mml_platform_sync.py`:
```python
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class MmlPlatformSync(models.AbstractModel):
    _name = 'mml.platform.sync'
    _description = 'MML Platform Sync (cron target)'

    @api.model
    def _cron_sync_events(self) -> None:
        """Push unsynced mml.event records to the platform. Run every 15 minutes."""
        from odoo.addons.mml_base.services.platform_client import PlatformClientBase
        client = PlatformClientBase()
        pending = self.env['mml.event'].search([('synced_to_platform', '=', False)], limit=500)
        if not pending:
            return
        success = client.sync_events(pending)
        if success:
            pending.write({'synced_to_platform': True})
            _logger.info('mml.platform.sync: synced %d events', len(pending))
```

**Step 3: Write cron XML**

`mml_base/data/ir_cron.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="cron_mml_platform_sync" model="ir.cron">
        <field name="name">MML: Sync events to platform</field>
        <field name="model_id" ref="mml_base.model_mml_platform_sync"/>
        <field name="state">code</field>
        <field name="code">model._cron_sync_events()</field>
        <field name="interval_number">15</field>
        <field name="interval_type">minutes</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>
</odoo>
```

**Step 4: Wire into `__init__.py` and manifest**

`mml_base/models/__init__.py`:
```python
from . import mml_capability
from . import mml_registry
from . import mml_event
from . import mml_event_subscription
from . import mml_license
from . import mml_platform_sync
```

`mml_base/__manifest__.py` — add model_mml_platform_sync to ir.model.access.csv: AbstractModel needs no row.

**Step 5: Run all mml_base tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_base --stop-after-init
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add mml_base/services/platform_client.py mml_base/models/mml_platform_sync.py mml_base/models/__init__.py mml_base/data/ir_cron.xml
git commit -m "feat(mml_base): add platform client stub and event sync cron"
```

---

### Task 8: `mml_base` module hooks (register/deregister pattern)

This task establishes the pattern every other module will follow. It serves as the reference implementation.

**Files:**
- Create: `mml_base/hooks.py`
- Modify: `mml_base/__manifest__.py`
- Create: `mml_base/tests/test_hooks.py`

**Step 1: Write hooks**

`mml_base/hooks.py`:
```python
"""
post_init_hook and uninstall_hook for mml_base.
Every mml_* module implements this same pattern.
"""


def post_init_hook(env):
    """Called after module install. Register capabilities and services."""
    env['mml.capability'].register(
        ['mml.event.emit', 'mml.capability.register', 'mml.registry.service'],
        module='mml_base',
    )


def uninstall_hook(env):
    """Called before module uninstall. Clean up registry entries."""
    env['mml.capability'].deregister_module('mml_base')
    env['mml.registry'].deregister('base')
    env['mml.event.subscription'].deregister_module('mml_base')
```

**Step 2: Wire hooks into manifest**

`mml_base/__manifest__.py`:
```python
{
    'name': 'MML Base Platform',
    'version': '19.0.1.0.0',
    'summary': 'Event bus, capability registry, service locator, and billing ledger for MML modules',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mail', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

**Step 3: Run full mml_base test suite**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_base --stop-after-init
```
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add mml_base/hooks.py mml_base/__manifest__.py
git commit -m "feat(mml_base): add post_init and uninstall hooks — reference pattern for all modules"
```

---

## Phase 1 — Decouple `mml_freight` from `stock_3pl_core`

---

### Task 9: Add `mml_base` to `mml_freight` and remove `stock_3pl_core` dep

**Files:**
- Modify: `fowarder.intergration/addons/mml_freight/__manifest__.py`
- Create: `fowarder.intergration/addons/mml_freight/hooks.py`

**Context:** `mml_freight/models/freight_booking.py` lines 503–660 already guard all 3PL calls with `if '3pl.connector' not in self.env:`. The Python code is safe. We only need to remove the manifest dep and add the hook pattern.

**Step 1: Update manifest**

`fowarder.intergration/addons/mml_freight/__manifest__.py`:
```python
{
    'name': 'MML Freight Orchestration',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Freight tender, quote, booking and tracking for inbound POs',
    'author': 'MML',
    'license': 'OPL-1',
    'depends': [
        'mml_base',      # ← added
        'mail',
        'stock',
        'account',
        'purchase',
        'delivery',
        'stock_account',
        # 'stock_3pl_core' ← REMOVED (now optional via mml_freight_3pl bridge)
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/freight_carrier_contract_views.xml',
        'views/freight_carrier_views.xml',
        'views/freight_tender_views.xml',
        'views/freight_booking_views.xml',
        'views/purchase_order_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mml_freight/static/src/scss/freight_views.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

**Step 2: Write hooks**

`fowarder.intergration/addons/mml_freight/hooks.py`:
```python
def post_init_hook(env):
    env['mml.capability'].register([
        'freight.tender.create',
        'freight.booking.confirm',
        'freight.quote.request',
        'freight.booking.get_lead_time',
    ], module='mml_freight')


def uninstall_hook(env):
    env['mml.capability'].deregister_module('mml_freight')
    env['mml.registry'].deregister('freight')
    env['mml.event.subscription'].deregister_module('mml_freight')
```

**Step 3: Install mml_freight without stock_3pl_core and verify no crash**

```bash
odoo-bin -i mml_base,mml_freight -d testdb --stop-after-init
```
Expected: Installs cleanly with no ImportError or missing model errors.

**Step 4: Run mml_freight tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_freight --stop-after-init
```
Expected: All existing tests PASS (3PL tests should self-skip via existing `if '3pl.*' not in self.env:` guards).

**Step 5: Commit**

```bash
git add fowarder.intergration/addons/mml_freight/__manifest__.py fowarder.intergration/addons/mml_freight/hooks.py
git commit -m "feat(mml_freight): remove stock_3pl_core hard dep, add mml_base + hooks"
```

---

### Task 10: Add event emission to `freight_booking` and `freight_tender`

**Files:**
- Modify: `fowarder.intergration/addons/mml_freight/models/freight_booking.py`
- Modify: `fowarder.intergration/addons/mml_freight/models/freight_tender.py`

**Step 1: Identify the confirm action in freight_booking.py**

Read `fowarder.intergration/addons/mml_freight/models/freight_booking.py` — find the method that transitions to confirmed state (look for `state = 'confirmed'` write or `action_confirm`).

**Step 2: Add event emission on booking confirmation**

In the confirmation method, add after the state write:
```python
self.env['mml.event'].emit(
    'freight.booking.confirmed',
    quantity=1,
    billable_unit='freight_booking',
    res_model=self._name,
    res_id=self.id,
    source_module='mml_freight',
    payload={'booking_ref': self.name, 'carrier': self.carrier_id.name if self.carrier_id else ''},
)
```

**Step 3: Add event emission on tender creation**

In `freight_tender.py`, find the `create()` override or tender confirm method and add:
```python
self.env['mml.event'].emit(
    'freight.tender.created',
    quantity=1,
    billable_unit='freight_tender',
    res_model=self._name,
    res_id=self.id,
    source_module='mml_freight',
    payload={'tender_ref': self.name},
)
```

**Step 4: Run mml_freight tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_freight --stop-after-init
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add fowarder.intergration/addons/mml_freight/models/freight_booking.py fowarder.intergration/addons/mml_freight/models/freight_tender.py
git commit -m "feat(mml_freight): emit billable events on booking confirm and tender create"
```

---

### Task 11: Extract `FreightService` (service locator pattern)

**Files:**
- Create: `fowarder.intergration/addons/mml_freight/services/__init__.py`
- Create: `fowarder.intergration/addons/mml_freight/services/freight_service.py`
- Modify: `fowarder.intergration/addons/mml_freight/hooks.py`
- Create: `fowarder.intergration/addons/mml_freight/tests/test_freight_service.py`

**Step 1: Write failing test**

`fowarder.intergration/addons/mml_freight/tests/test_freight_service.py`:
```python
from odoo.tests.common import TransactionCase


class TestFreightService(TransactionCase):

    def test_service_registered_via_registry(self):
        """FreightService is accessible via the mml.registry service locator."""
        svc = self.env['mml.registry'].service('freight')
        # Should not be NullService if mml_freight is installed
        from odoo.addons.mml_base.services.null_service import NullService
        self.assertNotIsInstance(svc, NullService)

    def test_get_booking_lead_time_returns_none_for_missing(self):
        """get_booking_lead_time returns None for a non-existent booking ID."""
        svc = self.env['mml.registry'].service('freight')
        result = svc.get_booking_lead_time(999999)
        self.assertIsNone(result)
```

**Step 2: Write the service class**

`fowarder.intergration/addons/mml_freight/services/freight_service.py`:
```python
class FreightService:
    """
    Public API for mml_freight. Retrieved via:
        svc = self.env['mml.registry'].service('freight')
    Returns NullService if mml_freight is not installed.
    """

    def __init__(self, env):
        self.env = env

    def create_tender(self, vals: dict) -> int | None:
        """Create a freight.tender. Returns the new tender's ID."""
        tender = self.env['freight.tender'].create(vals)
        return tender.id

    def get_booking_lead_time(self, booking_id: int) -> int | None:
        """Return transit_days_actual for a confirmed freight.booking, or None."""
        booking = self.env['freight.booking'].browse(booking_id)
        if not booking.exists():
            return None
        return getattr(booking, 'transit_days_actual', None)
```

**Step 3: Register service in hooks**

Update `fowarder.intergration/addons/mml_freight/hooks.py`:
```python
def post_init_hook(env):
    from odoo.addons.mml_freight.services.freight_service import FreightService
    env['mml.capability'].register([
        'freight.tender.create',
        'freight.booking.confirm',
        'freight.quote.request',
        'freight.booking.get_lead_time',
    ], module='mml_freight')
    env['mml.registry'].register('freight', FreightService)
```

**Step 4: Run tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_freight --stop-after-init
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add fowarder.intergration/addons/mml_freight/services/ fowarder.intergration/addons/mml_freight/hooks.py fowarder.intergration/addons/mml_freight/tests/test_freight_service.py
git commit -m "feat(mml_freight): add FreightService + register with service locator"
```

---

### Task 12: Add `mml_base` to `stock_3pl_core` and wire capabilities

**Files:**
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_core/__manifest__.py`
- Create: `mainfreight.3pl.intergration/addons/stock_3pl_core/hooks.py`

**Step 1: Update manifest**

`mainfreight.3pl.intergration/addons/stock_3pl_core/__manifest__.py` — add `'mml_base'` to `depends` and `post_init_hook`/`uninstall_hook`.

**Step 2: Write hooks**

`mainfreight.3pl.intergration/addons/stock_3pl_core/hooks.py`:
```python
def post_init_hook(env):
    from odoo.addons.stock_3pl_core.services.tpl_service import TPLService
    env['mml.capability'].register([
        '3pl.message.queue',
        '3pl.connector.get',
        '3pl.inbound.create',
    ], module='stock_3pl_core')
    env['mml.registry'].register('3pl', TPLService)


def uninstall_hook(env):
    env['mml.capability'].deregister_module('stock_3pl_core')
    env['mml.registry'].deregister('3pl')
    env['mml.event.subscription'].deregister_module('stock_3pl_core')
```

**Step 3: Create minimal `TPLService`**

`mainfreight.3pl.intergration/addons/stock_3pl_core/services/tpl_service.py`:
```python
class TPLService:
    def __init__(self, env):
        self.env = env

    def queue_inward_order(self, purchase_order_id: int, connector_id: int | None = None) -> int | None:
        """Queue an inward order 3pl.message for the given PO. Returns message ID."""
        po = self.env['purchase.order'].browse(purchase_order_id)
        if not po.exists():
            return None
        # Delegate to existing 3pl.message.create logic
        msg = self.env['3pl.message'].create({
            'document_type': 'inward_order',
            'res_model': 'purchase.order',
            'res_id': po.id,
        })
        return msg.id
```

**Step 4: Run stock_3pl_core tests**

```bash
python -m pytest mainfreight.3pl.intergration/ -m "not odoo_integration" -q
```
Expected: All pure-Python tests PASS.

**Step 5: Commit**

```bash
git add mainfreight.3pl.intergration/addons/stock_3pl_core/__manifest__.py mainfreight.3pl.intergration/addons/stock_3pl_core/hooks.py mainfreight.3pl.intergration/addons/stock_3pl_core/services/
git commit -m "feat(stock_3pl_core): add mml_base dep, capabilities, TPLService"
```

---

## Phase 2 — Decouple `mml_roq_forecast` from `mml_freight`

---

### Task 13: Remove `mml_freight` manifest dep and delete `freight_tender_ext.py`

**Files:**
- Modify: `roq.model/mml_roq_forecast/__manifest__.py`
- Delete: `roq.model/mml_roq_forecast/models/freight_tender_ext.py`
- Modify: `roq.model/mml_roq_forecast/models/__init__.py`

**Context:** `freight_tender_ext.py` contains `_inherit = 'freight.tender'` to add `shipment_group_id`. This field moves to the `mml_roq_freight` bridge in Phase 4. Deleting it here means ROQ installs without freight, but the field doesn't exist until the bridge is installed — which is correct behaviour.

**Step 1: Update manifest**

`roq.model/mml_roq_forecast/__manifest__.py` — change `depends`:
```python
'depends': [
    'mml_base',          # ← added
    'base', 'sale', 'purchase', 'stock',
    'stock_landed_costs',
    # 'mml_freight' ← REMOVED
],
```

**Step 2: Remove freight_tender_ext from `__init__.py`**

`roq.model/mml_roq_forecast/models/__init__.py` — remove the `from . import freight_tender_ext` line.

**Step 3: Delete the file**

```bash
git rm roq.model/mml_roq_forecast/models/freight_tender_ext.py
git rm roq.model/mml_roq_forecast/tests/test_freight_tender_ext.py
```

**Step 4: Remove freight field from `roq_shipment_group.py`**

Read `roq.model/mml_roq_forecast/models/roq_shipment_group.py`. Find and remove:
- Line 52: `fields.Many2one('freight.tender', ...)` — delete this field definition entirely
- Line 99: `self.env['freight.tender'].create({...})` — replace with service locator call:

```python
# Before (line 99 area):
tender = self.env['freight.tender'].create({...})

# After:
svc = self.env['mml.registry'].service('freight')
tender_id = svc.create_tender({...})
# tender_id is None if mml_freight not installed — handled gracefully
```

**Step 5: Fix `res_partner_ext.py` freight.booking references**

Read `roq.model/mml_roq_forecast/models/res_partner_ext.py` lines 102–127. Replace direct env access with service locator:

```python
# Before:
if hasattr(self.env['freight.booking'], 'transit_days_actual'):
    bookings = self.env['freight.booking'].sudo().search([...])

# After:
svc = self.env['mml.registry'].service('freight')
transit_days = svc.get_booking_lead_time(booking_id)
```

**Step 6: Install mml_roq_forecast alone and verify no crash**

```bash
odoo-bin -i mml_base,mml_roq_forecast -d testdb --stop-after-init
```
Expected: Installs cleanly.

**Step 7: Commit**

```bash
git add roq.model/mml_roq_forecast/__manifest__.py roq.model/mml_roq_forecast/models/__init__.py roq.model/mml_roq_forecast/models/roq_shipment_group.py roq.model/mml_roq_forecast/models/res_partner_ext.py
git commit -m "feat(mml_roq_forecast): remove mml_freight hard dep, use service locator"
```

---

### Task 14: Wire `mml_roq_forecast` capabilities + ROQService

**Files:**
- Create: `roq.model/mml_roq_forecast/hooks.py`
- Create: `roq.model/mml_roq_forecast/services/roq_service.py`
- Modify: `roq.model/mml_roq_forecast/__manifest__.py`

**Step 1: Write ROQService**

`roq.model/mml_roq_forecast/services/roq_service.py`:
```python
class ROQService:
    """Public API for mml_roq_forecast. Retrieved via mml.registry.service('roq')."""

    def __init__(self, env):
        self.env = env

    def on_freight_booking_confirmed(self, event) -> None:
        """
        Called by mml_roq_freight bridge when a freight booking is confirmed.
        Updates lead time feedback on the related supplier.
        """
        import json
        payload = json.loads(event.payload_json or '{}')
        booking_id = event.res_id
        if not booking_id:
            return
        svc = self.env['mml.registry'].service('freight')
        transit_days = svc.get_booking_lead_time(booking_id)
        if transit_days is None:
            return
        # Update lead time history — implementation delegates to existing service layer
        self.env['roq.forecast.run']._update_supplier_lead_time_feedback(
            booking_id=booking_id,
            transit_days=transit_days,
        )
```

**Step 2: Write hooks**

`roq.model/mml_roq_forecast/hooks.py`:
```python
def post_init_hook(env):
    from odoo.addons.mml_roq_forecast.services.roq_service import ROQService
    env['mml.capability'].register([
        'roq.forecast.run',
        'roq.shipment_group.create',
        'roq.po.raise',
    ], module='mml_roq_forecast')
    env['mml.registry'].register('roq', ROQService)


def uninstall_hook(env):
    env['mml.capability'].deregister_module('mml_roq_forecast')
    env['mml.registry'].deregister('roq')
    env['mml.event.subscription'].deregister_module('mml_roq_forecast')
```

**Step 3: Wire hooks into manifest**

Add `'post_init_hook': 'post_init_hook', 'uninstall_hook': 'uninstall_hook'` to manifest.

**Step 4: Run mml_roq_forecast tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_roq_forecast --stop-after-init
```
Expected: All tests PASS (removed tests for freight_tender_ext are gone).

**Step 5: Commit**

```bash
git add roq.model/mml_roq_forecast/hooks.py roq.model/mml_roq_forecast/services/ roq.model/mml_roq_forecast/__manifest__.py
git commit -m "feat(mml_roq_forecast): add ROQService + register capabilities and hooks"
```

---

### Task 15: Add event emission to `mml_roq_forecast`

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_forecast_run.py`
- Modify: `roq.model/mml_roq_forecast/models/roq_shipment_group.py`

**Step 1: Emit on forecast run**

In `roq_forecast_run.py`, find the method that completes a run (likely `action_run` or `_execute_run`). Add after successful completion:
```python
self.env['mml.event'].emit(
    'roq.forecast.run',
    quantity=1,
    billable_unit='roq_run',
    res_model=self._name,
    res_id=self.id,
    source_module='mml_roq_forecast',
    payload={'run_ref': self.name, 'sku_count': len(self.line_ids)},
)
```

**Step 2: Emit on shipment group confirmed**

In `roq_shipment_group.py`, find the confirm/consolidate action. Add:
```python
self.env['mml.event'].emit(
    'roq.shipment_group.confirmed',
    quantity=1,
    billable_unit='roq_po_line',
    res_model=self._name,
    res_id=self.id,
    source_module='mml_roq_forecast',
    payload={'group_ref': self.name},
)
```

**Step 3: Run tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_roq_forecast --stop-after-init
```
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_forecast_run.py roq.model/mml_roq_forecast/models/roq_shipment_group.py
git commit -m "feat(mml_roq_forecast): emit billable events on run and shipment group confirm"
```

---

## Phase 3 — Wire remaining modules to `mml_base`

---

### Task 16: Wire `mml_edi` to `mml_base`

**Files:**
- Modify: `briscoes.edi/mml.edi/__manifest__.py`
- Create: `briscoes.edi/mml.edi/hooks.py`
- Create: `briscoes.edi/mml.edi/services/edi_service.py`
- Modify relevant model files for event emission

**Step 1: Update manifest** — add `'mml_base'` to `depends`, add hooks keys.

**Step 2: Write hooks**

`briscoes.edi/mml.edi/hooks.py`:
```python
def post_init_hook(env):
    from odoo.addons.mml_edi.services.edi_service import EDIService
    env['mml.capability'].register([
        'edi.order.process',
        'edi.asn.send',
        'edi.invoice.send',
    ], module='mml_edi')
    env['mml.registry'].register('edi', EDIService)


def uninstall_hook(env):
    env['mml.capability'].deregister_module('mml_edi')
    env['mml.registry'].deregister('edi')
    env['mml.event.subscription'].deregister_module('mml_edi')
```

**Step 3: Create minimal `EDIService`**

`briscoes.edi/mml.edi/services/edi_service.py`:
```python
class EDIService:
    def __init__(self, env):
        self.env = env

    def on_3pl_despatch_confirmed(self, event) -> None:
        """Trigger ASN send when Mainfreight confirms despatch."""
        # Implementation: find EDI-enabled SO, send ASN
        pass  # Stub — implement when 3PL↔EDI bridge is built
```

**Step 4: Add event emission in EDI order processing**

Find the method in `mml_edi` that marks an EDI order as processed and add:
```python
self.env['mml.event'].emit(
    'edi.order.processed',
    quantity=len(self.line_ids),
    billable_unit='edi_order_line',
    res_model=self._name,
    res_id=self.id,
    source_module='mml_edi',
    payload={'partner': self.partner_id.name, 'order_ref': self.name},
)
```

**Step 5: Run mml_edi tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_edi --stop-after-init
```
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add briscoes.edi/mml.edi/__manifest__.py briscoes.edi/mml.edi/hooks.py briscoes.edi/mml.edi/services/
git commit -m "feat(mml_edi): add mml_base dep, capabilities, EDIService, billable events"
```

---

## Phase 4 — Schema Bridge Modules

---

### Task 17: Scaffold `mml_roq_freight` bridge

**Files:**
- Create: `mml_roq_freight/__manifest__.py`
- Create: `mml_roq_freight/__init__.py`
- Create: `mml_roq_freight/models/__init__.py`
- Create: `mml_roq_freight/models/roq_shipment_group_freight.py`
- Create: `mml_roq_freight/models/freight_tender_roq.py`
- Create: `mml_roq_freight/hooks.py`
- Create: `mml_roq_freight/security/ir.model.access.csv`
- Create: `mml_roq_freight/tests/test_bridge.py`

**Step 1: Write manifest**

`mml_roq_freight/__manifest__.py`:
```python
{
    'name': 'MML ROQ ↔ Freight Bridge',
    'version': '19.0.1.0.0',
    'summary': 'Connects mml_roq_forecast and mml_freight when both are installed',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mml_roq_forecast', 'mml_freight'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': True,   # installs automatically when both deps are present
    'application': False,
}
```

**Step 2: Write schema — freight_tender field on shipment group**

`mml_roq_freight/models/roq_shipment_group_freight.py`:
```python
from odoo import fields, models


class RoqShipmentGroupFreight(models.Model):
    _inherit = 'roq.shipment.group'

    freight_tender_id = fields.Many2one(
        'freight.tender',
        string='Freight Tender',
        ondelete='set null',
    )
```

**Step 3: Write schema — shipment_group field on freight.tender**

`mml_roq_freight/models/freight_tender_roq.py`:
```python
from odoo import fields, models


class FreightTenderROQ(models.Model):
    _inherit = 'freight.tender'

    shipment_group_id = fields.Many2one(
        'roq.shipment.group',
        string='ROQ Shipment Group',
        ondelete='set null',
    )
```

**Step 4: Write hooks — register subscriptions**

`mml_roq_freight/hooks.py`:
```python
def post_init_hook(env):
    # When a ROQ shipment group is confirmed, create a freight tender
    env['mml.event.subscription'].register(
        event_type='roq.shipment_group.confirmed',
        handler_model='mml.freight.service',
        handler_method='on_shipment_group_confirmed',
        module='mml_roq_freight',
    )
    # When a freight booking is confirmed, feed back lead time to ROQ
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='roq.service',
        handler_method='on_freight_booking_confirmed',
        module='mml_roq_freight',
    )


def uninstall_hook(env):
    env['mml.event.subscription'].deregister_module('mml_roq_freight')
```

**Step 5: Write bridge tests**

`mml_roq_freight/tests/test_bridge.py`:
```python
from odoo.tests.common import TransactionCase


class TestROQFreightBridge(TransactionCase):

    def test_freight_tender_field_on_shipment_group(self):
        """freight_tender_id field exists on roq.shipment.group when bridge installed."""
        self.assertIn('freight_tender_id', self.env['roq.shipment.group']._fields)

    def test_shipment_group_field_on_freight_tender(self):
        """shipment_group_id field exists on freight.tender when bridge installed."""
        self.assertIn('shipment_group_id', self.env['freight.tender']._fields)

    def test_subscriptions_registered(self):
        """Bridge event subscriptions are registered on install."""
        subs = self.env['mml.event.subscription'].search([
            ('module', '=', 'mml_roq_freight'),
        ])
        event_types = subs.mapped('event_type')
        self.assertIn('roq.shipment_group.confirmed', event_types)
        self.assertIn('freight.booking.confirmed', event_types)
```

**Step 6: Run bridge tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_roq_freight --stop-after-init
```
Expected: 3 PASS.

**Step 7: Commit**

```bash
git add mml_roq_freight/
git commit -m "feat(mml_roq_freight): add ROQ↔Freight schema bridge with auto_install"
```

---

### Task 18: Scaffold `mml_freight_3pl` bridge

**Files:**
- Create: `mml_freight_3pl/__manifest__.py`
- Create: `mml_freight_3pl/__init__.py`
- Create: `mml_freight_3pl/hooks.py`
- Create: `mml_freight_3pl/tests/test_bridge.py`

**Step 1: Write manifest**

`mml_freight_3pl/__manifest__.py`:
```python
{
    'name': 'MML Freight ↔ 3PL Bridge',
    'version': '19.0.1.0.0',
    'summary': 'Connects mml_freight and stock_3pl_core when both are installed',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mml_freight', 'stock_3pl_core'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': True,
    'application': False,
}
```

**Step 2: Write hooks — register subscriptions**

`mml_freight_3pl/hooks.py`:
```python
def post_init_hook(env):
    # When a freight booking is confirmed, queue a 3PL inward order
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='mml.3pl.bridge',
        handler_method='on_freight_booking_confirmed',
        module='mml_freight_3pl',
    )


def uninstall_hook(env):
    env['mml.event.subscription'].deregister_module('mml_freight_3pl')
```

**Step 3: Write the bridge handler model**

`mml_freight_3pl/models/mml_3pl_bridge.py`:
```python
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class Mml3plBridge(models.AbstractModel):
    _name = 'mml.3pl.bridge'
    _description = 'MML Freight ↔ 3PL Event Handlers'

    @api.model
    def on_freight_booking_confirmed(self, event) -> None:
        """Queue a 3PL inward order when a freight booking is confirmed."""
        booking = self.env['freight.booking'].browse(event.res_id)
        if not booking.exists() or not booking.purchase_id:
            return
        svc = self.env['mml.registry'].service('3pl')
        msg_id = svc.queue_inward_order(booking.purchase_id.id)
        if msg_id:
            _logger.info(
                'mml_freight_3pl: queued 3pl.message %s for booking %s',
                msg_id, booking.name,
            )
        # Emit event for audit trail
        self.env['mml.event'].emit(
            '3pl.inbound.queued',
            quantity=1,
            billable_unit='3pl_receipt',
            res_model='purchase.order',
            res_id=booking.purchase_id.id,
            source_module='mml_freight_3pl',
        )
```

**Step 4: Write bridge tests**

`mml_freight_3pl/tests/test_bridge.py`:
```python
from odoo.tests.common import TransactionCase


class TestFreight3PLBridge(TransactionCase):

    def test_subscriptions_registered(self):
        """Bridge subscription is registered on install."""
        subs = self.env['mml.event.subscription'].search([
            ('module', '=', 'mml_freight_3pl'),
            ('event_type', '=', 'freight.booking.confirmed'),
        ])
        self.assertEqual(len(subs), 1)

    def test_bridge_handler_model_exists(self):
        """mml.3pl.bridge model is accessible."""
        self.assertIsNotNone(self.env.get('mml.3pl.bridge'))
```

**Step 5: Create `__init__.py` and models `__init__.py`**

```python
# mml_freight_3pl/__init__.py
from . import models

# mml_freight_3pl/models/__init__.py
from . import mml_3pl_bridge
```

**Step 6: Run bridge tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_freight_3pl --stop-after-init
```
Expected: 2 PASS.

**Step 7: Run full integration smoke test — all modules together**

```bash
odoo-bin -i mml_base,mml_roq_forecast,mml_freight,stock_3pl_core,stock_3pl_mainfreight,mml_edi,mml_roq_freight,mml_freight_3pl -d testdb --stop-after-init
```
Expected: All install cleanly. `mml_roq_freight` and `mml_freight_3pl` auto-install when deps are present.

**Step 8: Run all tests**

```bash
odoo-bin --test-enable -d testdb --test-tags mml_base,mml_roq_forecast,mml_freight,stock_3pl_core,mml_edi,mml_roq_freight,mml_freight_3pl --stop-after-init
```
Expected: All tests PASS.

**Step 9: Commit**

```bash
git add mml_freight_3pl/
git commit -m "feat(mml_freight_3pl): add Freight↔3PL schema bridge with auto_install"
```

---

## Final Verification

### Smoke test: install each module independently

```bash
# ROQ alone
odoo-bin -i mml_base,mml_roq_forecast -d testdb_roq --stop-after-init

# Freight alone
odoo-bin -i mml_base,mml_freight -d testdb_freight --stop-after-init

# 3PL alone
odoo-bin -i mml_base,stock_3pl_core,stock_3pl_mainfreight -d testdb_3pl --stop-after-init

# EDI alone
odoo-bin -i mml_base,mml_edi -d testdb_edi --stop-after-init

# ROQ + Freight (bridge auto-installs)
odoo-bin -i mml_base,mml_roq_forecast,mml_freight -d testdb_roq_freight --stop-after-init

# Full stack
odoo-bin -i mml_base,mml_roq_forecast,mml_freight,stock_3pl_core,stock_3pl_mainfreight,mml_edi -d testdb_full --stop-after-init
```

Each must install cleanly with no errors.

### Verify event ledger populates

In a running Odoo instance with the full stack, confirm a freight booking and verify:
- `mml.event` has a record with `event_type = 'freight.booking.confirmed'`
- `synced_to_platform = False` (platform stub is no-op)
- `company_id` is set correctly

---

## Module Location Summary

```
mml.odoo.apps/
  mml_base/                             ← NEW — Phase 0
  mml_roq_freight/                      ← NEW — Phase 4 bridge
  mml_freight_3pl/                      ← NEW — Phase 4 bridge
  roq.model/mml_roq_forecast/           ← MODIFIED — Phase 2
  fowarder.intergration/addons/mml_freight/    ← MODIFIED — Phase 1
  mainfreight.3pl.intergration/addons/stock_3pl_core/  ← MODIFIED — Phase 1
  briscoes.edi/mml.edi/                 ← MODIFIED — Phase 3
  docs/plans/                           ← Design + this plan
```
