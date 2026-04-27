"""Pure-Python structural tests for emit_idempotent() and dedupe_key.

These tests run without a live Odoo runtime. They verify:
- The dedupe_key field is declared on MmlEvent as a Char with index=True
- emit_idempotent() exists with the expected signature
- Calling emit_idempotent() twice with the same dedupe_key returns the
  EXISTING event without creating a duplicate
- Calling emit_idempotent() with an empty/None dedupe_key raises ValueError

The model class is loaded via the conftest Odoo stubs so we can introspect
fields and call emit_idempotent() against a stub-driven self.
"""
import inspect
import json
import pathlib
import sys

import pytest


# Make the mml_base package importable as `odoo.addons.mml_base.*` style
# is NOT used here — instead we import the module file directly via path.
_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_mml_event_module():
    """Import mml_base.models.mml_event by adding the worktree root to sys.path.

    Side-effect-safe: only manipulates sys.path; the module gets cached in
    sys.modules under the dotted name produced by importlib.
    """
    import importlib
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    module_name = 'mml_base.models.mml_event'
    if module_name in sys.modules:
        return sys.modules[module_name]
    # mml_base.models exists as a real package; make sure mml_base.__init__ is
    # importable as a vanilla namespace too. The package's __init__ imports
    # from .models which imports from . (Odoo addon style); that pulls
    # services/post_init_hook etc. — too much. Import the leaf file directly.
    spec = importlib.util.spec_from_file_location(
        module_name,
        _ROOT / 'mml_base' / 'models' / 'mml_event.py',
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def mml_event_cls():
    mod = _load_mml_event_module()
    return mod.MmlEvent


def test_dedupe_key_field_declared_as_char_with_index(mml_event_cls):
    """dedupe_key is a Char field with index=True so lookups are fast.

    The partial UNIQUE index is added in the post-migration script
    (mml_base/migrations/19.0.1.1.0/post-migration.py); the field-level
    index=True keeps the BTREE in place for queries even without the
    UNIQUE constraint enforced for NULL rows.
    """
    fields_meta = mml_event_cls._fields_meta
    assert 'dedupe_key' in fields_meta, (
        "MmlEvent must declare a 'dedupe_key' field for idempotent emits"
    )
    field = fields_meta['dedupe_key']
    # The conftest stub records all kwargs passed to fields.Char(...)
    assert field.__class__.__name__ == 'Char', (
        f"dedupe_key must be a Char field, got {field.__class__.__name__}"
    )
    assert field._kwargs.get('index') is True, (
        "dedupe_key must declare index=True for fast existence lookups"
    )


def test_emit_idempotent_method_signature(mml_event_cls):
    """emit_idempotent has the expected keyword-only signature."""
    assert hasattr(mml_event_cls, 'emit_idempotent'), (
        "MmlEvent must expose an emit_idempotent() method"
    )
    sig = inspect.signature(mml_event_cls.emit_idempotent)
    params = sig.parameters
    # First param is self; second is event_type (positional-or-kw); rest must
    # be keyword-only so callers cannot accidentally mis-position dedupe_key.
    assert 'self' in params
    assert 'event_type' in params
    for required_kw in (
        'dedupe_key',
        'quantity',
        'billable_unit',
        'res_model',
        'res_id',
        'payload',
        'source_module',
    ):
        assert required_kw in params, (
            f"emit_idempotent must accept '{required_kw}' as a keyword argument"
        )
        assert params[required_kw].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"emit_idempotent's '{required_kw}' must be keyword-only "
            f"(found kind={params[required_kw].kind})"
        )
    # dedupe_key has no default — caller MUST supply one
    assert params['dedupe_key'].default is inspect.Parameter.empty, (
        "dedupe_key must be a required keyword arg (no default) — use emit() "
        "for events that have no idempotency key"
    )


def test_emit_idempotent_rejects_empty_dedupe_key(mml_event_cls):
    """emit_idempotent('foo', dedupe_key='') raises ValueError."""
    instance = mml_event_cls()
    # Provide minimal stub env that emit_idempotent might touch BEFORE the
    # validation; but the validation runs first so env is unused on this path.
    with pytest.raises(ValueError, match='dedupe_key'):
        instance.emit_idempotent('test.event', dedupe_key='')


