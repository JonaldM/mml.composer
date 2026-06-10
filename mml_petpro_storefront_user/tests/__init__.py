import odoo
_STUB = getattr(odoo, "_stubbed", False)

if _STUB:
    # Pure-Python: import pytest at module scope, function-only tests
    from . import test_acl_csv
    from . import test_record_rules
