import odoo
_STUB = getattr(odoo, "_stubbed", False)

# Odoo-safe: structural tests with no module-level pytest import after MIXED fix
from . import test_bridge

if _STUB:
    # Pure-Python: function-only tests (no TestCase)
    from . import test_bridge_handler
