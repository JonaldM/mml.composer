"""Pure-Python tests for handler isolation in mml.event.subscription.dispatch().

The contract under test:
  - dispatch() iterates subscriptions for event.event_type.
  - Each handler is invoked inside its OWN savepoint (env.cr.savepoint()).
  - If a handler raises, dispatch logs the failure to
    mml.event.dispatch.failure and continues with the next subscription.
  - The handler-method regex (^_on_[a-z_]+$) is enforced BEFORE invocation.
  - Successful handlers are not logged as failures.

These tests do not require a live Odoo. They use the conftest.py stubs and
load mml_event_subscription.py via importlib so they can drive
MmlEventSubscription.dispatch() against a hand-rolled fake env.
"""
import importlib.util
import os
import types

import pytest


# ---------------------------------------------------------------------------
# Module loader — bypasses odoo.addons import path
# ---------------------------------------------------------------------------

def _load_subscription_module():
    """Import mml_event_subscription.py via importlib so that dispatch() is
    callable without a full Odoo addon registry.
    """
    here = os.path.dirname(__file__)
    path = os.path.join(here, '..', 'models', 'mml_event_subscription.py')
    spec = importlib.util.spec_from_file_location(
        'mml_base_test_dispatch_subscription', path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_dispatcher():
    mod = _load_subscription_module()
    dispatcher = object.__new__(mod.MmlEventSubscription)
    return dispatcher


# ---------------------------------------------------------------------------
# Fake env / cr / savepoint plumbing
# ---------------------------------------------------------------------------

class _FakeSavepoint:
    """Context manager stand-in for env.cr.savepoint().

    Records entry/exit calls. If a handler raises inside the with-block, the
    exception propagates out (matching the real Odoo behaviour); dispatch()
    must catch it externally.

    Set rollback_on_exit=True to track when the manager would have rolled
    back (i.e. exited with an exception).
    """

    def __init__(self, log):
        self._log = log
        self.entered_count = 0
        self.exited_count = 0
        self.rolled_back = 0

    def __enter__(self):
        self.entered_count += 1
        self._log.append('enter')
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited_count += 1
        if exc_type is not None:
            self.rolled_back += 1
            self._log.append(f'rollback:{exc_type.__name__}')
        else:
            self._log.append('release')
        # Do NOT swallow — let dispatch() catch outside the savepoint.
        return False


class _FakeCursor:
    """Cursor stub. Each savepoint() call returns a fresh manager so we can
    count how many handlers got their own savepoint."""

    def __init__(self):
        self.savepoint_log = []
        self.savepoints = []

    def savepoint(self):
        sp = _FakeSavepoint(self.savepoint_log)
        self.savepoints.append(sp)
        return sp


class _Subscription:
    """In-memory stand-in for a mml.event.subscription record."""
    __slots__ = ('id', 'event_type', 'handler_model', 'handler_method', 'module')

    def __init__(self, id, event_type, handler_model, handler_method, module='_test'):
        self.id = id
        self.event_type = event_type
        self.handler_model = handler_model
        self.handler_method = handler_method
        self.module = module


class _FakeFailureModel:
    """Stub for env['mml.event.dispatch.failure']. Records create() calls."""

    def __init__(self):
        self.created = []

    def sudo(self):
        return self

    def create(self, vals):
        self.created.append(dict(vals))
        return types.SimpleNamespace(id=len(self.created), **vals)


class _Recorder:
    """A handler model whose _on_* methods record calls and optionally raise.

    raise_on: dict of method_name -> Exception instance (or None for no-raise).
    """

    def __init__(self, raise_on=None):
        self.calls = []
        self._raise_on = raise_on or {}

    # Method name normally looks like _on_foo_bar — created on demand below.
    def _make_on(self, name):
        def method(event):
            self.calls.append((name, event))
            exc = self._raise_on.get(name)
            if exc is not None:
                raise exc
        return method

    def __getattr__(self, name):
        # Only respond to safe handler names; raise AttributeError otherwise so
        # that dispatch() does not try to call random attributes.
        if name.startswith('_on_'):
            return self._make_on(name)
        raise AttributeError(name)


class _FakeEnv:
    """Lookup map: model_name -> recorder/model stub."""

    def __init__(self, models, failure_model, cr):
        self._models = models
        self._failure_model = failure_model
        self.cr = cr

    def __getitem__(self, name):
        if name == 'mml.event.dispatch.failure':
            return self._failure_model
        if name in self._models:
            return self._models[name]
        raise KeyError(name)

    def get(self, name, default=None):
        if name == 'mml.event.dispatch.failure':
            return self._failure_model
        return self._models.get(name, default)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(event_type='evt.x', event_id=42):
    return types.SimpleNamespace(id=event_id, event_type=event_type)


def _patched_dispatch(dispatcher, env, subscriptions):
    """Drive dispatcher.dispatch(event) with a stubbed self.search() call.

    The real Model.search returns a recordset; here we monkey-patch the
    instance to return our list of subscriptions for the matching event_type.
    """
    dispatcher.env = env
    dispatcher.search = lambda domain: list(subscriptions)
    return dispatcher


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDispatchSavepointIsolation:

    def test_failing_handler_does_not_block_subsequent_handlers(self):
        """If subscriber A raises, subscriber B is still invoked."""
        rec_a = _Recorder(raise_on={'_on_thing': RuntimeError('A boom')})
        rec_b = _Recorder()
        cr = _FakeCursor()
        failures = _FakeFailureModel()
        env = _FakeEnv(
            models={'model.a': rec_a, 'model.b': rec_b},
            failure_model=failures,
            cr=cr,
        )
        subs = [
            _Subscription(1, 'evt.thing', 'model.a', '_on_thing'),
            _Subscription(2, 'evt.thing', 'model.b', '_on_thing'),
        ]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)

        dispatcher.dispatch(_make_event('evt.thing'))

        # Both handlers were called, in order.
        assert [c[0] for c in rec_a.calls] == ['_on_thing']
        assert [c[0] for c in rec_b.calls] == ['_on_thing']

    def test_savepoint_is_opened_per_handler(self):
        """Each handler invocation opens its own env.cr.savepoint() context."""
        rec = _Recorder()
        cr = _FakeCursor()
        env = _FakeEnv(
            models={'model.x': rec},
            failure_model=_FakeFailureModel(),
            cr=cr,
        )
        subs = [
            _Subscription(1, 'evt.q', 'model.x', '_on_q'),
            _Subscription(2, 'evt.q', 'model.x', '_on_q'),
            _Subscription(3, 'evt.q', 'model.x', '_on_q'),
        ]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)

        dispatcher.dispatch(_make_event('evt.q'))

        # Three subscriptions, three savepoints opened.
        assert len(cr.savepoints) == 3
        for sp in cr.savepoints:
            assert sp.entered_count == 1
            assert sp.exited_count == 1

    def test_failing_handler_logs_to_dispatch_failure(self):
        """A failing handler creates an mml.event.dispatch.failure record with
        error_class, error_message, and traceback populated."""
        boom = ValueError('payload missing key foo')
        rec = _Recorder(raise_on={'_on_q': boom})
        cr = _FakeCursor()
        failures = _FakeFailureModel()
        env = _FakeEnv(
            models={'model.x': rec},
            failure_model=failures,
            cr=cr,
        )
        subs = [_Subscription(99, 'evt.q', 'model.x', '_on_q')]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)
        event = _make_event('evt.q', event_id=7)

        dispatcher.dispatch(event)

        assert len(failures.created) == 1
        rec_vals = failures.created[0]
        assert rec_vals['event_id'] == 7
        assert rec_vals['subscription_id'] == 99
        assert rec_vals['handler_model'] == 'model.x'
        assert rec_vals['handler_method'] == '_on_q'
        assert rec_vals['error_class'] == 'ValueError'
        assert 'payload missing key foo' in rec_vals['error_message']
        # traceback is the full Python traceback string — a few markers we
        # always expect to find.
        assert rec_vals['traceback']
        assert 'ValueError' in rec_vals['traceback']

    def test_successful_handlers_do_not_log_failures(self):
        """When every handler returns cleanly, no failure rows are created."""
        rec = _Recorder()
        cr = _FakeCursor()
        failures = _FakeFailureModel()
        env = _FakeEnv(
            models={'model.x': rec},
            failure_model=failures,
            cr=cr,
        )
        subs = [
            _Subscription(1, 'evt.q', 'model.x', '_on_q'),
            _Subscription(2, 'evt.q', 'model.x', '_on_q'),
        ]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)

        dispatcher.dispatch(_make_event('evt.q'))

        assert failures.created == []

    def test_handler_method_regex_enforced_before_invocation(self):
        """A subscription whose handler_method does not match ^_on_[a-z_]+$
        is rejected: handler is NOT called and no failure row is logged."""
        rec = _Recorder()
        cr = _FakeCursor()
        failures = _FakeFailureModel()
        env = _FakeEnv(
            models={'model.x': rec},
            failure_model=failures,
            cr=cr,
        )
        bad_subs = [
            _Subscription(1, 'evt.q', 'model.x', 'unlink'),         # no _on_ prefix
            _Subscription(2, 'evt.q', 'model.x', '_on_BadCase'),    # uppercase
            _Subscription(3, 'evt.q', 'model.x', '_on_with-dash'),  # dash
            _Subscription(4, 'evt.q', 'model.x', '__init__'),       # dunder
            _Subscription(5, 'evt.q', 'model.x', '_on_'),           # empty suffix
        ]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, bad_subs)

        dispatcher.dispatch(_make_event('evt.q'))

        # No handler invoked.
        assert rec.calls == []
        # No failure row written for rejected subscriptions — they never ran.
        assert failures.created == []

    def test_mixed_success_and_failure(self):
        """A run with one failing and two successful handlers logs exactly one
        failure row and calls all three handlers."""
        rec_ok = _Recorder()
        rec_bad = _Recorder(raise_on={'_on_q': KeyError('missing')})
        cr = _FakeCursor()
        failures = _FakeFailureModel()
        env = _FakeEnv(
            models={'model.ok': rec_ok, 'model.bad': rec_bad},
            failure_model=failures,
            cr=cr,
        )
        subs = [
            _Subscription(1, 'evt.q', 'model.ok', '_on_q'),
            _Subscription(2, 'evt.q', 'model.bad', '_on_q'),
            _Subscription(3, 'evt.q', 'model.ok', '_on_q'),
        ]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)

        dispatcher.dispatch(_make_event('evt.q'))

        assert len(rec_ok.calls) == 2
        assert len(rec_bad.calls) == 1
        assert len(failures.created) == 1
        assert failures.created[0]['handler_model'] == 'model.bad'
        assert failures.created[0]['error_class'] == 'KeyError'

    def test_dispatch_does_not_propagate_handler_exception(self):
        """dispatch() returns normally even when every handler raises."""
        rec = _Recorder(raise_on={'_on_q': RuntimeError('always')})
        cr = _FakeCursor()
        env = _FakeEnv(
            models={'model.x': rec},
            failure_model=_FakeFailureModel(),
            cr=cr,
        )
        subs = [_Subscription(1, 'evt.q', 'model.x', '_on_q')]
        dispatcher = _patched_dispatch(_make_dispatcher(), env, subs)

        # Should NOT raise.
        dispatcher.dispatch(_make_event('evt.q'))


