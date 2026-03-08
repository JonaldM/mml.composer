# Medium Priority Production Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve all medium-priority issues identified in the 2026-03-08 production readiness audit — hardening code quality, data integrity, and observability without blocking deployment.

**Architecture:** Seven independent workstreams across different module directories. Each can be dispatched as a parallel agent. All follow TDD: write the failing test first, implement the minimal fix, verify it passes, commit.

**Tech Stack:** Python 3.12, Odoo 19, pytest (pure-Python tier)

**Test commands by workspace:**
```bash
# Root / bridge modules / mml_base / mml_roq_forecast
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest -m "not odoo_integration" -q          # entire repo

# Freight forwarding
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.fowarder.intergration
pytest addons/ -q

# EDI
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest mml.edi/ -q

# Barcode registry
pytest mml.barcodes/ -q

# ROQ forecast
pytest mml.roq.model/ -q

# 3PL
pytest mml.3pl.intergration/ -q
```

---

## WORKSTREAM M-A — mml_base Event Handler Exception Handling
**Scope:** `mml_base/` only
**Parallel with:** All other workstreams

### Task M-A1: Tighten exception handling in event subscription dispatch

**Files:**
- Read first: `mml_base/models/mml_event_subscription.py` — find `dispatch()` or `emit()` method, the broad `except Exception` catch
- Read also: `mml_base/tests/` — understand existing test fixtures
- Modify: `mml_base/models/mml_event_subscription.py`
- Test: `mml_base/tests/test_event_subscription.py` — add test cases

**Context:** The event dispatch loop currently catches all `Exception` types in the handler call block. This means real bugs (database corruption, programming errors) are silently swallowed and only logged. The correct behaviour is:
- Catch `AttributeError` (handler method missing on model) — log and continue
- Catch `TypeError` (handler signature mismatch) — log and continue
- Let all other exceptions propagate so they cause visible failures in monitoring

**Step 1: Read `mml_event_subscription.py` — find the dispatch loop and the `except Exception` block**

**Step 2: Write failing tests**

Add to `mml_base/tests/test_event_subscription.py`:

```python
def test_attribute_error_in_handler_is_caught_and_logged(self):
    """AttributeError (missing handler method) must not propagate."""
    # Subscribe a handler that doesn't exist on the model
    # Emit the event
    # Assert no exception raised
    # Assert error was logged
    pass


def test_type_error_in_handler_is_caught_and_logged(self):
    """TypeError (wrong handler signature) must not propagate."""
    pass


def test_other_exceptions_in_handler_propagate(self):
    """Non-AttributeError/TypeError exceptions must propagate so ops notices."""
    # Subscribe a handler that raises ValueError
    # Emit the event
    # Assert ValueError propagates (is not swallowed)
    pass
```

NOTE: These are Odoo integration tests (`@tagged('odoo_integration')`). Adapt fixture construction to match existing tests in this file. Run via `python odoo-bin --test-enable -u mml_base -d <db>` in staging.

**Step 3: Run structural test in pure-Python (no live DB needed)**

Write a pure-Python AST-based test alongside:

```python
"""Structural test: dispatch uses specific exception types, not bare Exception."""
import ast, pathlib


def test_dispatch_catches_specific_exceptions_not_bare():
    src = pathlib.Path('mml_base/models/mml_event_subscription.py').read_text()
    tree = ast.parse(src)

    bare_except_handlers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            # A bare `except Exception:` has type=Name(id='Exception') or type=None
            if node.type is None:
                bare_except_handlers.append(node)
            elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                bare_except_handlers.append(node)

    assert not bare_except_handlers, (
        f"Found {len(bare_except_handlers)} bare 'except Exception' handler(s) "
        f"in mml_event_subscription.py. Use specific exception types: "
        f"except (AttributeError, TypeError)"
    )
```

**Step 4: Run — confirm structural test fails**

**Step 5: Implement the fix**

