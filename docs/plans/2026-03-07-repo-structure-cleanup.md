# Repo Structure Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync all CLAUDE.md files and dev docs with the actual `mml.*` directory layout, fix known code issues, and scaffold the missing test infrastructure for `mml.forecasting/`.

**Architecture:** Three independent streams: (1) docs-only updates to CLAUDE.md files; (2) one-line code fix in `freight_booking.py`; (3) new `conftest.py` + `pytest.ini` for the forecasting workspace.

**Tech Stack:** Python, pytest, Odoo 19 stub pattern (mirrors existing workspaces).

---

## Context

The repo directories were renamed from the old layout (`barcodes/`, `fowarder.intergration/`, `mainfreight.3pl.intergration/`, `roq.model/`, `briscoes.edi/`) to `mml.*`-prefixed names (`mml.barcodes/`, `mml.fowarder.intergration/`, `mml.3pl.intergration/`, `mml.roq.model/`, `mml.edi/`). The root `CLAUDE.md` still uses the old names. Additionally:

- `freight_booking.py:action_confirm()` has a **redundant** `for booking in self:` loop that was left over from before `ensure_one()` was added (line 183). The function already guards with `ensure_one()` so the loop iterates exactly once. It is harmless but misleading — the Known Issues entry in multiple CLAUDE.md files and MEMORY.md still flags it as an active bug.
- `mml.forecasting/` has no `conftest.py` or `pytest.ini`, so pure-Python tests cannot run from the workspace directory (Odoo stubs are not installed).

---

## Task 1: Update root CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (repo root)

**Step 1: Replace the directory map**

Replace the entire `## Actual Directory Structure` block with:

```markdown
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
├── mml.edi/                             ← EDI engine (Odoo module) + legacy .NET binaries
│   └── mml_edi/                         ← mml_edi Odoo module (module root is mml.edi/ itself)
├── mml.barcodes/
│   └── mml_barcode_registry/            ← Barcode registry module
└── mml.forecasting/
    ├── mml_forecast_core/               ← Core forecasting engine
    └── mml_forecast_financial/          ← Financial forecasting layer
```

**Note on typos:** `mml.fowarder.intergration` and `mml.3pl.intergration` are intentional directory names (typos preserved from original repo history).
```

**Step 2: Update the Development Commands section**

Replace the `## Development Commands` block with:

```markdown
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
```

**Step 3: Update the Test Infrastructure section**

In the paragraph starting "Each workspace", replace old path names:

Old: `Each workspace (\`fowarder.intergration/\`, \`mainfreight.3pl.intergration/\`, \`roq.model/\`, \`briscoes.edi/\`) has its own \`pytest.ini\``

New: `Each workspace (\`mml.fowarder.intergration/\`, \`mml.3pl.intergration/\`, \`mml.roq.model/\`, \`mml.edi/\`, \`mml.forecasting/\`) has its own \`pytest.ini\` with the same marker definition so tests can be run from within that workspace directory.`

**Step 4: Remove the Known Issues entry for freight_booking**

The `action_confirm()` issue is no longer a bug — `ensure_one()` is present and there is no multi-record risk. Remove the entire `### Known Issues / Backlog` section (or replace with a blank section if more items exist in future).

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE.md): update directory map and dev commands for mml.* rename"
```

---

## Task 2: Clean up redundant loop in `action_confirm()`

**Files:**
- Modify: `mml.fowarder.intergration/addons/mml_freight/models/freight_booking.py:182-200`

**Background:**

Current code (lines 182–200):
```python
def action_confirm(self):
    self.ensure_one()
    self.write({'state': 'confirmed'})
    for booking in self:          # <- redundant: ensure_one() means self is always len=1
        self.env['mml.event'].emit(
            'freight.booking.confirmed',
            quantity=1,
            billable_unit='freight_booking',
            res_model=booking._name,
            res_id=booking.id,
            source_module='mml_freight',
            payload={
                'booking_ref': booking.name,
                'carrier': booking.carrier_id.name if booking.carrier_id else '',
            },
        )
    self._queue_3pl_inward_order()
    self._build_inward_order_payload()
    return True
```

After `ensure_one()`, iterating `for booking in self` runs exactly once, with `booking is self`. The loop adds no value and misleads readers into thinking it can handle multiple records.

**Step 1: Remove the loop, use `self` directly**

Replace `action_confirm()` with:

```python
def action_confirm(self):
    self.ensure_one()
    self.write({'state': 'confirmed'})
    self.env['mml.event'].emit(
        'freight.booking.confirmed',
        quantity=1,
        billable_unit='freight_booking',
        res_model=self._name,
        res_id=self.id,
        source_module='mml_freight',
        payload={
            'booking_ref': self.name,
            'carrier': self.carrier_id.name if self.carrier_id else '',
        },
    )
    self._queue_3pl_inward_order()
    self._build_inward_order_payload()
    return True