# ---------------------------------------------------------------------------
# Structural tests — guarantee the source code uses savepoint() and the new
# failure model. Catches accidental regressions to the old behaviour.
# ---------------------------------------------------------------------------

class TestDispatchSourceStructure:

    @pytest.fixture
    def dispatch_source(self):
        import pathlib
        return pathlib.Path(
            'mml_base/models/mml_event_subscription.py'
        ).read_text()

    def test_source_uses_env_cr_savepoint(self, dispatch_source):
        """dispatch must wrap each handler in a SAVEPOINT, not a Python try."""
        assert 'self.env.cr.savepoint()' in dispatch_source, (
            "mml_event_subscription.dispatch must wrap handler invocation in "
            "self.env.cr.savepoint() so handler DB writes can be rolled back "
            "on failure."
        )

    def test_source_writes_to_failure_model(self, dispatch_source):
        """dispatch must persist failures to mml.event.dispatch.failure."""
        assert 'mml.event.dispatch.failure' in dispatch_source, (
            "mml_event_subscription.dispatch must log handler failures to the "
            "mml.event.dispatch.failure model."
        )

    def test_handler_method_regex_still_present(self, dispatch_source):
        """The ^_on_[a-z_]+$ allowlist must remain enforced."""
        assert '_on_[a-z_]+' in dispatch_source, (
            "Handler-method regex ^_on_[a-z_]+$ must remain enforced before "
            "invocation as a security boundary."
        )
