"""Pure-Python tests for mml.event.dispatch.failure.write() resolve stamping.

The model declares resolved_at (Datetime) and resolved_by (Many2one res.users)
but they were never populated. The write() override stamps them when a row
transitions resolved False -> True, and only then.

These tests do not need a live Odoo. They load the model via importlib against
the conftest stubs and drive write() with a hand-rolled fake recordset so the
branch logic (newly-resolved filter, no-clobber on re-resolve, no stamp on
un-resolve, caller-supplied stamps respected) can be asserted directly.
"""
import importlib.util
import os
import types


def _load_failure_module():
    """Load mml_event_dispatch_failure.py directly (no odoo.addons path needed)."""
    path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_event_dispatch_failure.py'
    )
    spec = importlib.util.spec_from_file_location(
        'mml_event_dispatch_failure', path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MmlEventDispatchFailure = _load_failure_module().MmlEventDispatchFailure


class _ChildRecordset:
    """Stand-in for the ``newly_resolved`` sub-recordset returned by filtered().

    Its write() simply records the vals so the test can inspect the stamping
    payload. (Using a plain object here avoids recursing back into the real
    write() override under test.)"""

    def __init__(self):
        self.written = []

    def __bool__(self):
        return True

    def write(self, vals):
        self.written.append(vals)


class _EmptyChildRecordset(_ChildRecordset):
    def __bool__(self):
        return False


def _make_record(resolved, newly_resolved_child, uid=99):
    """Build a real MmlEventDispatchFailure instance wired with fakes.

    resolved: the record's current resolved value (read by the filtered lambda).
    newly_resolved_child: what self.filtered(...) returns.
    """
    rec = object.__new__(MmlEventDispatchFailure)
    rec.resolved = resolved
    rec._super_writes = []

    def _filtered(predicate):
        return newly_resolved_child

    rec.filtered = _filtered
    rec.env = types.SimpleNamespace(uid=uid)

    # Patch the bound super().write — the conftest Model stub's write() is a
    # no-op; we just need to record the top-level vals passed through.
    return rec


class TestResolveStamping:

    def test_transition_to_resolved_stamps_at_and_by(self):
        """False -> True stamps resolved_at and resolved_by on the newly-resolved set."""
        child = _ChildRecordset()
        rec = _make_record(resolved=False, newly_resolved_child=child, uid=42)

        rec.write({'resolved': True})

        assert len(child.written) == 1
        stamp = child.written[0]
        assert 'resolved_at' in stamp and stamp['resolved_at'] is not None
        assert stamp['resolved_by'] == 42

    def test_already_resolved_is_not_restamped(self):
        """A record already resolved (filtered yields empty) is not re-stamped."""
        child = _EmptyChildRecordset()
        rec = _make_record(resolved=True, newly_resolved_child=child)

        rec.write({'resolved': True})

        assert child.written == []  # no clobber of the original stamp

    def test_unresolving_does_not_stamp(self):
        """Setting resolved=False never stamps resolved_at/resolved_by."""
        child = _ChildRecordset()
        rec = _make_record(resolved=True, newly_resolved_child=child)

        rec.write({'resolved': False})

        assert child.written == []

    def test_write_without_resolved_key_does_not_stamp(self):
        """A write that does not touch resolved leaves the stamp branch alone."""
        child = _ChildRecordset()
        rec = _make_record(resolved=False, newly_resolved_child=child)

        rec.write({'error_message': 'updated note'})

        assert child.written == []

    def test_caller_supplied_resolved_at_is_respected(self):
        """If the caller passes resolved_at itself, the override does not add its own."""
        child = _ChildRecordset()
        rec = _make_record(resolved=False, newly_resolved_child=child)

        rec.write({'resolved': True, 'resolved_at': '2026-01-01 00:00:00'})

        # Stamp branch is skipped because resolved_at was supplied explicitly.
        assert child.written == []

    def test_caller_supplied_resolved_by_is_respected(self):
        """If the caller passes resolved_by itself, the override does not add its own."""
        child = _ChildRecordset()
        rec = _make_record(resolved=False, newly_resolved_child=child)

        rec.write({'resolved': True, 'resolved_by': 7})

        assert child.written == []
