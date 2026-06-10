import odoo
_STUB = getattr(odoo, "_stubbed", False)

# Odoo-safe: TransactionCase subclasses, no module-level pytest
from . import test_allocation
from . import test_generate_sequences
from . import test_lifecycle
from . import test_import_wizard

if _STUB:
    # Pure-Python: import pytest at module scope, or function-only (no TestCase)
    from . import test_gs1
    from . import test_brand_tracking
    from . import test_reuse_error_message
