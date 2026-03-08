"""
Integration tests for mml_freight_3pl bridge event handler logic.
Pure-Python — uses Odoo stubs from conftest.py. No live Odoo needed.

Handler: mml.3pl.bridge._on_freight_booking_confirmed(event)

Logic:
  1. Guard: if event.res_id is falsy, return immediately.
  2. Browse freight.booking by event.res_id; if not booking.exists(), return.
  3. If booking.po_ids is empty, return.
  4. Get svc = mml.registry.service('3pl').
  5. For each PO in booking.po_ids:
       msg_id = svc.queue_inward_order(po.id)
       if msg_id:
           mml.event.emit('3pl.inbound.queued', ...)    <- billable event
       else:
           log warning only, no event emitted
  6. Any exception from the above block: log warning, return (no re-raise).
"""
import types
import pytest


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------

class Mock3PLService:
    """3PL service that returns a configurable msg_id per call."""

    def __init__(self, msg_id=1001):
        self.queue_inward_order_calls = []
        self._msg_id = msg_id

    def queue_inward_order(self, po_id):
        self.queue_inward_order_calls.append(po_id)
        return self._msg_id

    def is_null(self):
        return False


class Mock3PLServiceReturnsNone:
    """3PL service whose queue_inward_order returns None."""

    def __init__(self):
        self.queue_inward_order_calls = []

    def queue_inward_order(self, po_id):
        self.queue_inward_order_calls.append(po_id)
        return None

    def is_null(self):
        return False


class Mock3PLServiceRaises:
    """3PL service that raises on queue_inward_order."""

    def __init__(self, exc=None):
        self.queue_inward_order_calls = []
        self._exc = exc or RuntimeError("3pl service failure")

    def queue_inward_order(self, po_id):
        self.queue_inward_order_calls.append(po_id)
        raise self._exc

    def is_null(self):
        return False


class _NullService:
    def is_null(self):
        return True

    def __getattr__(self, name):
        return lambda *a, **kw: None


# ---------------------------------------------------------------------------
# Fake Odoo environment plumbing
# ---------------------------------------------------------------------------

def _make_po(po_id):
    return types.SimpleNamespace(id=po_id)


def _make_booking(res_id, po_ids, exists=True):
    booking = types.SimpleNamespace(
        id=res_id,
        po_ids=po_ids,
        _exists=exists,
    )
    booking.exists = lambda: booking._exists
    return booking


class _FakeEventEmitter:
    def __init__(self, log):
        self._log = log

    def emit(self, event_type, **kwargs):
        self._log.append({'event_type': event_type, **kwargs})


class _FakeRegistry:
    def __init__(self, service_map):
        self._map = service_map

    def service(self, name):
        return self._map.get(name, _NullService())


class _FakeEnv:
    def __init__(self, service_map, booking_map):
        self._registry = _FakeRegistry(service_map)
        self._booking_map = booking_map
        self.emitted = []

    def __getitem__(self, model_name):
        if model_name == 'mml.registry':
            return self._registry
        if model_name == 'mml.event':
            return _FakeEventEmitter(self.emitted)
        if model_name == 'freight.booking':
            return _FakeBookingModel(self._booking_map)
        raise KeyError(model_name)


class _FakeBookingModel:
    def __init__(self, booking_map):
        self._map = booking_map  # dict: res_id -> booking record or None

    def browse(self, res_id):
        if res_id in self._map:
            return self._map[res_id]
        # Return a non-existent stub
        stub = types.SimpleNamespace(id=res_id, po_ids=[], _exists=False)
        stub.exists = lambda: False
        return stub


def _make_env(service_map, booking_map):
    return _FakeEnv(service_map, booking_map)


# ---------------------------------------------------------------------------
# Bridge loader
# ---------------------------------------------------------------------------

