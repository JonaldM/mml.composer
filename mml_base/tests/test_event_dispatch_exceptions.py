"""Structural test: dispatch catches specific exception types, not bare Exception.

An 'except Exception' handler is acceptable only if it re-raises (i.e. contains
a bare 'raise' statement). A handler that catches Exception and only logs without
re-raising is a bug swallower that hides real failures.
"""
import ast
import pathlib


def _handler_re_raises(handler_node: ast.ExceptHandler) -> bool:
    """Return True if the except handler body contains a bare 'raise' statement."""
    for node in ast.walk(handler_node):
        if isinstance(node, ast.Raise) and node.exc is None:
            return True
    return False


def test_dispatch_does_not_swallow_exceptions():
    src = pathlib.Path('mml_base/models/mml_event_subscription.py').read_text()
    tree = ast.parse(src)

    swallowing_handlers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            is_bare_except = node.type is None
            is_broad_exception = (
                isinstance(node.type, ast.Name) and node.type.id == 'Exception'
            )
            if (is_bare_except or is_broad_exception) and not _handler_re_raises(node):
                kind = 'bare except' if is_bare_except else 'except Exception'
                swallowing_handlers.append(kind)

    assert not swallowing_handlers, (
        f"Found broad exception handler(s) that do not re-raise in "
        f"mml_event_subscription.py: {swallowing_handlers}. "
        f"Use 'except (AttributeError, TypeError)' for handler method errors, "
        f"and for 'except Exception' always re-raise after logging."
    )
