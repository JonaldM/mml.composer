import odoo
_STUB = getattr(odoo, "_stubbed", False)

# Odoo-safe: TransactionCase subclasses (with @unittest.skipUnless guard),
# no module-level pytest import after MIXED fix
from . import test_bridge
from . import test_roq_freight_3pl_e2e

if _STUB:
    # Pure-Python: import pytest at module scope, no TransactionCase
    from . import test_bridge_handler
