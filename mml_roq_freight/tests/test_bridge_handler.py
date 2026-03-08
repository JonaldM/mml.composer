"""
Integration tests for mml_roq_freight bridge event handler logic.
Pure-Python — uses Odoo stubs from conftest.py. No live Odoo needed.

Handler: mml.roq.freight.bridge
  _on_shipment_group_confirmed(event)
      - Guards on event.res_id (no-op if falsy)
      - Parses event.payload_json for 'group_ref'
      - Calls mml.registry.service('freight') -> FreightService.create_tender(...)
      - On success: writes freight_tender_id back on roq.shipment.group
      - On exception: logs warning, posts chatter note on shipment group, returns

  _on_freight_booking_confirmed(event)
      - Guards on event.res_id (no-op if falsy)
      - Calls mml.registry.service('roq') -> ROQService.on_freight_booking_confirmed(event)
      - On exception: logs warning, returns (does not re-raise)
"""
import json
import types
import pytest


# ---------------------------------------------------------------------------
# Minimal mock service definitions
# ---------------------------------------------------------------------------

class MockFreightService:
    """Stub for the freight service returned by mml.registry.service('freight')."""

    def __init__(self, tender_id=42):
        self.create_tender_calls = []
        self._tender_id = tender_id

    def create_tender(self, payload):
        self.create_tender_calls.append(payload)
        return self._tender_id

    def is_null(self):
        return False


class MockFreightServiceRaises:
    """Freight service that raises on create_tender."""

    def __init__(self, exc=None):
        self.create_tender_calls = []
        self._exc = exc or RuntimeError("freight service unavailable")

    def create_tender(self, payload):
        self.create_tender_calls.append(payload)
        raise self._exc

    def is_null(self):
        return False


class MockROQService:
    """Stub for the ROQ service returned by mml.registry.service('roq')."""

    def __init__(self):
        self.on_freight_booking_confirmed_calls = []

    def on_freight_booking_confirmed(self, event):
        self.on_freight_booking_confirmed_calls.append(event)

    def is_null(self):
        return False


class MockROQServiceRaises:
    """ROQ service that raises on on_freight_booking_confirmed."""

    def __init__(self, exc=None):
        self.on_freight_booking_confirmed_calls = []
        self._exc = exc or RuntimeError("roq service error")

    def on_freight_booking_confirmed(self, event):
        self.on_freight_booking_confirmed_calls.append(event)
        raise self._exc

    def is_null(self):
        return False


# ---------------------------------------------------------------------------
# Fake Odoo environment plumbing
# ---------------------------------------------------------------------------

def _make_record(res_id, write_store=None, exists=True, message_posts=None):
    """Return a minimal record-like object that tracks write() and message_post()."""
    record = types.SimpleNamespace(
        id=res_id,
        _write_vals=None,
        _message_posts=message_posts if message_posts is not None else [],
        _exists=exists,
    )

    def _write(vals):
        record._write_vals = vals

    def _exists_fn():
        return record._exists

    def _message_post(**kwargs):
        record._message_posts.append(kwargs)

    record.write = _write
    record.exists = _exists_fn
    record.message_post = _message_post
    return record


def _make_env(registry_map, model_records=None):
    """
    Build a minimal self.env replacement.

    registry_map: dict mapping service name -> service instance,
                  e.g. {'freight': MockFreightService()}
    model_records: dict mapping model name -> dict of id -> record-like
    """
    model_records = model_records or {}

    class FakeRegistry:
        def service(self_r, name):
            return registry_map.get(name, _NullService())

    class FakeEnv:
        def __init__(self):
            self._registry = FakeRegistry()
            self._emitted = []

        def __getitem__(self, model_name):
            if model_name == 'mml.registry':
                return self._registry

            if model_name == 'mml.event':
                return _FakeEventEmitter(self._emitted)

            # Return a fake model accessor for a named model
            records_for_model = model_records.get(model_name, {})
            return _FakeModel(records_for_model)

    return FakeEnv()