```

**Step 2: Verify existing tests still pass**

```bash
pytest mml.fowarder.intergration/addons/mml_freight/tests/test_3pl_handoff.py -q
```

Expected: all pure-Python tests PASS (Odoo integration tests skipped).

**Step 3: Update `mml.fowarder.intergration/CLAUDE.md`**

In the `## Key Gotchas` section, replace the `action_confirm()` entry:

Old:
```
- **`action_confirm()` has a redundant loop**: it calls `ensure_one()` then iterates `for booking in self`. The `_build_inward_order_payload()` call also has `ensure_one()`. This is safe but redundant — the loop never processes more than one record.
```

New: *(remove this entry entirely — it was cleaned up)*

**Step 4: Update `mml.3pl.intergration/CLAUDE.md`**

In `## Known Issues / Backlog`, remove the entry:
```
- `freight_booking.py` `action_confirm()` operates on a recordset but calls `_build_inward_order_payload()` which calls `ensure_one()` internally — will raise `ValueError` if called on >1 record
```

**Step 5: Commit**

```bash
git add mml.fowarder.intergration/addons/mml_freight/models/freight_booking.py \
        mml.fowarder.intergration/CLAUDE.md \
        mml.3pl.intergration/CLAUDE.md
git commit -m "fix(mml_freight): remove redundant loop in action_confirm(); update CLAUDE.md entries"
```

---

## Task 3: Scaffold `mml.forecasting/` test infrastructure

**Files:**
- Create: `mml.forecasting/conftest.py`
- Create: `mml.forecasting/pytest.ini`
- Modify: `mml.forecasting/CLAUDE.md`

**Step 1: Create `mml.forecasting/pytest.ini`**

```ini
[pytest]
markers =
    odoo_integration: marks tests that require a live Odoo database (deselect with -m "not odoo_integration")
addopts = -p no:warnings
```

**Step 2: Create `mml.forecasting/conftest.py`**

Model: `mml.roq.model/conftest.py` (self-contained stub installer + addon registration).

```python
# conftest.py — mml.forecasting
#
# Self-contained Odoo stub installer for the mml.forecasting workspace.
# Mirrors the pattern in mml.roq.model/conftest.py.
#
# Installs lightweight odoo.* stubs so pure-Python structural tests can
# import model classes without a running Odoo instance.
#
# Registers mml_forecast_core and mml_forecast_financial into sys.modules
# under both their short names and odoo.addons.* so intra-addon imports resolve.

import sys
import types
import pathlib
import pytest

_ROOT = pathlib.Path(__file__).parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _install_odoo_stubs():
    """Build and register lightweight odoo stubs in sys.modules (idempotent)."""
    if 'odoo' in sys.modules and hasattr(sys.modules['odoo'], '_stubbed'):
        return

    # ---- odoo.fields ----
    odoo_fields = types.ModuleType('odoo.fields')

    class _BaseField:
        def __init__(self, *args, **kwargs):
            self._kwargs = kwargs
            self.default = kwargs.get('default')
            self.string = args[0] if args else kwargs.get('string', '')

        def __set_name__(self, owner, name):
            self._attr_name = name
            if '_fields_meta' not in owner.__dict__:
                owner._fields_meta = {}
            owner._fields_meta[name] = self

    class Selection(_BaseField):
        def __init__(self, selection=None, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.selection = selection or []

    for _name in ('Boolean', 'Char', 'Date', 'Float', 'Integer', 'Text',
                   'Html', 'Binary', 'Json', 'Many2one', 'One2many', 'Many2many'):
        setattr(odoo_fields, _name, type(_name, (_BaseField,), {}))

    class Datetime(_BaseField):
        @classmethod
        def now(cls):
            import datetime
            return datetime.datetime.utcnow()

    odoo_fields.Selection = Selection
    odoo_fields.Datetime = Datetime

    # ---- odoo.models ----
    odoo_models = types.ModuleType('odoo.models')

    class Model:
        _inherit = None
        _name = None
        _fields_meta = {}
        def write(self, vals): pass
        def ensure_one(self): pass
        def search(self, domain, **kwargs): return []
        def sudo(self): return self
        def create(self, vals): pass

    class AbstractModel(Model): pass
    class TransientModel(Model): pass

    odoo_models.Model = Model
    odoo_models.AbstractModel = AbstractModel
    odoo_models.TransientModel = TransientModel

    # ---- odoo.api ----
    odoo_api = types.ModuleType('odoo.api')
    odoo_api.model = lambda f: f
    odoo_api.depends = lambda *args: (lambda f: f)
    odoo_api.constrains = lambda *args: (lambda f: f)
    odoo_api.onchange = lambda *args: (lambda f: f)
    odoo_api.model_create_multi = lambda f: f

    # ---- odoo.exceptions ----
    odoo_exceptions = types.ModuleType('odoo.exceptions')
    class ValidationError(Exception): pass
    class UserError(Exception): pass
    odoo_exceptions.ValidationError = ValidationError
    odoo_exceptions.UserError = UserError

    # ---- odoo.tests ----
    import unittest
    odoo_tests = types.ModuleType('odoo.tests')
    class TransactionCase(unittest.TestCase):
        """Stub: self.env NOT available without Odoo."""
    def tagged(*args):
        def decorator(cls): return cls
        return decorator
    odoo_tests.TransactionCase = TransactionCase
    odoo_tests.tagged = tagged

    odoo_tests_common = types.ModuleType('odoo.tests.common')
    odoo_tests_common.TransactionCase = TransactionCase

    # ---- odoo.http ----
    odoo_http = types.ModuleType('odoo.http')
    odoo_http.Controller = type('Controller', (), {})
    odoo_http.route = lambda *a, **kw: (lambda f: f)
    odoo_http.request = None

    # ---- odoo root ----
    odoo = types.ModuleType('odoo')
    odoo._stubbed = True
    odoo._ = lambda s: s
    odoo.models = odoo_models
    odoo.fields = odoo_fields
    odoo.api = odoo_api
    odoo.exceptions = odoo_exceptions
    odoo.tests = odoo_tests
    odoo.http = odoo_http

    sys.modules['odoo'] = odoo
    sys.modules['odoo.models'] = odoo_models
    sys.modules['odoo.fields'] = odoo_fields
    sys.modules['odoo.api'] = odoo_api
    sys.modules['odoo.exceptions'] = odoo_exceptions
    sys.modules['odoo.tests'] = odoo_tests
    sys.modules['odoo.tests.common'] = odoo_tests_common
    sys.modules['odoo.http'] = odoo_http

    odoo_addons = types.ModuleType('odoo.addons')
    sys.modules['odoo.addons'] = odoo_addons
    odoo.addons = odoo_addons

    # Register mml_forecast_core and mml_forecast_financial
    for addon_name in ('mml_forecast_core', 'mml_forecast_financial'):
        addon_path = _ROOT / addon_name
        full_name = f'odoo.addons.{addon_name}'
        if full_name not in sys.modules:
            pkg = types.ModuleType(full_name)
            pkg.__path__ = [str(addon_path)]
            pkg.__package__ = full_name
            sys.modules[full_name] = pkg
            if addon_name not in sys.modules:
                sys.modules[addon_name] = pkg
            setattr(odoo_addons, addon_name, pkg)
        for sub in ('models', 'services', 'wizard'):
            sub_full = f'{full_name}.{sub}'
            if sub_full not in sys.modules:
                sub_pkg = types.ModuleType(sub_full)
                sub_pkg.__path__ = [str(addon_path / sub)]
                sub_pkg.__package__ = sub_full
                sys.modules[sub_full] = sub_pkg


_install_odoo_stubs()


def pytest_collection_modifyitems(config, items):
    """Auto-mark TransactionCase tests as odoo_integration (requires odoo-bin)."""
    from odoo.tests import TransactionCase
    for item in items:
        if isinstance(item, pytest.Class):
            continue
        cls = getattr(item, 'cls', None)
        if cls is not None and issubclass(cls, TransactionCase):
            item.add_marker(pytest.mark.odoo_integration)
```

