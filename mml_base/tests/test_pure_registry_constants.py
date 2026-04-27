"""Pure-Python tests for mml.registry module-level constants.

The registry persists service class paths into ``ir.config_parameter`` under a fixed
prefix and gates re-hydration through an allow-list of trusted module prefixes. These
constants are security-critical: changing ``_ALLOWED_SERVICE_PREFIXES`` or
``_PARAM_PREFIX`` without coordination with deployment migrations would either break
re-hydration after worker fork or open arbitrary-code-execution via
``ir.config_parameter`` tampering.

These tests pin those invariants without requiring an Odoo runtime.
"""
import importlib.util
import inspect
import os


def _load_registry_module():
    """Load mml_registry.py directly — avoids the unregistered odoo.addons.* package path."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_registry.py'
    )
    spec = importlib.util.spec_from_file_location('mml_registry', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reg_module = _load_registry_module()


class TestParamPrefixConstant:
    """_PARAM_PREFIX is the namespace used in ir.config_parameter for service paths."""

    def test_param_prefix_exists(self):
        assert hasattr(reg_module, '_PARAM_PREFIX')

    def test_param_prefix_is_str(self):
        assert isinstance(reg_module._PARAM_PREFIX, str)

    def test_param_prefix_value(self):
        """Pin the exact value — changing it requires a data migration."""
        assert reg_module._PARAM_PREFIX == 'mml_registry.service.'

    def test_param_prefix_ends_with_dot(self):
        """The prefix is concatenated with a service name; trailing dot avoids collisions."""
        assert reg_module._PARAM_PREFIX.endswith('.')


class TestAllowedServicePrefixes:
    """The allow-list of module prefixes that may be re-hydrated as service classes."""

    def test_allowed_prefixes_exists(self):
        assert hasattr(reg_module, '_ALLOWED_SERVICE_PREFIXES')

    def test_allowed_prefixes_is_tuple(self):
        """Tuples are immutable — guards against mutation at runtime."""
        assert isinstance(reg_module._ALLOWED_SERVICE_PREFIXES, tuple)

    def test_allowed_prefixes_is_non_empty(self):
        assert len(reg_module._ALLOWED_SERVICE_PREFIXES) > 0

    def test_includes_mml_addons(self):
        """All mml_* services live under odoo.addons.mml_*."""
        assert 'odoo.addons.mml_' in reg_module._ALLOWED_SERVICE_PREFIXES

    def test_includes_stock_3pl_addons(self):
        """3PL adapter services live under odoo.addons.stock_3pl_*."""
        assert 'odoo.addons.stock_3pl_' in reg_module._ALLOWED_SERVICE_PREFIXES

    def test_no_overly_permissive_prefix(self):
        """A prefix like 'odoo' or '' would defeat the allow-list — explicit guard."""
        forbidden = {'', 'o', 'od', 'odoo', 'odoo.', 'odoo.addons', 'odoo.addons.'}
        for prefix in reg_module._ALLOWED_SERVICE_PREFIXES:
            assert prefix not in forbidden, (
                f"Prefix {prefix!r} is too broad — would allow re-hydration of any "
                f"odoo addon, defeating the security check."
            )

    def test_each_prefix_is_a_namespace(self):
        """Each entry must end with ``_`` so prefix matching is namespace-bounded."""
        for prefix in reg_module._ALLOWED_SERVICE_PREFIXES:
            assert prefix.endswith('_'), (
                f"Prefix {prefix!r} does not end with '_' — partial-name collisions "
                f"could let an attacker register e.g. 'odoo.addons.mml_evil' if 'mml' "
                f"alone were allowed."
            )


class TestServiceRegistryGlobal:
    """The in-process service cache — semantics matter for forked-worker behaviour."""

    def test_service_registry_exists(self):
        assert hasattr(reg_module, '_SERVICE_REGISTRY')

    def test_service_registry_is_dict(self):
        assert isinstance(reg_module._SERVICE_REGISTRY, dict)


class TestRegistryPublicSurface:
    """The public methods of mml.registry — what other modules call."""

    def test_register_signature(self):
        sig = inspect.signature(reg_module.MmlRegistry.register)
        params = list(sig.parameters.keys())
        assert params == ['self', 'service_name', 'service_class']

    def test_deregister_signature(self):
        sig = inspect.signature(reg_module.MmlRegistry.deregister)
        params = list(sig.parameters.keys())
        assert params == ['self', 'service_name']

    def test_service_signature(self):
        sig = inspect.signature(reg_module.MmlRegistry.service)
        params = list(sig.parameters.keys())
        assert params == ['self', 'service_name']

    def test_load_from_db_signature(self):
        """Internal helper — ``_`` prefix marks it private but signature is still pinned."""
        sig = inspect.signature(reg_module.MmlRegistry._load_from_db)
        params = list(sig.parameters.keys())
        assert params == ['self', 'service_name']