class _NullService:
    def is_null(self):
        return True

    def __getattr__(self, name):
        return lambda *a, **kw: None


class _FakeModel:
    def __init__(self, records):
        self._records = records  # dict id -> record

    def browse(self, res_id):
        if res_id in self._records:
            return self._records[res_id]
        # Return a non-existent stub
        rec = types.SimpleNamespace(
            id=res_id,
            _write_vals=None,
            _message_posts=[],
            _exists=False,
        )

        def _exists_fn():
            return rec._exists

        def _write(vals):
            rec._write_vals = vals

        def _message_post(**kwargs):
            rec._message_posts.append(kwargs)

        rec.exists = _exists_fn
        rec.write = _write
        rec.message_post = _message_post
        return rec


class _FakeEventEmitter:
    def __init__(self, log):
        self._log = log

    def emit(self, event_type, **kwargs):
        self._log.append({'event_type': event_type, **kwargs})


# ---------------------------------------------------------------------------
# Bridge class loader (pure-Python, stubs already installed by conftest.py)
# ---------------------------------------------------------------------------

def _load_bridge():
    """Import the bridge module and return the handler class."""
    import importlib.util
    import os
    bridge_path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'bridge_service.py'
    )
    spec = importlib.util.spec_from_file_location('bridge_service', bridge_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MmlRoqFreightBridge


def _make_handler(env):
    """Return a handler instance with self.env wired to the given fake env."""
    cls = _load_bridge()
    handler = object.__new__(cls)
    handler.env = env
    return handler


# ---------------------------------------------------------------------------
# Tests: _on_shipment_group_confirmed
# ---------------------------------------------------------------------------

class TestOnShipmentGroupConfirmed:

    def _event(self, res_id=10, payload=None):
        return types.SimpleNamespace(
            id=99,
            res_id=res_id,
            payload_json=json.dumps(payload) if payload else None,
        )

    def test_normal_path_creates_tender_with_correct_args(self):
        """freight service is called with shipment_group_ref and shipment_group_id."""
        freight_svc = MockFreightService(tender_id=77)
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload={'group_ref': 'GRP-001'})

        handler._on_shipment_group_confirmed(event)

        assert len(freight_svc.create_tender_calls) == 1
        call_args = freight_svc.create_tender_calls[0]
        assert call_args['shipment_group_ref'] == 'GRP-001'
        assert call_args['shipment_group_id'] == 10

    def test_normal_path_writes_tender_id_back_on_shipment_group(self):
        """freight_tender_id is written back on the shipment group record."""
        freight_svc = MockFreightService(tender_id=42)
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload={'group_ref': 'GRP-002'})

        handler._on_shipment_group_confirmed(event)

        assert sg_record._write_vals == {'freight_tender_id': 42}

    def test_no_write_when_tender_id_is_falsy(self):
        """If create_tender returns None/0, write() is NOT called on the shipment group."""
        freight_svc = MockFreightService(tender_id=None)
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload={'group_ref': 'GRP-003'})

        handler._on_shipment_group_confirmed(event)

        assert sg_record._write_vals is None  # no write occurred

    def test_no_op_when_res_id_is_zero(self):
        """Handler returns immediately when event.res_id is falsy (0)."""
        freight_svc = MockFreightService(tender_id=42)
        env = _make_env(registry_map={'freight': freight_svc})
        handler = _make_handler(env)
        event = self._event(res_id=0)

        handler._on_shipment_group_confirmed(event)

        assert freight_svc.create_tender_calls == []

    def test_no_op_when_res_id_is_none(self):
        """Handler returns immediately when event.res_id is None."""
        freight_svc = MockFreightService(tender_id=42)
        env = _make_env(registry_map={'freight': freight_svc})
        handler = _make_handler(env)
        event = self._event(res_id=None)

        handler._on_shipment_group_confirmed(event)

        assert freight_svc.create_tender_calls == []

    def test_missing_payload_json_defaults_to_empty_group_ref(self):
        """Null/missing payload_json yields group_ref='' (does not raise)."""
        freight_svc = MockFreightService(tender_id=5)
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload=None)

        handler._on_shipment_group_confirmed(event)

        assert freight_svc.create_tender_calls[0]['shipment_group_ref'] == ''

    def test_exception_from_freight_service_does_not_propagate(self):
        """Handler catches exceptions from create_tender and does not re-raise."""
        freight_svc = MockFreightServiceRaises()
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload={'group_ref': 'GRP-X'})

        # Must not raise
        handler._on_shipment_group_confirmed(event)

    def test_exception_posts_chatter_note_on_shipment_group(self):
        """On exception, a message_post() chatter note is written on the SG record."""
        freight_svc = MockFreightServiceRaises(exc=RuntimeError("timeout"))
        sg_record = _make_record(res_id=10)
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={'roq.shipment.group': {10: sg_record}},
        )
        handler = _make_handler(env)
        event = self._event(res_id=10, payload={'group_ref': 'GRP-X'})

        handler._on_shipment_group_confirmed(event)

        assert len(sg_record._message_posts) == 1
        body = sg_record._message_posts[0]['body']
        assert 'timeout' in body

    def test_exception_with_nonexistent_shipment_group_does_not_raise(self):
        """Even if browse/exists returns False, the handler does not raise."""
        freight_svc = MockFreightServiceRaises()
        # No record in model_records -> browse returns a non-existent stub
        env = _make_env(
            registry_map={'freight': freight_svc},
            model_records={},
        )
        handler = _make_handler(env)
        event = self._event(res_id=999)

        # Must not raise
        handler._on_shipment_group_confirmed(event)


