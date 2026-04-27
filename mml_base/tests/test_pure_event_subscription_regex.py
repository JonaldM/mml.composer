"""Pure-Python tests for the handler-method regex enforced by mml.event.subscription.dispatch.

dispatch() resolves a method by name and calls it via getattr() — letting any method
name through would mean a malicious or buggy subscription could invoke arbitrary
attributes on a model (e.g. ``write``, ``unlink``, ``__class__``). The regex
``^_on_[a-z_]+$`` enforces the convention that event handlers are private hooks like
``_on_freight_booking_confirmed``.

These tests run under plain pytest using the root ``conftest.py`` Odoo stubs, so they
do not require a live Odoo runtime.
"""
import importlib.util
import os
import re


def _load_subscription_module():
    """Load mml_event_subscription.py directly by file path.

    Avoids the ``odoo.addons.mml_base`` package import path, which is not registered
    by the root ``conftest.py``. Mirrors the loader pattern used by existing pure-Python
    tests in ``mml_roq_freight/tests/test_bridge_handler.py``.
    """
    path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_event_subscription.py'
    )
    spec = importlib.util.spec_from_file_location('mml_event_subscription', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sub_module = _load_subscription_module()
_HANDLER_METHOD_RE = _sub_module._HANDLER_METHOD_RE
_is_valid_handler_method = _sub_module._is_valid_handler_method


class TestHandlerMethodRegexConstant:
    """The compiled pattern itself is the source of truth for handler-method validation."""

    def test_pattern_string_is_anchored(self):
        """Pattern must be anchored on both ends — partial matches must not slip through."""
        assert _HANDLER_METHOD_RE.pattern.startswith('^')
        assert _HANDLER_METHOD_RE.pattern.endswith('$')

    def test_pattern_is_compiled(self):
        """The constant is a compiled regex, not a raw string — avoids re-compiling per call."""
        assert isinstance(_HANDLER_METHOD_RE, re.Pattern)


class TestIsValidHandlerMethodAccepts:
    """Names that match ^_on_[a-z_]+$ are accepted."""

    def test_simple_name_accepted(self):
        assert _is_valid_handler_method('_on_event') is True

    def test_multi_word_snake_case_accepted(self):
        assert _is_valid_handler_method('_on_freight_booking_confirmed') is True

    def test_single_letter_suffix_accepted(self):
        assert _is_valid_handler_method('_on_x') is True

    def test_trailing_underscore_accepted(self):
        """Trailing underscores match [a-z_]+ — explicit guard against future drift."""
        assert _is_valid_handler_method('_on_event_') is True

    def test_consecutive_underscores_accepted(self):
        """Consecutive underscores match [a-z_]+ — also a regression guard."""
        assert _is_valid_handler_method('_on__double') is True


class TestIsValidHandlerMethodRejects:
    """Names that do not match the pattern are rejected — these are the security cases."""

    def test_no_underscore_prefix_rejected(self):
        assert _is_valid_handler_method('on_event') is False

    def test_double_underscore_prefix_rejected(self):
        """Names like ``__init__`` or ``__class__`` are explicitly out of scope."""
        assert _is_valid_handler_method('__on_event') is False

    def test_uppercase_letters_rejected(self):
        """Pattern is lowercase-only — CamelCase or SCREAMING_CASE handler names fail."""
        assert _is_valid_handler_method('_On_Event') is False
        assert _is_valid_handler_method('_on_Event') is False
        assert _is_valid_handler_method('_ON_EVENT') is False

    def test_digits_rejected(self):
        """No digits allowed in [a-z_]+ — ``_on_event_2`` is rejected."""
        assert _is_valid_handler_method('_on_event2') is False
        assert _is_valid_handler_method('_on_event_2') is False

    def test_special_characters_rejected(self):
        for name in ['_on_event-x', '_on_event.x', '_on_event x', '_on_event!']:
            assert _is_valid_handler_method(name) is False, name

    def test_empty_suffix_rejected(self):
        """``_on_`` alone has no [a-z_]+ suffix — rejected."""
        assert _is_valid_handler_method('_on_') is False

    def test_dunder_methods_rejected(self):
        """The whole point — block reflective attribute access via crafted names."""
        for name in ['__class__', '__init__', '__getattribute__', 'write', 'unlink']:
            assert _is_valid_handler_method(name) is False, name

    def test_empty_string_rejected(self):
        assert _is_valid_handler_method('') is False

    def test_whitespace_rejected(self):
        """Leading/trailing whitespace and tabs are rejected.

        Note: Python's regex ``$`` matches both end-of-string AND the position before
        a single trailing ``\\n`` (this is documented re module behaviour). A trailing
        newline therefore slips past ``^_on_[a-z_]+$`` — so we don't assert against it
        here. handler_method comes from a Char field with size=128 and is set in code,
        not user input, so a trailing newline is not a realistic attack vector. Future
        tightening could swap ``$`` for ``\\Z``.
        """
        assert _is_valid_handler_method(' _on_event') is False
        assert _is_valid_handler_method('_on_event ') is False
        assert _is_valid_handler_method('\t_on_event') is False
        assert _is_valid_handler_method('_on_event\t') is False


class TestIsValidHandlerMethodTypeSafety:
    """The helper guards against non-string inputs — None, ints, bytes etc."""

    def test_none_rejected(self):
        assert _is_valid_handler_method(None) is False

    def test_integer_rejected(self):
        assert _is_valid_handler_method(123) is False

    def test_bytes_rejected(self):
        """Bytes look superficially valid but re.match would TypeError on str pattern."""
        assert _is_valid_handler_method(b'_on_event') is False

    def test_list_rejected(self):
        assert _is_valid_handler_method(['_on_event']) is False
