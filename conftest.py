# conftest.py — repo root
# Installs minimal Odoo stubs so that pure-Python structural tests in any
# mml_* module can be collected and run without a live Odoo runtime.
import sys
import types
import pathlib
import pytest

_ROOT = pathlib.Path(__file__).parent


def _install_odoo_stubs():
    """Build and register lightweight odoo stubs in sys.modules (idempotent)."""
    if 'odoo' in sys.modules and hasattr(sys.modules['odoo'], '_stubbed'):
        return

    # ---- odoo.fields ----
    odoo_fields = types.ModuleType('odoo.fields')

    class _BaseField:
        """Minimal field descriptor that captures kwargs for introspection."""
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

    class Boolean(_BaseField):
        pass

    class Char(_BaseField):
        pass

    class Datetime(_BaseField):
        @classmethod
        def now(cls):
            import datetime
            return datetime.datetime.utcnow()

    class Date(_BaseField):
        pass

    class Many2one(_BaseField):
        pass

    class One2many(_BaseField):
        pass

    class Many2many(_BaseField):
        pass

    class Float(_BaseField):
        pass

    class Integer(_BaseField):
        pass

    class Text(_BaseField):
        pass

    class Html(_BaseField):
        pass

    class Binary(_BaseField):
        pass

    class Json(_BaseField):
        pass

    odoo_fields.Selection = Selection
    odoo_fields.Boolean = Boolean
    odoo_fields.Char = Char
    odoo_fields.Datetime = Datetime
    odoo_fields.Date = Date
    odoo_fields.Many2one = Many2one
    odoo_fields.One2many = One2many
    odoo_fields.Many2many = Many2many
    odoo_fields.Float = Float
    odoo_fields.Integer = Integer
    odoo_fields.Text = Text
    odoo_fields.Html = Html
    odoo_fields.Binary = Binary
    odoo_fields.Json = Json

    # ---- odoo.models ----
    odoo_models = types.ModuleType('odoo.models')

    class Model:
        _inherit = None
        _name = None
        _fields_meta = {}

        def write(self, vals):
            pass

        def ensure_one(self):
            pass

        def search(self, domain, **kwargs):
            return []

        def sudo(self):
            return self

        def create(self, vals):
            pass

    class AbstractModel(Model):
        pass

    class TransientModel(Model):
        pass

    odoo_models.Model = Model
    odoo_models.AbstractModel = AbstractModel
    odoo_models.TransientModel = TransientModel
    # Odoo 19: models.Constraint — no-op in structural tests (real SQL constraint not needed)
    odoo_models.Constraint = lambda *a, **kw: None

    # ---- odoo.api ----
    odoo_api = types.ModuleType('odoo.api')
    odoo_api.model = lambda f: f
    odoo_api.depends = lambda *args: (lambda f: f)
    odoo_api.constrains = lambda *args: (lambda f: f)
    odoo_api.onchange = lambda *args: (lambda f: f)
    odoo_api.model_create_multi = lambda f: f

    # ---- odoo.exceptions ----
    odoo_exceptions = types.ModuleType('odoo.exceptions')

    class ValidationError(Exception):
        pass

    class UserError(Exception):
        pass

    odoo_exceptions.ValidationError = ValidationError
    odoo_exceptions.UserError = UserError

    # ---- odoo.tests ----
    import unittest
    odoo_tests = types.ModuleType('odoo.tests')

    class TransactionCase(unittest.TestCase):
        """Stub: provides assertion methods. self.env is NOT available without Odoo."""

    def tagged(*args):
        def decorator(cls):
            return cls
        return decorator

    class HttpCase(TransactionCase):
        """Stub: HTTP test case requiring Odoo."""

    odoo_tests.TransactionCase = TransactionCase
    odoo_tests.HttpCase = HttpCase
    odoo_tests.tagged = tagged

    # ---- odoo.tests.common (alias) ----
    odoo_tests_common = types.ModuleType('odoo.tests.common')
    odoo_tests_common.TransactionCase = TransactionCase
    odoo_tests_common.HttpCase = HttpCase

    # ---- odoo.http ----
    odoo_http = types.ModuleType('odoo.http')

    class _StubController:
        pass

    def _stub_route(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    odoo_http.Controller = _StubController
    odoo_http.route = _stub_route
    odoo_http.request = None

    # ---- odoo translation stub ----
    def _(s):
        """No-op translation stub."""
        return s

    odoo = types.ModuleType('odoo')
    odoo._stubbed = True
    odoo._ = _
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

    # ---- odoo.addons namespace ----
    odoo_addons = types.ModuleType('odoo.addons')
    sys.modules['odoo.addons'] = odoo_addons
    odoo.addons = odoo_addons


_install_odoo_stubs()


def _wire_sysmodules_parents():
    """Ensure intermediate namespace packages have their children as attributes.

    When test-setup code does:
        sys.modules['odoo.addons.stock_3pl_mainfreight.document.inventory_report'] = mod
    unittest.mock.patch() expects:
        odoo.addons.stock_3pl_mainfreight  (attribute on odoo.addons)
        odoo.addons.stock_3pl_mainfreight.document  (attribute on that)
    This hook creates any missing intermediate packages and sets the attributes.
    """
    import sys, types
    prefix = 'odoo.addons.'
    for fqn in list(sys.modules):
        if not fqn.startswith(prefix):
            continue
        parts = fqn.split('.')
        for i in range(1, len(parts)):
            parent_fqn = '.'.join(parts[:i])
            child_fqn = '.'.join(parts[:i + 1])
            if parent_fqn not in sys.modules:
                sys.modules[parent_fqn] = types.ModuleType(parent_fqn)
            parent_mod = sys.modules[parent_fqn]
            child_name = parts[i]
            if child_fqn in sys.modules and not hasattr(parent_mod, child_name):
                setattr(parent_mod, child_name, sys.modules[child_fqn])


# Also patch for non-odoo.addons modules (e.g. mml_edi.parsers.briscoes)
def _wire_all_sysmodules_parents():
    """Wire up parent attributes for ALL dotted module paths in sys.modules."""
    import sys, types
    for fqn in list(sys.modules):
        parts = fqn.split('.')
        if len(parts) < 2:
            continue
        for i in range(1, len(parts)):
            parent_fqn = '.'.join(parts[:i])
            child_fqn = '.'.join(parts[:i + 1])
            if parent_fqn in sys.modules and child_fqn in sys.modules:
                parent_mod = sys.modules[parent_fqn]
                child_name = parts[i]
                if not hasattr(parent_mod, child_name):
                    setattr(parent_mod, child_name, sys.modules[child_fqn])


@pytest.fixture(autouse=True)
def _patch_sysmodules_wiring():
    """Before each test, ensure sys.modules parent→child attributes are wired."""
    _wire_sysmodules_parents()
    _wire_all_sysmodules_parents()
    yield


def pytest_collection_modifyitems(config, items):
    """Auto-mark TransactionCase-based tests as odoo_integration (requires odoo-bin)."""
    from odoo.tests import TransactionCase
    for item in items:
        if isinstance(item, pytest.Class):
            continue
        cls = getattr(item, 'cls', None)
        if cls is not None and issubclass(cls, TransactionCase):
            item.add_marker(pytest.mark.odoo_integration)
