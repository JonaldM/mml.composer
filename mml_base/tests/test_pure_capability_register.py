"""Pure-Python structural tests for mml.capability.

mml_base is the platform layer every other mml_* module depends on, so the shape of
``mml.capability`` (the field set, the model name, the public method surface) is part of
the contract. These tests assert that contract without spinning up Odoo: the conftest
``_BaseField.__set_name__`` hook captures every field as ``_fields_meta`` so we can
inspect the model class directly.
"""
import importlib.util
import inspect
import os


def _load_capability_module():
    """Load mml_capability.py directly — avoids the unregistered odoo.addons.* package path."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_capability.py'
    )
    spec = importlib.util.spec_from_file_location('mml_capability', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MmlCapability = _load_capability_module().MmlCapability


class TestCapabilityModelMetadata:
    """Class-level attributes that other mml_* modules depend on."""

    def test_model_name(self):
        assert MmlCapability._name == 'mml.capability'

    def test_has_description(self):
        assert MmlCapability._description
        assert isinstance(MmlCapability._description, str)


class TestCapabilityFields:
    """Field inventory captured by the conftest's _BaseField.__set_name__ hook."""

    def test_fields_meta_populated(self):
        """conftest captures every field declaration as _fields_meta — sanity check."""
        assert hasattr(MmlCapability, '_fields_meta')
        assert isinstance(MmlCapability._fields_meta, dict)

    def test_has_name_field(self):
        assert 'name' in MmlCapability._fields_meta

    def test_has_module_field(self):
        assert 'module' in MmlCapability._fields_meta

    def test_has_company_id_field(self):
        """Capabilities are scoped per-company (multi-tenant safety)."""
        assert 'company_id' in MmlCapability._fields_meta

    def test_name_field_is_required(self):
        name_field = MmlCapability._fields_meta['name']
        assert name_field._kwargs.get('required') is True

    def test_module_field_is_required(self):
        module_field = MmlCapability._fields_meta['module']
        assert module_field._kwargs.get('required') is True

    def test_name_field_is_indexed(self):
        """has() does ``search_count([('name', '=', cap)])`` — the name field MUST be indexed.

        Capability lookups happen on every event dispatch in some flows; missing the
        index here would silently degrade performance.
        """
        name_field = MmlCapability._fields_meta['name']
        assert name_field._kwargs.get('index') is True

    def test_module_field_is_indexed(self):
        """deregister_module() searches by module — index required for cheap uninstalls."""
        module_field = MmlCapability._fields_meta['module']
        assert module_field._kwargs.get('index') is True


class TestCapabilityPublicSurface:
    """Method surface used by post_init_hook / uninstall_hook in every mml_* module."""

    def test_has_register(self):
        assert hasattr(MmlCapability, 'register')
        assert callable(MmlCapability.register)

    def test_has_deregister_module(self):
        assert hasattr(MmlCapability, 'deregister_module')
        assert callable(MmlCapability.deregister_module)

    def test_has_has_method(self):
        assert hasattr(MmlCapability, 'has')
        assert callable(MmlCapability.has)

    def test_register_signature_takes_capabilities_list_and_module(self):
        """Signature: register(self, capabilities: list[str], module: str) -> None."""
        sig = inspect.signature(MmlCapability.register)
        params = list(sig.parameters.keys())
        assert params == ['self', 'capabilities', 'module']

    def test_deregister_module_signature(self):
        """Signature: deregister_module(self, module: str) -> None."""
        sig = inspect.signature(MmlCapability.deregister_module)
        params = list(sig.parameters.keys())
        assert params == ['self', 'module']

    def test_has_signature(self):
        """Signature: has(self, capability: str) -> bool."""
        sig = inspect.signature(MmlCapability.has)
        params = list(sig.parameters.keys())
        assert params == ['self', 'capability']

    def test_register_module_kwarg_is_keyword_only_or_named(self):
        """post_init_hook calls ``register([...], module='mml_base')`` — module is keyword.

        We accept positional or keyword-only here because the existing tests pass module
        as a kwarg; this guard catches accidental removal/rename of the parameter.
        """
        sig = inspect.signature(MmlCapability.register)
        assert 'module' in sig.parameters