def _load_bridge():
    import importlib.util
    import os
    bridge_path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_3pl_bridge.py'
    )
    spec = importlib.util.spec_from_file_location('mml_3pl_bridge', bridge_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Mml3plBridge


def _make_handler(env):
    cls = _load_bridge()
    handler = object.__new__(cls)
    handler.env = env
    return handler


def _event(res_id):
    return types.SimpleNamespace(id=77, res_id=res_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOnFreightBookingConfirmed:

    def test_normal_path_calls_queue_inward_order_for_each_po(self):
        """Each PO in booking.po_ids triggers exactly one queue_inward_order call."""
        svc = Mock3PLService(msg_id=500)
        po1 = _make_po(po_id=1)
        po2 = _make_po(po_id=2)
        booking = _make_booking(res_id=10, po_ids=[po1, po2])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert svc.queue_inward_order_calls == [1, 2]

    def test_normal_path_emits_billable_event_per_po(self):
        """A 3pl.inbound.queued event is emitted for each PO when msg_id is truthy."""
        svc = Mock3PLService(msg_id=500)
        po1 = _make_po(po_id=1)
        po2 = _make_po(po_id=2)
        booking = _make_booking(res_id=10, po_ids=[po1, po2])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert len(env.emitted) == 2
        for emitted, po in zip(env.emitted, [po1, po2]):
            assert emitted['event_type'] == '3pl.inbound.queued'
            assert emitted['res_id'] == po.id
            assert emitted['billable_unit'] == '3pl_receipt'
            assert emitted['res_model'] == 'purchase.order'
            assert emitted['source_module'] == 'mml_freight_3pl'

    def test_no_op_when_res_id_is_zero(self):
        """Handler returns immediately when event.res_id is 0."""
        svc = Mock3PLService(msg_id=1)
        env = _make_env(service_map={'3pl': svc}, booking_map={})
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=0))

        assert svc.queue_inward_order_calls == []
        assert env.emitted == []

    def test_no_op_when_res_id_is_none(self):
        """Handler returns immediately when event.res_id is None."""
        svc = Mock3PLService(msg_id=1)
        env = _make_env(service_map={'3pl': svc}, booking_map={})
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=None))

        assert svc.queue_inward_order_calls == []

    def test_exits_cleanly_when_booking_does_not_exist(self):
        """Handler returns without calling service when booking.exists() is False."""
        svc = Mock3PLService(msg_id=1)
        booking = _make_booking(res_id=10, po_ids=[_make_po(1)], exists=False)
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert svc.queue_inward_order_calls == []
        assert env.emitted == []

    def test_exits_cleanly_when_po_ids_is_empty(self):
        """Handler returns without calling service when booking.po_ids is empty."""
        svc = Mock3PLService(msg_id=1)
        booking = _make_booking(res_id=10, po_ids=[])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert svc.queue_inward_order_calls == []
        assert env.emitted == []

    def test_no_billable_event_when_queue_returns_none(self):
        """When queue_inward_order returns None, no billable event is emitted."""
        svc = Mock3PLServiceReturnsNone()
        po = _make_po(po_id=5)
        booking = _make_booking(res_id=10, po_ids=[po])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert svc.queue_inward_order_calls == [5]
        assert env.emitted == []  # no billing event

    def test_billable_event_emitted_when_queue_returns_nonzero_msg_id(self):
        """When queue_inward_order returns a non-zero int, one billing event is emitted."""
        svc = Mock3PLService(msg_id=999)
        po = _make_po(po_id=7)
        booking = _make_booking(res_id=10, po_ids=[po])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert len(env.emitted) == 1
        assert env.emitted[0]['event_type'] == '3pl.inbound.queued'
        assert env.emitted[0]['res_id'] == 7

    def test_exception_from_queue_inward_order_does_not_propagate(self):
        """Exception from queue_inward_order is caught; handler does not re-raise."""
        svc = Mock3PLServiceRaises(exc=ConnectionError("3pl down"))
        po = _make_po(po_id=3)
        booking = _make_booking(res_id=10, po_ids=[po])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        # Must not raise
        handler._on_freight_booking_confirmed(_event(res_id=10))

    def test_exception_suppresses_all_billing_events(self):
        """When queue_inward_order raises, no billing event is emitted."""
        svc = Mock3PLServiceRaises()
        po = _make_po(po_id=3)
        booking = _make_booking(res_id=10, po_ids=[po])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert env.emitted == []

    def test_mixed_msg_ids_only_emit_for_successful_pos(self):
        """POs with msg_id=None do not emit; POs with a real msg_id do emit."""

        class _MixedService:
            """Returns None for even PO IDs, a real ID for odd ones."""
            def __init__(self):
                self.queue_inward_order_calls = []

            def queue_inward_order(self, po_id):
                self.queue_inward_order_calls.append(po_id)
                return None if po_id % 2 == 0 else 200

            def is_null(self):
                return False

        svc = _MixedService()
        po_odd = _make_po(po_id=1)   # will get msg_id=200
        po_even = _make_po(po_id=2)  # will get msg_id=None
        booking = _make_booking(res_id=10, po_ids=[po_odd, po_even])
        env = _make_env(
            service_map={'3pl': svc},
            booking_map={10: booking},
        )
        handler = _make_handler(env)

        handler._on_freight_booking_confirmed(_event(res_id=10))

        assert svc.queue_inward_order_calls == [1, 2]
        assert len(env.emitted) == 1
        assert env.emitted[0]['res_id'] == 1
