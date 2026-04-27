"""Pure-Python tests for NullService.

NullService is the fallback returned by ``mml.registry.service()`` when the requested
service module is not installed. Its contract: any method call returns None silently,
``available()`` returns False, ``is_null()`` returns True. Callers in feature modules
(e.g. mml_roq_freight) rely on this so they never need to check installation state
before invoking a service method.

These tests use pure Python — no Odoo runtime required.
"""
import importlib.util
import os


def _load_null_service():
    """Load null_service.py directly — avoids the unregistered odoo.addons.* package path."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'services', 'null_service.py'
    )
    spec = importlib.util.spec_from_file_location('null_service', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NullService = _load_null_service().NullService


class TestNullServiceMethodCalls:
    """Any attribute access returns a callable that returns None."""

    def test_arbitrary_method_returns_none(self):
        svc = NullService()
        assert svc.create_tender({'lines': []}) is None

    def test_arbitrary_method_with_no_args_returns_none(self):
        svc = NullService()
        assert svc.do_something() is None

    def test_arbitrary_method_with_kwargs_returns_none(self):
        svc = NullService()
        assert svc.process(record_id=42, force=True) is None

    def test_method_with_many_args_returns_none(self):
        svc = NullService()
        assert svc.some_method(1, 2, 3, foo='bar', baz=99) is None

    def test_chained_attribute_access_yields_callable(self):
        """``svc.foo`` is a callable, not a NullService — chained ``svc.foo.bar()`` is not part of the contract.

        We assert the documented behaviour explicitly so future drift is caught.
        """
        svc = NullService()
        attr = svc.foo
        assert callable(attr)
        assert attr() is None

    def test_dunder_lookalike_methods_return_none(self):
        """Names that look like dunders but lack underscores still resolve to the lambda."""
        svc = NullService()
        assert svc.get_thing() is None
        assert svc.put_thing() is None


class TestNullServiceContractMethods:
    """available() and is_null() — the documented detection hooks for callers."""

    def test_available_returns_false(self):
        assert NullService().available() is False

    def test_is_null_returns_true(self):
        assert NullService().is_null() is True

    def test_available_is_a_real_method_not_a_lambda(self):
        """available() and is_null() must be real methods so callers can rely on the value."""
        svc = NullService()
        # If __getattr__ was shadowing the real method, available() would return None,
        # not False. Check the value.
        assert svc.available() is not None
        assert svc.is_null() is not None


class TestNullServiceIsolation:
    """Two NullService instances are independent and produce identical behaviour."""

    def test_two_instances_behave_identically(self):
        a = NullService()
        b = NullService()
        assert a.foo() == b.foo()
        assert a.available() == b.available()
        assert a.is_null() == b.is_null()

    def test_no_state_leaks_between_calls(self):
        svc = NullService()
        svc.set_value(42)
        # NullService never stores state — subsequent ``get_value()`` is still None.
        assert svc.get_value() is None
