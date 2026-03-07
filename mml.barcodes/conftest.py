# conftest.py — mml.barcodes
#
# Self-contained: installs Odoo stubs and registers mml_barcode_registry
# under odoo.addons so that absolute imports like
#   from odoo.addons.mml_barcode_registry.services.gs1 import ...
# resolve correctly during pure-Python test collection.
#
# All barcode tests are Odoo integration tests (TransactionCase) and will be
# auto-marked odoo_integration and skipped under plain pytest.

import sys
import types
import pathlib
import pytest

_ROOT = pathlib.Path(__file__).parent
_ADDON = _ROOT / 'mml_barcode_registry'


def _install_odoo_stubs():
    """Install minimal odoo.* stubs (idempotent)."""
    if 'odoo' in sys.modules and hasattr(sys.modules['odoo'], '_stubbed'):
        return

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

    class Datetime(_BaseField):
        @classmethod
        def now(cls):
            import datetime
            return datetime.datetime.utcnow()

    for _n in ('Boolean', 'Char', 'Date', 'Float', 'Integer', 'Text',
               'Html', 'Binary', 'Json', 'Many2one', 'One2many', 'Many2many'):
        setattr(odoo_fields, _n, type(_n, (_BaseField,), {}))
    odoo_fields.Selection = Selection
    odoo_fields.Datetime = Datetime

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

    odoo_api = types.ModuleType('odoo.api')
    odoo_api.model = lambda f: f
    odoo_api.depends = lambda *args: (lambda f: f)
    odoo_api.constrains = lambda *args: (lambda f: f)
    odoo_api.onchange = lambda *args: (lambda f: f)
    odoo_api.model_create_multi = lambda f: f

    odoo_exceptions = types.ModuleType('odoo.exceptions')
    class ValidationError(Exception): pass
    class UserError(Exception): pass
    odoo_exceptions.ValidationError = ValidationError
    odoo_exceptions.UserError = UserError

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

    odoo_http = types.ModuleType('odoo.http')
    odoo_http.Controller = type('Controller', (), {})
    odoo_http.route = lambda *a, **kw: (lambda f: f)
    odoo_http.request = None

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


def _register_barcode_addon():
    """Register mml_barcode_registry under odoo.addons and as a top-level package."""
    odoo_addons = sys.modules.get('odoo.addons')
    full_name = 'odoo.addons.mml_barcode_registry'
    if full_name in sys.modules:
        return

    pkg = types.ModuleType(full_name)
    pkg.__path__ = [str(_ADDON)]
    pkg.__package__ = full_name
    sys.modules[full_name] = pkg
    if 'mml_barcode_registry' not in sys.modules:
        sys.modules['mml_barcode_registry'] = pkg
    if odoo_addons is not None:
        setattr(odoo_addons, 'mml_barcode_registry', pkg)

    # Register subpackages needed for absolute imports
    for sub in ('models', 'services', 'wizard', 'views', 'tests'):
        sub_full = f'{full_name}.{sub}'
        if sub_full not in sys.modules:
            sub_pkg = types.ModuleType(sub_full)
            sub_pkg.__path__ = [str(_ADDON / sub)]
            sub_pkg.__package__ = sub_full
            sys.modules[sub_full] = sub_pkg


_install_odoo_stubs()
_register_barcode_addon()

# Add the repo root to sys.path so mml_barcode_registry is importable directly
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_collection_modifyitems(config, items):
    """Auto-mark TransactionCase-based tests as odoo_integration."""
    from odoo.tests import TransactionCase
    for item in items:
        if isinstance(item, pytest.Class):
            continue
        cls = getattr(item, 'cls', None)
        if cls is not None and issubclass(cls, TransactionCase):
            item.add_marker(pytest.mark.odoo_integration)