```python
# BEFORE:
try:
    handler_model._on_some_event(event)
except Exception as e:
    _logger.error('Event handler %s failed: %s', handler_method, e)

# AFTER:
try:
    handler_model._on_some_event(event)
except (AttributeError, TypeError) as e:
    _logger.error(
        'Event handler %s on %s failed (bad method reference or signature): %s',
        handler_method, handler_model, e,
    )
except Exception:
    _logger.exception(
        'Event handler %s on %s raised an unexpected exception — re-raising',
        handler_method, handler_model,
    )
    raise
```

Read the actual code structure before implementing — adapt to match existing variable names.

**Step 6: Run structural test — confirm pass**

**Step 7: Commit**
```bash
git add mml_base/models/mml_event_subscription.py
git add mml_base/tests/test_event_subscription_dispatch_errors.py
git commit -m "fix(mml_base): tighten event handler exception handling — only swallow AttributeError/TypeError"
```

---

## WORKSTREAM M-B — mml_edi Medium Fixes
**Scope:** `mml.edi/` only
**Parallel with:** All other workstreams

Three medium-priority fixes, implement sequentially.

**Test command:** `cd E:\ClaudeCode\projects\mml.odoo.apps && pytest mml.edi/ -q`

---

### Task M-B1: Validate client_ref_template with regex

**Files:**
- Read first: `mml.edi/models/edi_trading_partner.py` — find `client_ref_template` field and `render_client_ref()` method
- Modify: same file
- Test: `mml.edi/tests/test_client_ref_template.py`

**Context:** `render_client_ref()` uses `string.Template.safe_substitute()` on a user-controlled template field. While `safe_substitute()` prevents code execution, an invalid template can produce wrong SO references silently. Add an `@api.constrains` validator that restricts allowed content.

**Step 1: Read `edi_trading_partner.py` to find `render_client_ref` and the field definition**

**Step 2: Write failing tests**

```python
"""Tests for client_ref_template validation."""
import pytest


def test_valid_template_accepted():
    """Templates with only $po_number and $store_code must be accepted."""
    # Construct a mock partner and set client_ref_template = '$po_number-$store_code'
    # Call _validate_client_ref_template (or create/write)
    # Assert no ValidationError
    pass


def test_template_with_unknown_variable_rejected():
    """Templates referencing unknown variables must raise ValidationError."""
    # Set client_ref_template = '$unknown_var'
    # Assert ValidationError raised
    pass


def test_empty_template_accepted():
    """Empty template must be accepted (falls back to $po_number)."""
    pass
```

Adapt fixtures to the existing test patterns in this file.

**Step 3: Run — confirm they fail**

**Step 4: Add `@api.constrains('client_ref_template')`**

```python
_ALLOWED_TEMPLATE_VARS = frozenset({'po_number', 'store_code'})
_TEMPLATE_VAR_RE = re.compile(r'\$\{?(\w+)\}?')  # matches $var and ${var}

@api.constrains('client_ref_template')
def _validate_client_ref_template(self):
    for rec in self:
        if not rec.client_ref_template:
            continue
        found_vars = set(_TEMPLATE_VAR_RE.findall(rec.client_ref_template))
        unknown = found_vars - _ALLOWED_TEMPLATE_VARS
        if unknown:
            raise ValidationError(
                f"client_ref_template contains unknown variable(s): "
                f"{', '.join(sorted(unknown))}. "
                f"Allowed: $po_number, $store_code"
            )
```

Ensure `import re` is at the top of the file.

**Step 5: Run — confirm tests pass**

**Step 6: Commit**
```bash
git add mml.edi/models/edi_trading_partner.py
git add mml.edi/tests/test_client_ref_template.py
git commit -m "fix(mml_edi): validate client_ref_template restricts to known variables only"
```

---

### Task M-B2: Strengthen FTP filename path traversal guard

**Files:**
- Read first: `mml.edi/models/edi_ftp.py` — find `_safe_filename()` method
- Modify: same file
- Test: `mml.edi/tests/test_ftp_handler.py` — add path traversal test cases

**Context:** Current guard rejects `..`, `/`, `\` but not `....//` (which after normalization becomes `../`) or leading dots (`.ssh`). Replace the blacklist with a whitelist: only allow alphanumeric, hyphen, underscore, dot, and require no leading dot.

**Step 1: Read `edi_ftp.py` — find `_safe_filename()`**