**Step 3: Verify conftest loads cleanly**

```bash
cd mml.forecasting
pytest --collect-only -q
```

Expected: `no tests ran` (no pure-Python tests exist yet) with no import errors.

**Step 4: Update `mml.forecasting/CLAUDE.md`**

In the `## Running Tests` section, replace:

Old:
```
There is no `conftest.py` or `pytest.ini` in this repo yet. All current tests are Odoo integration tests (`TransactionCase`) and require a live Odoo database:
```

New:
```
Pure-Python tests (when added) can run without Odoo from the workspace root:

```bash
pytest -m "not odoo_integration" -q
```

All current tests are Odoo integration tests (`TransactionCase`) and require a live Odoo database:
```

Remove the note at the bottom of the Running Tests section:
```
The parent repo's pure-Python stub pattern ... is not yet set up here. When adding pure-Python tests, follow the parent repo's two-tier test strategy...
```
(This is now done — delete that paragraph.)

**Step 5: Commit**

```bash
git add mml.forecasting/conftest.py mml.forecasting/pytest.ini mml.forecasting/CLAUDE.md
git commit -m "feat(mml.forecasting): scaffold pure-Python test tier (conftest + pytest.ini)"
```

---

## Task 4: Retire stale known-issue entries in MEMORY.md

**Files:**
- Modify: `C:\Users\jpwmc\.claude\projects\E--ClaudeCode-projects-mml-odoo-apps\memory\MEMORY.md`

**Step 1: Update MEMORY.md**

In `## Remaining Backlog`, remove the `freight_booking.py` entry (it's been fixed). If the backlog section becomes empty after removal, remove the section heading too.

**Step 2: No commit needed** — MEMORY.md is outside the git repo.

---

## Execution Order

Tasks 1, 2, 3 are independent and can be done in parallel. Task 4 is a cleanup step, do it last.

Recommended order: 1 → 2 → 3 → 4 (shortest path to clean state).