# ---------------------------------------------------------------------------
# Tests: _on_freight_booking_confirmed (ROQ lead-time feedback handler)
# ---------------------------------------------------------------------------

class TestOnFreightBookingConfirmed:

    def _event(self, res_id=20):
        return types.SimpleNamespace(id=55, res_id=res_id)

    def test_normal_path_calls_roq_service(self):
        """ROQ service.on_freight_booking_confirmed is called with the event."""
        roq_svc = MockROQService()
        env = _make_env(registry_map={'roq': roq_svc})
        handler = _make_handler(env)
        event = self._event(res_id=20)

        handler._on_freight_booking_confirmed(event)

        assert len(roq_svc.on_freight_booking_confirmed_calls) == 1
        assert roq_svc.on_freight_booking_confirmed_calls[0] is event

    def test_no_op_when_res_id_is_zero(self):
        """Handler returns immediately when event.res_id is 0."""
        roq_svc = MockROQService()
        env = _make_env(registry_map={'roq': roq_svc})
        handler = _make_handler(env)
        event = self._event(res_id=0)

        handler._on_freight_booking_confirmed(event)

        assert roq_svc.on_freight_booking_confirmed_calls == []

    def test_no_op_when_res_id_is_none(self):
        """Handler returns immediately when event.res_id is None."""
        roq_svc = MockROQService()
        env = _make_env(registry_map={'roq': roq_svc})
        handler = _make_handler(env)
        event = self._event(res_id=None)

        handler._on_freight_booking_confirmed(event)

        assert roq_svc.on_freight_booking_confirmed_calls == []

    def test_exception_from_roq_service_does_not_propagate(self):
        """Handler catches exceptions from ROQ service and does not re-raise."""
        roq_svc = MockROQServiceRaises(exc=RuntimeError("roq failure"))
        env = _make_env(registry_map={'roq': roq_svc})
        handler = _make_handler(env)
        event = self._event(res_id=20)

        # Must not raise
        handler._on_freight_booking_confirmed(event)

    def test_null_service_does_not_raise(self):
        """Handler does not raise when registry returns a NullService."""
        env = _make_env(registry_map={})  # no 'roq' key -> NullService
        handler = _make_handler(env)
        event = self._event(res_id=20)

        # NullService.on_freight_booking_confirmed is a no-op lambda that returns None
        # The handler passes the event through without raising
        handler._on_freight_booking_confirmed(event)