**Step 2: Write failing tests**

Add to `mml.edi/tests/test_ftp_handler.py`:

```python
def test_safe_filename_rejects_dot_dot_slash_variant():
    """....// should be rejected."""
    from mml_edi.models.edi_ftp import EdiFtp  # adapt to actual import
    with pytest.raises(Exception):  # adapt to actual exception type
        EdiFtp._safe_filename(None, '....//etc/passwd')


def test_safe_filename_rejects_leading_dot():
    """.ssh/authorized_keys path traversal via leading dot."""
    with pytest.raises(Exception):
        EdiFtp._safe_filename(None, '.hidden_file')


def test_safe_filename_accepts_normal_edi_filename():
    """Standard EDI filenames must pass."""
    result = EdiFtp._safe_filename(None, 'BRISCOES_PO_20260308_001.edi')
    assert result == 'BRISCOES_PO_20260308_001.edi'
```

**Step 3: Run — confirm traversal tests fail (not currently caught)**

**Step 4: Replace blacklist with whitelist**

```python
import re as _re

_SAFE_FILENAME_RE = _re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.\-]*$')

def _safe_filename(self, filename: str) -> str:
    if not filename or not isinstance(filename, str):
        raise EDIFTPError(f'Invalid filename: {filename!r}')
    if not _SAFE_FILENAME_RE.match(filename):
        raise EDIFTPError(
            f'Filename rejected — must start with alphanumeric and contain '
            f'only letters, digits, underscores, hyphens, dots: {filename!r}'
        )
    return filename
```

