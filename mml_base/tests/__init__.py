import odoo
_STUB = getattr(odoo, "_stubbed", False)

# Odoo-safe: TransactionCase subclasses, no module-level pytest, no importlib exec
from . import test_capability
from . import test_registry
from . import test_event
from . import test_event_subscription
from . import test_license

if _STUB:
    # Pure-Python: use importlib exec_module at module scope, import pytest at
    # module scope, or are function-only (no TestCase)
    from . import test_event_dispatch_exceptions
    from . import test_pure_dispatch_isolation
    from . import test_pure_capability_register
    from . import test_pure_event_emit_signature
    from . import test_pure_event_subscription_regex
    from . import test_pure_null_service
    from . import test_pure_registry_constants
    from . import test_pure_event_idempotent_emit
    from . import test_pure_dispatch_failure_resolve
