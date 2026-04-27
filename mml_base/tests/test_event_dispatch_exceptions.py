"""Structural test: broad-exception handlers in mml_event_subscription are
permitted ONLY inside the savepoint-isolation pattern.

Background
----------
A bare ``except Exception:`` that only logs and continues is normally a
bug-swallower — it hides real failures. Two functions in this module are
intentional exceptions to that rule and must be allowed:

* ``MmlEventSubscription._dispatch_one`` — by design isolates a single
  subscriber so a failure in module B does not roll back module A's billable
  event. The handler exception is caught, the savepoint rolls back the
  handler's DB writes, and a row is logged to ``mml.event.dispatch.failure``.

* ``MmlEventSubscription._log_dispatch_failure`` — guards the failure-log
  ``create()`` itself; if logging fails we must not crash dispatch().

Anywhere else, a broad ``except Exception`` must re-raise after logging.
"""
import ast
import pathlib

# Functions where a non-re-raising broad exception handler is part of the
# intended contract. Adding a function here is a deliberate API decision and
# should be reviewed.
ISOLATION_ALLOWLIST = {'_dispatch_one', '_log_dispatch_failure'}


def _handler_re_raises(handler_node: ast.ExceptHandler) -> bool:
    """Return True if the except handler body contains a bare ``raise``."""
    for node in ast.walk(handler_node):
        if isinstance(node, ast.Raise) and node.exc is None:
            return True
    return False


def _enclosing_function_name(tree: ast.AST, target: ast.ExceptHandler) -> str | None:
    """Walk the tree and return the name of the FunctionDef enclosing
    ``target``, or None if it is at module/class level."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for descendant in ast.walk(node):
                if descendant is target:
                    return node.name
    return None


def test_dispatch_does_not_swallow_exceptions():
    src = pathlib.Path('mml_base/models/mml_event_subscription.py').read_text()
    tree = ast.parse(src)

    swallowing_handlers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_bare_except = node.type is None
        is_broad_exception = (
            isinstance(node.type, ast.Name) and node.type.id == 'Exception'
        )
        if not (is_bare_except or is_broad_exception):
            continue
        if _handler_re_raises(node):
            continue
        # Broad handler that does not re-raise — only OK inside the
        # explicit handler-isolation allowlist.
        fn_name = _enclosing_function_name(tree, node)
        if fn_name in ISOLATION_ALLOWLIST:
            continue
        kind = 'bare except' if is_bare_except else 'except Exception'
        swallowing_handlers.append((kind, fn_name or '<module>'))

    assert not swallowing_handlers, (
        f"Found broad exception handler(s) that do not re-raise outside the "
        f"isolation allowlist {sorted(ISOLATION_ALLOWLIST)} in "
        f"mml_event_subscription.py: {swallowing_handlers}. "
        f"Use 'except (AttributeError, TypeError)' for narrow handler errors, "
        f"and for 'except Exception' always re-raise after logging unless the "
        f"function is part of the documented savepoint-isolation pattern."
    )