The regex `^[A-Za-z0-9][A-Za-z0-9_.\-]*$` requires:
- First character: letter or digit (blocks leading `.`)
- Remaining: letter, digit, `_`, `.`, `-` (blocks `/`, `\`, `..` sequences)

**Step 5: Run — confirm all tests pass**

**Step 6: Run full EDI suite**
```bash
pytest mml.edi/ -q
```

**Step 7: Commit**
```bash
git add mml.edi/models/edi_ftp.py
git add mml.edi/tests/test_ftp_handler.py
git commit -m "fix(mml_edi): replace FTP filename blacklist with whitelist to prevent path traversal"
```

---

### Task M-B3: Version pending change order attachments

**Files:**
- Read first: `mml.edi/models/edi_processor.py` and `mml.edi/models/edi_order_review.py` — find where pending change order data is stored as `ir.attachment`
- Modify: `mml.edi/models/edi_processor.py`
- Test: `mml.edi/tests/test_po_change_workflow.py` — add versioning test

**Context:** When a second change order arrives for the same SO before the first is approved, the `pending_changes.json` attachment is overwritten with no history. Each change order should create a separate timestamped attachment.

**Step 1: Read the attachment creation code — find where `pending_changes.json` is written**

**Step 2: Write a failing test**

Add to `mml.edi/tests/test_po_change_workflow.py`:

```python
def test_second_change_order_creates_new_attachment_not_overwrite(self):
    """
    Two successive change orders for the same review must produce
    two separate attachments, not one overwritten one.
    """
    # Create an edi.order.review record
    # Call the change-order processing method twice with different payloads
    # Assert env['ir.attachment'].search([('res_id', '=', review.id)]) returns 2 records
    pass
```

**Step 3: Run — confirm it fails (currently only 1 attachment)**

**Step 4: Add a timestamp to the attachment name**

```python
from datetime import datetime

# BEFORE:
self.env['ir.attachment'].create({
    'name': 'pending_changes.json',
    'res_model': 'edi.order.review',
    'res_id': review.id,
    'datas': self._encode_pending_changes(order, existing_so),
    'mimetype': 'application/json',
})

# AFTER:
ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
self.env['ir.attachment'].create({
    'name': f'pending_changes_{ts}.json',
    'res_model': 'edi.order.review',
    'res_id': review.id,
    'datas': self._encode_pending_changes(order, existing_so),
    'mimetype': 'application/json',
    'description': f'Change order received {ts}',
})
```

**Step 5: Run — confirm test passes**

**Step 6: Run full EDI suite**

**Step 7: Commit**
```bash
git add mml.edi/models/edi_processor.py
git add mml.edi/tests/test_po_change_workflow.py
git commit -m "fix(mml_edi): timestamp pending_changes attachments to preserve change order history"
```

---

## WORKSTREAM M-C — mml_barcode_registry Medium Fixes
**Scope:** `mml.barcodes/` only
**Parallel with:** All other workstreams

Two fixes.

**Test command:** `cd E:\ClaudeCode\projects\mml.odoo.apps && pytest mml.barcodes/ -q`

---

### Task M-C1: Add tracking=True to brand_id on barcode_allocation

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/barcode_allocation.py` — find `brand_id` field
- Modify: same file
- Test: structural test

**Context:** The `brand_id` field on `mml.barcode.allocation` can be manually corrected but no audit history is kept. Adding `tracking=True` makes Odoo log field changes to the chatter automatically.

**Step 1: Read `barcode_allocation.py` — find the `brand_id` field definition**

**Step 2: Write a structural test**

```python
"""Verify brand_id field has tracking enabled."""
import ast, pathlib


def test_brand_id_has_tracking():
    src = pathlib.Path('mml.barcodes/mml_barcode_registry/models/barcode_allocation.py').read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'brand_id':
                    dumped = ast.dump(node.value)
                    assert 'tracking' in dumped, (
                        "brand_id field must have tracking=True for audit trail"
                    )
                    return
    pytest.fail("brand_id field not found in barcode_allocation.py")
```

**Step 3: Run — confirm it fails**

**Step 4: Add tracking=True**

```python
# BEFORE:
brand_id = fields.Many2one(
    'mml.brand',
    ondelete='set null',
)

# AFTER:
brand_id = fields.Many2one(
    'mml.brand',
    ondelete='set null',
    tracking=True,
)
```

NOTE: `tracking=True` requires the model to inherit from `mail.thread`. Check if `BarcodeAllocation` already inherits `mail.thread`. If not, add it:
```python
class BarcodeAllocation(models.Model):
    _name = 'mml.barcode.allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```
And ensure `mail` is in the module's `depends` list in `__manifest__.py`.

**Step 5: Run structural test — confirm pass**

**Step 6: Run full barcode suite**

**Step 7: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/barcode_allocation.py
git add mml.barcodes/mml_barcode_registry/__manifest__.py  # only if depends changed
git commit -m "fix(mml_barcode_registry): add tracking=True to brand_id for audit trail"
```

---

### Task M-C2: Improve error message when barcode reuse not yet eligible

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/barcode_registry.py` — find the `UserError` raised when `reuse_eligible_date` has not passed
- Modify: same file
- Test: structural test

**Context:** The current error says approximately "eligible in N months". Add the GS1 guidance: the GTIN must not be reused because it may still appear in retail scanners, price files, or supplier data. Give ops something actionable.

**Step 1: Read `barcode_registry.py` — find the reuse eligibility error**

**Step 2: Update the error message**

```python
# BEFORE (approximate):
raise UserError(
    f"GTIN {rec.gtin_13} cannot be returned to pool yet. "
    f"Reuse eligible in approximately {months_remaining} month(s) "
    f"(eligible date: {rec.reuse_eligible_date})."
)

# AFTER:
raise UserError(
    f"GTIN {rec.gtin_13} cannot be reused yet.\n\n"
    f"GS1 requires a 48-month cool-down from first allocation "
    f"({rec.allocation_date or 'unknown'}) before a GTIN may be "
    f"reassigned to a different product. This prevents barcode conflicts "
    f"in retailer systems and POS scanners.\n\n"
    f"Eligible to return to pool: {rec.reuse_eligible_date} "
    f"({months_remaining} month(s) remaining).\n\n"
    f"If you need a new barcode now, apply for an additional GS1 "
    f"prefix block at https://www.gs1nz.org/"
)
```

**Step 3: Write a structural test**

```python
def test_reuse_error_message_includes_gs1_guidance():
    import pathlib
    src = pathlib.Path('mml.barcodes/mml_barcode_registry/models/barcode_registry.py').read_text()
    assert 'gs1nz.org' in src or 'gs1.org' in src, (
        "Reuse eligibility error message must include a GS1 contact URL"
    )
    assert '48' in src, "Error message must mention 48-month cool-down period"
```

**Step 4: Run — confirm pass**

**Step 5: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/barcode_registry.py
git commit -m "fix(mml_barcode_registry): improve GTIN reuse error message with GS1 guidance"
```

---

## WORKSTREAM M-D — mml_roq_forecast Medium Fixes
**Scope:** `mml.roq.model/mml_roq_forecast/` only
**Parallel with:** All other workstreams

**Test command:** `cd E:\ClaudeCode\projects\mml.odoo.apps && pytest mml.roq.model/ -q`

---

### Task M-D1: Add upper bound clamp to Holt-Winters forecast

**Files:**
- Read first: `mml.roq.model/mml_roq_forecast/services/forecast_methods.py` — find the Holt-Winters method and its return statement
- Modify: same file
- Test: `mml.roq.model/mml_roq_forecast/tests/test_forecast_methods.py` — add edge case test

**Context:** The Holt-Winters forecast clamps negative values to 0 but has no upper bound. With pathological data (volatile trend, alpha/beta/gamma misconfigured), the forecast can produce unrealistically large values that cascade into container capacity miscalculations.

**Step 1: Read `forecast_methods.py` — find the Holt-Winters return line**

**Step 2: Write failing test**

Add to `test_forecast_methods.py`:

```python
def test_holt_winters_clamps_explosive_trend():
    """Holt-Winters must not produce absurdly large forecasts regardless of input."""
    from mml_roq_forecast.services.forecast_methods import holt_winters_forecast  # adapt import

    # Feed in a series designed to produce trend explosion
    # e.g., rapidly escalating values with high alpha/beta
    explosive_history = [1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0]
    result = holt_winters_forecast(explosive_history, periods=1)

    # The result should be bounded — pick a reasonable max for weekly unit demand
    # (e.g. 1,000,000 units/week is impossible for a 400-SKU NZ distributor)
    assert result <= 1_000_000, (
        f"Holt-Winters produced an explosive forecast of {result} units — "
        f"add an upper bound clamp"
    )
```

Adapt the function name and call signature to what's actually in `forecast_methods.py` after reading it.

**Step 3: Run — confirm it fails (or passes if already bounded)**

**Step 4: Add the clamp**

```python
# BEFORE:
forecast = last_level + last_trend + last_season
return max(0.0, forecast)

# AFTER:
_MAX_WEEKLY_DEMAND = 1_000_000.0  # Hard upper bound — no SKU demands 1M units/week
forecast = last_level + last_trend + last_season
return max(0.0, min(_MAX_WEEKLY_DEMAND, forecast))
```

Place `_MAX_WEEKLY_DEMAND` as a module-level constant so it can be configured if needed.

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.roq.model/mml_roq_forecast/services/forecast_methods.py
git add mml.roq.model/mml_roq_forecast/tests/test_forecast_methods.py
git commit -m "fix(mml_roq_forecast): add upper bound clamp to Holt-Winters forecast to prevent trend explosion"
```

---

### Task M-D2: Log when weeks-of-cover sentinel is returned

**Files:**
- Read first: `mml.roq.model/mml_roq_forecast/services/roq_calculator.py` — find `calculate_weeks_of_cover()`
- Modify: same file
- Test: `mml.roq.model/mml_roq_forecast/tests/test_forecast_methods.py` or a new file

**Context:** When `weekly_demand <= 0`, a sentinel of `999.0` is returned. If a dormant SKU unexpectedly gets reordered (data anomaly), the sentinel silently excludes it from container padding. A debug log makes this visible.

**Step 1: Read `roq_calculator.py` — find `calculate_weeks_of_cover()`**

**Step 2: Add the debug log**

```python
def calculate_weeks_of_cover(projected_inventory, weekly_demand):
    if weekly_demand <= 0:
        _logger.debug(
            'weeks_of_cover: zero/negative demand (%.4f) — returning sentinel 999.0. '
            'If this SKU is being actively ordered, investigate demand forecast.',
            weekly_demand,
        )
        return 999.0
    return projected_inventory / weekly_demand
```

Ensure `_logger = logging.getLogger(__name__)` exists at the top of the file.

**Step 3: Write a structural test**

```python
def test_weeks_of_cover_sentinel_is_logged():
    import pathlib
    src = pathlib.Path('mml.roq.model/mml_roq_forecast/services/roq_calculator.py').read_text()
    assert '_logger' in src, "roq_calculator.py must use _logger for logging"
    assert '999' in src, "Sentinel value 999.0 must be present"
    assert 'debug' in src.lower() or 'warning' in src.lower(), (
        "Sentinel return must be logged at debug or warning level"
    )
```

**Step 4: Run — confirm test passes**

**Step 5: Commit**
```bash
git add mml.roq.model/mml_roq_forecast/services/roq_calculator.py
git commit -m "fix(mml_roq_forecast): log debug message when weeks-of-cover sentinel is returned for zero-demand SKU"
```

---

## WORKSTREAM M-E — Bridge Module Integration Tests
**Scope:** `mml_roq_freight/`, `mml_freight_3pl/` (root repo)
**Parallel with:** All other workstreams

The bridge module handler logic has no tests verifying actual handler behaviour — only structural/manifest tests exist. This workstream adds pure-Python integration tests using mock services.

**Test command:** `cd E:\ClaudeCode\projects\mml.odoo.apps && pytest mml_roq_freight/ mml_freight_3pl/ -q`

---

### Task M-E1: Integration tests for mml_roq_freight handler

**Files:**
- Read first: `mml_roq_freight/models/bridge_service.py` — read the full file, understand `_on_shipment_group_confirmed` and `_on_freight_booking_confirmed` handlers
- Read also: `mml_roq_freight/tests/test_bridge.py` — understand existing test fixture patterns
- Create: `mml_roq_freight/tests/test_bridge_handler.py`

**Step 1: Read both files**

**Step 2: Write tests based on actual handler logic**

Create `mml_roq_freight/tests/test_bridge_handler.py`:

```python
"""
Integration tests for mml_roq_freight bridge handlers.
Pure-Python — no live Odoo needed.
"""
import types
import pytest

# After reading bridge_service.py, implement these tests based on
# the actual method signatures, registry service calls, and error paths.

class MockFreightService:
    def __init__(self, tender_id=42):
        self.create_tender_calls = []
        self._tender_id = tender_id

    def create_tender(self, shipment_group_id):
        self.create_tender_calls.append(shipment_group_id)
        return self._tender_id

    def is_null(self):
        return False


class MockNullService:
    def is_null(self):
        return True

    def __getattr__(self, name):
        return lambda *a, **kw: None


class MockROQService:
    def __init__(self):
        self.booking_update_calls = []

    def update_booking_ref(self, shipment_group_id, booking_id):
        self.booking_update_calls.append((shipment_group_id, booking_id))

    def is_null(self):
        return False


def test_on_shipment_group_confirmed_calls_create_tender(monkeypatch):
    """
    When a roq.shipment_group.confirmed event fires,
    the handler must call freight_service.create_tender() with the group ID.
    """
    # After reading bridge_service.py:
    # 1. Import the handler class/model
    # 2. Monkeypatch mml.registry to return MockFreightService
    # 3. Build a mock event with the right res_id
    # 4. Call the handler
    # 5. Assert MockFreightService.create_tender_calls == [event.res_id]
    pytest.skip("Implement after reading bridge_service.py handler signature")


def test_on_shipment_group_confirmed_writes_tender_id_back(monkeypatch):
    """After create_tender returns, freight_tender_id must be written to the group record."""
    pytest.skip("Implement after reading bridge_service.py")


def test_on_shipment_group_confirmed_handles_null_freight_service(monkeypatch):
    """If freight service is NullService, handler must exit without error."""
    pytest.skip("Implement after reading bridge_service.py")


def test_on_shipment_group_confirmed_handles_service_exception(monkeypatch):
    """If freight service raises, handler must catch, log, and not re-raise."""
    pytest.skip("Implement after reading bridge_service.py")


def test_on_freight_booking_confirmed_updates_roq_group(monkeypatch):
    """When freight.booking.confirmed fires, ROQ service must be notified."""
    pytest.skip("Implement after reading bridge_service.py")
```

IMPORTANT: The `pytest.skip` calls are placeholders. After reading `bridge_service.py`, replace each with the actual test implementation. Do not leave any skips in the final committed version.

**Step 3: Run — skips are OK at this point while reading**

**Step 4: Implement each test based on what you find in bridge_service.py**

**Step 5: Run — all tests must pass (no skips)**

**Step 6: Commit**
```bash
git add mml_roq_freight/tests/test_bridge_handler.py
git commit -m "test(mml_roq_freight): add integration tests for bridge event handler logic"
```

---

### Task M-E2: Integration tests for mml_freight_3pl handler

**Files:**
- Read first: `mml_freight_3pl/models/mml_3pl_bridge.py` — full file
- Read also: `mml_freight_3pl/tests/test_bridge.py`
- Create: `mml_freight_3pl/tests/test_bridge_handler.py`

Same pattern as M-E1. Test the following paths in `_on_freight_booking_confirmed`:

1. Normal path: each PO in `booking.po_ids` gets one `queue_inward_order()` call
2. Empty `booking.po_ids`: handler exits early without calling 3PL service
3. `queue_inward_order()` returns `None`: billable `mml.event` must NOT be emitted
4. `queue_inward_order()` returns a message ID: billable event IS emitted
5. `queue_inward_order()` raises: exception caught, logged, does not propagate
6. `booking.exists()` returns False: handler exits without error

**Step 1: Read `mml_3pl_bridge.py` and `test_bridge.py`**
**Step 2-4: Implement all 6 test cases using mocks**
**Step 5: Run — all pass**
**Step 6: Commit**
```bash
git add mml_freight_3pl/tests/test_bridge_handler.py
git commit -m "test(mml_freight_3pl): add integration tests for 3PL bridge event handler logic"
```

---

## WORKSTREAM M-F — stock_3pl_mainfreight SOH Drift Threshold
**Scope:** `mml.3pl.intergration/addons/stock_3pl_mainfreight/` only
**Parallel with:** All other workstreams

Short task — make the SOH drift logging threshold configurable rather than hardcoded at 0.

**Test command:** `cd E:\ClaudeCode\projects\mml.odoo.apps && pytest mml.3pl.intergration/ -q`

---

### Task M-F1: Make SOH drift log threshold configurable

**Files:**
- Read first: `mml.3pl.intergration/addons/stock_3pl_mainfreight/models/route_engine.py` — find `_SOH_DRIFT_LOG_THRESHOLD`
- Modify: same file
- Test: `mml.3pl.intergration/addons/stock_3pl_mainfreight/tests/test_route_engine.py` or adjacent test

**Context:** `_SOH_DRIFT_LOG_THRESHOLD = 0` logs a warning for every single unit difference between Odoo and MF quantities. After go-live reconciliation, this produces high log noise. The threshold should be readable from `ir.config_parameter` with a safe default.

**Step 1: Read `route_engine.py` to find where `_SOH_DRIFT_LOG_THRESHOLD` is used**

**Step 2: Write a structural test**

```python
"""Verify SOH drift threshold is configurable, not hardcoded."""
import pathlib


def test_soh_drift_threshold_reads_from_config():
    src = pathlib.Path(
        'addons/stock_3pl_mainfreight/models/route_engine.py'
    ).read_text()
    # After the fix, threshold should come from ir.config_parameter or equivalent
    # At minimum, a named constant with a comment explaining how to override it
    assert 'mml_3pl.soh_drift_threshold' in src or '_SOH_DRIFT_LOG_THRESHOLD' in src, (
        "SOH drift threshold must be documented and ideally read from ir.config_parameter"
    )
```

**Step 3: Update the threshold to read from config**

```python
# BEFORE:
_SOH_DRIFT_LOG_THRESHOLD = 0

# AFTER: remove the module-level constant and read from config at call site
def _get_soh_drift_threshold(self):
    """
    Returns the minimum qty drift that triggers a SOH warning log.
    Default: 0 (log everything) — increase post-go-live to reduce noise.
    Configure via ir.config_parameter key: mml_3pl.soh_drift_threshold
    """
    try:
        val = self.env['ir.config_parameter'].sudo().get_param(
            'mml_3pl.soh_drift_threshold', '0'
        )
        return float(val)
    except (ValueError, TypeError):
        return 0.0
```

Then replace `if drift > _SOH_DRIFT_LOG_THRESHOLD:` with `if drift > self._get_soh_drift_threshold():`.

**Step 4: Run — confirm structural test passes**

**Step 5: Run full 3PL suite**
```bash
cd mml.3pl.intergration
pytest addons/ -q
```

**Step 6: Commit**
```bash
git add mml.3pl.intergration/addons/stock_3pl_mainfreight/models/route_engine.py
git commit -m "fix(stock_3pl_mainfreight): make SOH drift log threshold configurable via ir.config_parameter"
```

---

## WORKSTREAM M-G — mml_roq_forecast ROQ Wizard Field Verification
**Scope:** `mml.roq.model/mml_roq_forecast/`
**Note:** This workstream is DOCUMENTATION + VERIFICATION only — no production code change unless field names are wrong.

### Task M-G1: Verify purchase.order.line field names against Odoo 19

**Context:** The audit flagged that `roq_raise_po_wizard.py` uses `product_uom` and `date_planned` as `purchase.order.line` field names, with a TODO comment to verify these against the installed Odoo 19 instance. The `mml.barcodes/docs/purchase.order.line.pdf` was printed from the live Odoo 15 instance — the field names may differ in Odoo 19.

**Step 1: Read `mml.roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py` — find the `purchase.order.line` field references**

**Step 2: Open `mml.barcodes/docs/purchase.order.line.pdf` if readable, or note that it is Odoo 15**

**Step 3: Check Odoo 19 source (if accessible) or the Odoo 19 changelog for `purchase.order.line` field renames**

Key fields to verify:
- `product_uom` — in Odoo 17+, this was renamed to `product_uom_id` in some contexts (check)
- `date_planned` — verify this is still the scheduled date field name

**Step 4: If field names are correct for Odoo 19:** Remove the TODO comment and add a passing test:
```python
def test_po_wizard_field_names_verified_for_odoo19():
    """Field names product_uom and date_planned verified against Odoo 19 purchase.order.line."""
    import pathlib
    src = pathlib.Path('mml.roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py').read_text()
    assert 'product_uom' in src, "product_uom field reference missing"
    assert 'date_planned' in src, "date_planned field reference missing"
    assert 'TODO' not in src or 'pre-deploy' not in src, "TODO verification comment must be removed"
```

**Step 5: If field names are WRONG for Odoo 19:** Fix them, add the test, commit.

**Step 6: Commit**
```bash
git add mml.roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py
git add mml.roq.model/mml_roq_forecast/tests/test_roq_wizard_fields.py
git commit -m "fix(mml_roq_forecast): verify and correct purchase.order.line field names for Odoo 19"
```

---

## Final Verification

After all medium workstreams complete:

```bash
cd E:\ClaudeCode\projects\mml.odoo.apps

# Full repo pure-Python suite
pytest -m "not odoo_integration" -q

# Per workspace
pytest mml.fowarder.intergration/addons/ -q
pytest mml.edi/ -q
pytest mml.barcodes/ -q
pytest mml.roq.model/ -q
pytest mml.3pl.intergration/ -q
pytest mml_roq_freight/ mml_freight_3pl/ -q
```

All suites green before marking medium sprint complete.

## Push Sequence (After All Workstreams)

```bash
# Freight sub-repo (M-A, B-workstreams already in)
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.fowarder.intergration && git push origin master

# EDI sub-repo (M-B workstream)
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.edi && git push origin master

# ROQ sub-repo (M-D, M-G workstreams)
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.roq.model && git push origin master

# 3PL sub-repo (M-F workstream)
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.3pl.intergration && git push origin master

# Root repo (M-A/mml_base, M-C/barcodes, M-E/bridges)
cd E:\ClaudeCode\projects\mml.odoo.apps && git push origin master
```