def test_emit_idempotent_returns_existing_event_on_duplicate_key(mml_event_cls):
    """The second emit_idempotent() with the same dedupe_key returns the
    same event and does NOT create a new row.

    We stub:
      - self.sudo() -> self
      - self.search([('dedupe_key', '=', K)], limit=1) -> existing or []
      - self.create({...}) -> records the call and returns a fake event
      - self.env['mml.event.subscription'].dispatch(event) -> records the call
      - self.env['ir.config_parameter'].sudo().get_param(...) -> ''
    """
    instance = mml_event_cls()

    # First emit: search returns empty -> create runs.
    # Second emit: search returns an existing event -> create does NOT run.
    create_calls: list[dict] = []
    dispatch_calls: list[object] = []
    existing_event_holder: list[object] = [None]

    class _FakeEvent:
        def __init__(self, vals):
            self.vals = vals
            self.event_type = vals.get('event_type', '')
            self.id = id(self)

    class _FakeSubscription:
        def dispatch(self, event):
            dispatch_calls.append(event)

    class _FakeConfigParam:
        def sudo(self):
            return self

        def get_param(self, key, default=''):
            return default

    class _FakeEnv:
        def __getitem__(self, model_name):
            if model_name == 'mml.event.subscription':
                return _FakeSubscription()
            if model_name == 'ir.config_parameter':
                return _FakeConfigParam()
            raise KeyError(model_name)

    def _fake_search(domain, **kwargs):
        # Only honour dedupe_key lookups; assert structure.
        for clause in domain:
            if clause[0] == 'dedupe_key' and clause[1] == '=':
                if existing_event_holder[0] is not None and \
                        existing_event_holder[0].vals.get('dedupe_key') == clause[2]:
                    return existing_event_holder[0]
        return []  # falsy -> not found

    def _fake_create(vals):
        ev = _FakeEvent(vals)
        existing_event_holder[0] = ev
        create_calls.append(vals)
        return ev

    # Bind stubs onto the instance (instance attributes shadow the stub
    # Model methods defined in conftest).
    instance.env = _FakeEnv()
    instance.sudo = lambda: instance
    instance.search = _fake_search
    instance.create = _fake_create

    key = 'freight.booking.42.confirmed'
    first = instance.emit_idempotent(
        'freight.booking.confirmed',
        dedupe_key=key,
        quantity=1.0,
        billable_unit='freight_booking',
        res_model='freight.booking',
        res_id=42,
        payload={'ref': 'FB-42'},
        source_module='mml_freight',
    )
    second = instance.emit_idempotent(
        'freight.booking.confirmed',
        dedupe_key=key,
        quantity=1.0,
        billable_unit='freight_booking',
        res_model='freight.booking',
        res_id=42,
        payload={'ref': 'FB-42'},
        source_module='mml_freight',
    )

    assert first is second, (
        "Second emit_idempotent with the same dedupe_key must return the "
        "SAME event object — no duplicate row created"
    )
    assert len(create_calls) == 1, (
        f"Expected exactly one create() call across two emits with the same "
        f"dedupe_key; got {len(create_calls)}"
    )
    assert create_calls[0]['dedupe_key'] == key
    assert create_calls[0]['event_type'] == 'freight.booking.confirmed'
    assert create_calls[0]['res_id'] == 42
    payload_round_trip = json.loads(create_calls[0]['payload_json'])
    assert payload_round_trip == {'ref': 'FB-42'}
    # dispatch is called once — only on the actual create
    assert len(dispatch_calls) == 1, (
        f"dispatch() must be called exactly once across two idempotent "
        f"emits; got {len(dispatch_calls)}"
    )


def test_emit_idempotent_distinct_keys_create_distinct_events(mml_event_cls):
    """Different dedupe_keys must create different events."""
    instance = mml_event_cls()

    create_calls: list[dict] = []
    rows: list[object] = []

    class _FakeEvent:
        def __init__(self, vals):
            self.vals = vals

    class _FakeSubscription:
        def dispatch(self, event):
            pass

    class _FakeConfigParam:
        def sudo(self):
            return self

        def get_param(self, key, default=''):
            return default

    class _FakeEnv:
        def __getitem__(self, model_name):
            if model_name == 'mml.event.subscription':
                return _FakeSubscription()
            if model_name == 'ir.config_parameter':
                return _FakeConfigParam()
            raise KeyError(model_name)

    def _fake_search(domain, **kwargs):
        for clause in domain:
            if clause[0] == 'dedupe_key' and clause[1] == '=':
                for row in rows:
                    if row.vals.get('dedupe_key') == clause[2]:
                        return row
        return []

    def _fake_create(vals):
        ev = _FakeEvent(vals)
        rows.append(ev)
        create_calls.append(vals)
        return ev

    instance.env = _FakeEnv()
    instance.sudo = lambda: instance
    instance.search = _fake_search
    instance.create = _fake_create

    a = instance.emit_idempotent('e.t', dedupe_key='key-A')
    b = instance.emit_idempotent('e.t', dedupe_key='key-B')

    assert a is not b
    assert len(create_calls) == 2
    assert create_calls[0]['dedupe_key'] == 'key-A'
    assert create_calls[1]['dedupe_key'] == 'key-B'
