"""Pure-Python structural tests for mml.event.emit().

emit() is THE public entry point of the event bus — every mml_* module calls it. Its
signature is therefore a contract: the keyword-only parameters, defaults, and field
shape on ``mml.event`` must not drift silently. Breaking changes here cascade into
every dependent module.

These tests use ``inspect.signature`` and the conftest field-meta hook — no Odoo
runtime required.
"""
import importlib.util
import inspect
import os


def _load_event_module():
    """Load mml_event.py directly — avoids the unregistered odoo.addons.* package path."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_event.py'
    )
    spec = importlib.util.spec_from_file_location('mml_event', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MmlEvent = _load_event_module().MmlEvent


class TestEmitSignature:
    """The shape of MmlEvent.emit — guards against accidental signature drift."""

    def _signature(self):
        return inspect.signature(MmlEvent.emit)

    def test_emit_exists_and_is_callable(self):
        assert hasattr(MmlEvent, 'emit')
        assert callable(MmlEvent.emit)

    def test_first_param_is_self(self):
        params = list(self._signature().parameters.values())
        assert params[0].name == 'self'

    def test_event_type_is_first_real_param(self):
        """event_type is the only positional arg callers should pass."""
        params = list(self._signature().parameters.values())
        # params[0] is self, params[1] is event_type
        assert params[1].name == 'event_type'

    def test_event_type_is_str_typed(self):
        params = self._signature().parameters
        assert params['event_type'].annotation is str

    def test_event_type_has_no_default(self):
        """event_type is required — no default allowed."""
        params = self._signature().parameters
        assert params['event_type'].default is inspect.Parameter.empty

    def test_quantity_is_keyword_only(self):
        """Every kwarg after event_type must be keyword-only — prevents misordered calls."""
        params = self._signature().parameters
        assert params['quantity'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_quantity_default_is_one(self):
        params = self._signature().parameters
        assert params['quantity'].default == 1.0

    def test_billable_unit_is_keyword_only(self):
        params = self._signature().parameters
        assert params['billable_unit'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_billable_unit_default_is_empty_string(self):
        params = self._signature().parameters
        assert params['billable_unit'].default == ''

    def test_res_model_is_keyword_only(self):
        params = self._signature().parameters
        assert params['res_model'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_res_model_default_is_empty_string(self):
        params = self._signature().parameters
        assert params['res_model'].default == ''

    def test_res_id_is_keyword_only(self):
        params = self._signature().parameters
        assert params['res_id'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_res_id_default_is_zero(self):
        params = self._signature().parameters
        assert params['res_id'].default == 0

    def test_payload_is_keyword_only(self):
        params = self._signature().parameters
        assert params['payload'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_payload_default_is_none(self):
        """payload defaults to None and is normalised to {} in the body — guards against
        the mutable-default-argument antipattern."""
        params = self._signature().parameters
        assert params['payload'].default is None

    def test_source_module_is_keyword_only(self):
        params = self._signature().parameters
        assert params['source_module'].kind is inspect.Parameter.KEYWORD_ONLY

    def test_source_module_default_is_empty_string(self):
        params = self._signature().parameters
        assert params['source_module'].default == ''

    def test_no_unexpected_params(self):
        """Catch accidental new params that callers don't know about."""
        params = self._signature().parameters
        expected = {
            'self', 'event_type', 'quantity', 'billable_unit',
            'res_model', 'res_id', 'payload', 'source_module',
        }
        assert set(params.keys()) == expected


class TestEmitParameterContract:
    """Beyond the signature — the parameter ordering matters for keyword-only enforcement."""

    def test_event_type_is_positional_or_keyword(self):
        """event_type can be passed positionally — callers do ``emit('foo.bar', ...)``."""
        sig = inspect.signature(MmlEvent.emit)
        kind = sig.parameters['event_type'].kind
        assert kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    def test_all_optionals_are_keyword_only(self):
        """All params with defaults must be keyword-only — prevents bug-prone positional drift."""
        sig = inspect.signature(MmlEvent.emit)
        for name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
                    f"Parameter {name!r} has a default but is not keyword-only — "
                    f"this breaks the documented call convention."
                )


class TestEventModelMetadata:
    """The shape of ``mml.event`` itself — fields callers and downstream consumers rely on."""

    def test_model_name(self):
        assert MmlEvent._name == 'mml.event'

    def test_rec_name_is_event_type(self):
        """Default rec_name is event_type — search/UI display key."""
        assert MmlEvent._rec_name == 'event_type'

    def test_has_event_type_field(self):
        assert 'event_type' in MmlEvent._fields_meta

    def test_event_type_is_required_and_indexed(self):
        f = MmlEvent._fields_meta['event_type']
        assert f._kwargs.get('required') is True
        assert f._kwargs.get('index') is True

    def test_has_payload_json_field(self):
        assert 'payload_json' in MmlEvent._fields_meta

    def test_has_quantity_field_with_default(self):
        assert 'quantity' in MmlEvent._fields_meta
        assert MmlEvent._fields_meta['quantity']._kwargs.get('default') == 1.0

    def test_has_synced_to_platform_field_indexed_for_sweeper(self):
        """The platform sync sweeper filters on ``synced_to_platform`` — index required."""
        f = MmlEvent._fields_meta['synced_to_platform']
        assert f._kwargs.get('index') is True
        assert f._kwargs.get('default') is False

    def test_has_instance_ref_field(self):
        """instance_ref tags every event for multi-instance billing attribution."""
        assert 'instance_ref' in MmlEvent._fields_meta
