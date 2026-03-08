# Production Readiness Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve all critical and high-priority issues identified in the 2026-03-08 production readiness audit so the codebase is safe to deploy to the MML Odoo 19 production instance.

**Architecture:** Five independent workstreams that touch separate module directories — each can be executed by a dedicated agent in parallel. No cross-workstream file conflicts. Every fix follows TDD: write a failing test, implement the minimal fix, verify it passes.

**Tech Stack:** Python 3.12, Odoo 19, PostgreSQL 15, pytest (pure-Python tier), paramiko, cryptography (Fernet)

**Module registry reference:** `mml.barcodes/docs/` contains PDFs of all Odoo model field definitions printed from the live instance. Consult `delivery.carrier.pdf`, `product.product.pdf`, `stock.picking.pdf` etc. when verifying field names.

**Test commands:**
```bash
# Freight workspace
cd E:\ClaudeCode\projects\mml.odoo.apps\mml.fowarder.intergration
pytest addons/ -q

# EDI workspace
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest mml.edi/ -q

# Barcode workspace
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest mml.barcodes/ -q
```

---

## WORKSTREAM A — Freight Carrier ACL + Webhook Auth Hardening
**Scope:** `mml_freight_knplus/`, `mml_freight_mainfreight/`
**Parallel with:** All other workstreams

Two carrier adapter modules ship with empty `ir.model.access.csv` files (header row only). This leaves `delivery.carrier` records — which carry OAuth secrets, API keys, and webhook secrets — readable and writable by any authenticated Odoo user. Additionally, the K+N webhook controller accepts unauthenticated requests in sandbox mode with no guard.

---

### Task A1: Add ACL rows to mml_freight_knplus

**Files:**
- Modify: `mml.fowarder.intergration/addons/mml_freight_knplus/security/ir.model.access.csv`

The file currently contains only the header row. `delivery.carrier` is the inherited model; its `model_id:id` in the ACL is `delivery.model_delivery_carrier`.

**Step 1: Read the current file to confirm header format**

```bash
cat mml.fowarder.intergration/addons/mml_freight_knplus/security/ir.model.access.csv
```
Expected: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`

**Step 2: Replace the file with correct ACL content**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_freight_carrier_knplus_user,freight.carrier K+N user,delivery.model_delivery_carrier,stock.group_stock_user,1,0,0,0
access_freight_carrier_knplus_manager,freight.carrier K+N manager,delivery.model_delivery_carrier,stock.group_stock_manager,1,1,1,1
```

**Step 3: Verify the file is valid CSV (no trailing blank lines, correct column count)**

```bash
python -c "
import csv
with open('mml.fowarder.intergration/addons/mml_freight_knplus/security/ir.model.access.csv') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 2, f'Expected 2 data rows, got {len(rows)}'
for r in rows:
    assert r['perm_read'] == '1', 'All rows must have perm_read=1'
print('OK:', len(rows), 'rows')
"
```

**Step 4: Commit**
```bash
git add mml.fowarder.intergration/addons/mml_freight_knplus/security/ir.model.access.csv
git commit -m "fix(mml_freight_knplus): add ACL rows to protect delivery.carrier records"
```

---

### Task A2: Add ACL rows to mml_freight_mainfreight

**Files:**
- Modify: `mml.fowarder.intergration/addons/mml_freight_mainfreight/security/ir.model.access.csv`

**Step 1: Same verification as A1**

**Step 2: Replace file content**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_freight_carrier_mf_user,freight.carrier Mainfreight user,delivery.model_delivery_carrier,stock.group_stock_user,1,0,0,0
access_freight_carrier_mf_manager,freight.carrier Mainfreight manager,delivery.model_delivery_carrier,stock.group_stock_manager,1,1,1,1
```

**Step 3: Verify**
Same CSV validation as A1, changing the file path.

**Step 4: Commit**
```bash
git add mml.fowarder.intergration/addons/mml_freight_mainfreight/security/ir.model.access.csv
git commit -m "fix(mml_freight_mainfreight): add ACL rows to protect delivery.carrier records"
```

---

### Task A3: Harden K+N webhook sandbox mode to fail-secure

**Files:**
- Read first: `mml.fowarder.intergration/addons/mml_freight_knplus/controllers/kn_webhook.py`
- Modify: same file
- Test: `mml.fowarder.intergration/addons/mml_freight_knplus/tests/test_kn_webhook.py` (create if it does not exist)

**Context:** The audit found that `kn_webhook.py` checks `x_knplus_environment`. In sandbox mode, it accepts all unauthenticated requests. Until K+N provides their auth spec, the endpoint should return HTTP `501 Not Implemented` in sandbox mode (refusing the request) rather than accepting it. This is fail-secure: ops know exactly why it's rejecting, and it cannot be exploited.

**Step 1: Read kn_webhook.py to understand the current conditional structure**

**Step 2: Write a failing test**

Create `mml.fowarder.intergration/addons/mml_freight_knplus/tests/test_kn_webhook_sandbox.py`:

```python
"""
Test that the K+N webhook controller returns 501 in sandbox mode.
Pure-Python test using Odoo stubs — no live Odoo needed.
"""
import sys
import types
import pytest


def _make_mock_request(body=b'{}', headers=None):
    """Minimal mock of Odoo request object."""
    mock = types.SimpleNamespace()
    mock.httprequest = types.SimpleNamespace()
    mock.httprequest.data = body
    mock.httprequest.headers = headers or {}
    return mock


def test_sandbox_mode_returns_501(monkeypatch):
    """Sandbox mode must not accept unauthenticated requests."""
    from mml_freight_knplus.controllers.kn_webhook import KnWebhookController
    controller = KnWebhookController()

    # Build a carrier stub that reports sandbox mode
    carrier = types.SimpleNamespace(
        id=1,
        x_knplus_environment='sandbox',
        exists=lambda: True,
    )

    # The method under test should return HTTP 501, not 200
    # Read kn_webhook.py to find the correct method name and adapt this test
    # Expected: response.status_code == 501 or similar rejection
    # This test intentionally fails until the fix is applied
    pytest.fail("Implement after reading kn_webhook.py structure")
```

NOTE: After reading `kn_webhook.py`, replace the `pytest.fail` with the actual assertion against the controller method. The method likely calls `request.make_json_response(...)` — mock `request` and assert the status code is 501.

**Step 3: Run the test — confirm it fails for the right reason**

```bash
cd mml.fowarder.intergration
pytest addons/mml_freight_knplus/tests/test_kn_webhook_sandbox.py -v
```

**Step 4: Implement the fix**

In `kn_webhook.py`, find the branch that handles sandbox mode and change it to return 501:

```python
# BEFORE (accepting sandbox requests):
# ... some branch that logs a warning and returns 200 ...

# AFTER: sandbox must refuse until auth is implemented
if environment == 'sandbox':
    _logger.warning(
        'K+N webhook: auth not yet implemented for carrier %s; '
        'returning 501 until K+N provides HMAC or API key spec.',
        carrier_id,
    )
    return request.make_json_response(
        {'status': 'not_implemented', 'message': 'Webhook auth pending K+N onboarding'},
        status=501,
    )
```

**Step 5: Update the test to assert 501, run it, confirm it passes**

**Step 6: Commit**
```bash
git add mml.fowarder.intergration/addons/mml_freight_knplus/controllers/kn_webhook.py
git add mml.fowarder.intergration/addons/mml_freight_knplus/tests/test_kn_webhook_sandbox.py
git commit -m "fix(mml_freight_knplus): return 501 in sandbox mode until K+N auth is implemented"
```

---

### Task A4: Move mml_freight_mainfreight webhook metadata logging post-auth

**Files:**
- Read first: `mml.fowarder.intergration/addons/mml_freight_mainfreight/controllers/mf_webhook.py`
- Modify: same file

**Context:** The audit found that `message_type` and `message_id` are extracted from the request body (and potentially logged) **before** auth validation completes. If logs are compromised, an attacker can correlate message IDs to internal tracking events.

**Step 1: Read `mf_webhook.py` — identify lines that extract `message_type`/`message_id` before auth**

**Step 2: Write a test that verifies auth happens before any body parsing**

Add to `mml.fowarder.intergration/addons/mml_freight_mainfreight/tests/test_mf_webhook_auth_order.py`:

```python
"""Verify auth check precedes body parsing in mf_webhook controller."""
import ast
import pathlib


def test_auth_check_before_body_parse():
    """
    Parse the AST of mf_webhook.py and verify that the auth validation
    call appears before any reference to message_type or message_id
    in the main handler method.
    """
    src = pathlib.Path(
        'addons/mml_freight_mainfreight/controllers/mf_webhook.py'
    ).read_text()
    tree = ast.parse(src)

    # Find the main handler method (look for def that handles POST)
    # Walk the AST: auth call must come before message_type assignment
    # This is an AST structural test — adapt to the actual method name after reading the file
    assert 'auth' in src.lower(), "No auth reference found in webhook controller"
    # After reading the file, add a precise assertion that the auth line number
    # is less than the message_type extraction line number
```

**Step 3: After reading the file, implement the structural reorder**

Move the lines that do `message_type = body.get(...)` and `message_id = body.get(...)` to after the auth check completes. Ensure no logging of these values occurs before auth.

**Step 4: Run tests**
```bash
pytest addons/mml_freight_mainfreight/tests/ -v
```

**Step 5: Commit**
```bash
git add mml.fowarder.intergration/addons/mml_freight_mainfreight/controllers/mf_webhook.py
git add mml.fowarder.intergration/addons/mml_freight_mainfreight/tests/test_mf_webhook_auth_order.py
git commit -m "fix(mml_freight_mainfreight): move message metadata extraction to post-auth"
```

---

## WORKSTREAM B — mml_freight + mml_freight_dsv Medium Fixes
**Scope:** `mml_freight/`, `mml_freight_dsv/`
**Parallel with:** All other workstreams

---

### Task B1: Add @api.depends to computed fields in freight_booking.py

**Files:**
- Read first: `mml.fowarder.intergration/addons/mml_freight/models/freight_booking.py` (lines ~170-200)
- Modify: same file

**Context:** `_compute_current_status()` and `_compute_transit_kpis()` are missing explicit `@api.depends` decorators. The ORM caches computed fields — without explicit dependencies, stale values will be served after related records change.

**Step 1: Read `freight_booking.py` lines 170-200 to confirm the exact method signatures**

**Step 2: Write a failing structural test**

Add to `mml.fowarder.intergration/addons/mml_freight/tests/test_booking_computed_fields.py`:

```python
"""Verify computed field methods have @api.depends decorators."""
import ast
import pathlib


def _get_method_decorators(source: str, method_name: str) -> list[str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return [ast.dump(d) for d in node.decorator_list]
    return []


def test_compute_current_status_has_depends():
    src = pathlib.Path('addons/mml_freight/models/freight_booking.py').read_text()
    decorators = _get_method_decorators(src, '_compute_current_status')
    assert any('depends' in d for d in decorators), (
        '_compute_current_status must have @api.depends'
    )


def test_compute_transit_kpis_has_depends():
    src = pathlib.Path('addons/mml_freight/models/freight_booking.py').read_text()
    decorators = _get_method_decorators(src, '_compute_transit_kpis')
    assert any('depends' in d for d in decorators), (
        '_compute_transit_kpis must have @api.depends'
    )
```

**Step 3: Run — confirm they fail**

```bash
cd mml.fowarder.intergration
pytest addons/mml_freight/tests/test_booking_computed_fields.py -v
```

**Step 4: Add the decorators**

Based on what the methods compute, add appropriate `@api.depends`. The audit identified:
- `_compute_current_status`: depends on `tracking_event_ids.status`, `tracking_event_ids.event_date`
- `_compute_transit_kpis`: depends on `actual_pickup_date`, `actual_delivery_date`, `eta`

Read the actual method bodies to confirm these are the right fields before adding decorators.

**Step 5: Run — confirm tests pass**

**Step 6: Commit**
```bash
git add addons/mml_freight/models/freight_booking.py
git add addons/mml_freight/tests/test_booking_computed_fields.py
git commit -m "fix(mml_freight): add missing @api.depends to computed booking fields"
```

---

### Task B2: Add company filter to freight cost product search

**Files:**
- Read first: `mml.fowarder.intergration/addons/mml_freight/models/freight_booking.py` (search for `_get_freight_cost_product`)
- Modify: same file
- Test: `mml.fowarder.intergration/addons/mml_freight/tests/test_freight_cost_product.py`

**Context:** `_get_freight_cost_product()` searches `product.product` by name only. In multi-company setups this returns a product from any company.

**Step 1: Read the method**

**Step 2: Write a failing test**

```python
"""Verify _get_freight_cost_product searches within company scope."""
import ast
import pathlib


def test_freight_cost_product_search_includes_company_filter():
    src = pathlib.Path('addons/mml_freight/models/freight_booking.py').read_text()
    # The search domain must include company_id
    # Look for the _get_freight_cost_product method body
    assert 'company_id' in src, (
        "_get_freight_cost_product must filter by company_id to avoid cross-company contamination"
    )
```

This is a simple grep-based structural test. After reading the method, write a more precise AST test if needed.

**Step 3: Run — confirm it fails**

**Step 4: Update the domain**

```python
# BEFORE:
product = self.env['product.product'].search(
    [('name', '=', 'Freight Cost')], limit=1
)

# AFTER:
product = self.env['product.product'].search([
    ('name', '=', 'Freight Cost'),
    ('company_id', 'in', [self.company_id.id, False]),
], limit=1)
```

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add addons/mml_freight/models/freight_booking.py
git add addons/mml_freight/tests/test_freight_cost_product.py
git commit -m "fix(mml_freight): add company filter to freight cost product search"
```

---

### Task B3: Restrict DSV wizard ACL to stock managers

**Files:**
- Read first: `mml.fowarder.intergration/addons/mml_freight_dsv/security/ir.model.access.csv`
- Modify: same file

**Context:** The wizard ACL grants `base.group_user` full CRUD on the document upload wizard transient model. Only logistics managers should be able to trigger DSV document uploads.

**Step 1: Read the file to see the exact rows**

**Step 2: Write a test**

```python
"""Verify DSV wizard ACL is restricted to stock managers."""
import csv
import pathlib


def test_dsv_wizard_acl_restricted_to_managers():
    with open('addons/mml_freight_dsv/security/ir.model.access.csv') as f:
        rows = list(csv.DictReader(f))

    wizard_rows = [r for r in rows if 'wizard' in r['name'].lower() or 'wizard' in r['id'].lower()]
    assert wizard_rows, "No wizard ACL rows found"

    for row in wizard_rows:
        assert 'group_user' not in row['group_id:id'], (
            f"Wizard ACL row '{row['id']}' must not grant to base.group_user; "
            f"restrict to stock.group_stock_manager"
        )
```

**Step 3: Run — confirm it fails**

**Step 4: Update ACL**

Change `base.group_user` to `stock.group_stock_manager` on all wizard ACL rows.

**Step 5: Run — confirm it passes**

**Step 6: Run full freight test suite**
```bash
pytest addons/ -q
```

**Step 7: Commit**
```bash
git add addons/mml_freight_dsv/security/ir.model.access.csv
git commit -m "fix(mml_freight_dsv): restrict doc upload wizard ACL to stock managers"
```

---

## WORKSTREAM C — mml_edi Critical + High Fixes
**Scope:** `mml.edi/` (module root is `mml.edi/`, not a subdirectory)
**Parallel with:** All other workstreams

Five fixes in priority order. All touch different files — implement sequentially within this workstream.

**Important:** The `mml.edi` module root is `E:\ClaudeCode\projects\mml.odoo.apps\mml.edi\`. The `__manifest__.py` is at that root. Models are in `mml.edi/models/`, parsers in `mml.edi/parsers/`, services in `mml.edi/services/`.

**Run tests with:**
```bash
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest mml.edi/ -q
```

---

### Task C1: Fix HTML injection in cron alert email

**Files:**
- Read first: `mml.edi/models/edi_processor.py` (search for `_send_cron_alert` or `mail.mail`)
- Modify: same file
- Test: `mml.edi/tests/test_processor.py` — add a test, or create `mml.edi/tests/test_cron_alert_escaping.py`

**Context:** `body_html` is constructed as `'<pre>%s</pre>' % body` where `body` is an exception message (potentially containing partner filenames, system paths, or special characters). This is an XSS risk in email clients.

**Step 1: Read `edi_processor.py` — find `_send_cron_alert` method**

**Step 2: Write a failing test**

```python
"""Verify cron alert emails escape HTML in the body."""
import html as html_lib


def test_alert_body_is_html_escaped():
    """
    The body passed to mail.mail must be HTML-escaped.
    Simulate a body containing HTML-special chars and verify the
    rendered body_html does not contain raw angle brackets.
    """
    raw_body = 'Error: file <briscoes_order.edi> contains & invalid chars'
    escaped = html_lib.escape(raw_body)

    assert '<' not in escaped, "html.escape must convert < to &lt;"
    assert '>' not in escaped, "html.escape must convert > to &gt;"
    assert '&amp;' in escaped, "html.escape must convert & to &amp;"

    # This test validates our fix strategy. The actual integration test
    # verifying _send_cron_alert uses html.escape is an AST structural test:
    import ast, pathlib
    src = pathlib.Path('mml.edi/models/edi_processor.py').read_text()
    assert 'html.escape' in src or 'markupsafe' in src, (
        "edi_processor.py must use html.escape() or markupsafe.escape() "
        "before embedding body in body_html"
    )
```

**Step 3: Run — confirm AST assertion fails**

**Step 4: Apply the fix**

In `edi_processor.py`, add `import html` at the top of the file (if not already present) and change the body_html construction:

```python
# BEFORE:
'body_html': '<pre>%s</pre>' % body,

# AFTER:
'body_html': '<pre>%s</pre>' % html.escape(body),
```

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.edi/models/edi_processor.py
git add mml.edi/tests/test_cron_alert_escaping.py
git commit -m "fix(mml_edi): escape HTML in cron alert email body to prevent XSS"
```

---

### Task C2: Add cron alert rate limiting

**Files:**
- Read first: `mml.edi/models/edi_processor.py` — find `_send_cron_alert` and the cron poll loop
- Modify: `mml.edi/models/edi_processor.py`
- Test: `mml.edi/tests/test_cron_alert_rate_limit.py`

**Context:** If the FTP server goes offline, a cron alert fires every 15 minutes (96 emails/day per partner). Add a cooldown: after an alert is sent, suppress subsequent alerts for the same partner for 1 hour.

**Strategy:** Use `ir.config_parameter` to store the timestamp of the last alert per partner. Key pattern: `mml_edi.last_alert.{partner_code}`. Check this key in `_send_cron_alert` before sending.

**Step 1: Read `_send_cron_alert` and the cron loop to understand the current call pattern**

**Step 2: Write a failing test**

```python
"""Test that cron alerts are rate-limited to one per hour per partner."""
import types
from datetime import datetime, timezone, timedelta
import pytest


class MockConfigParam:
    """Stub for ir.config_parameter."""
    def __init__(self, stored_value=None):
        self._store = {}
        if stored_value is not None:
            self._store['mml_edi.last_alert.BRISCOES'] = stored_value

    def get_param(self, key, default=False):
        return self._store.get(key, default)

    def set_param(self, key, value):
        self._store[key] = value


def test_alert_suppressed_within_cooldown(monkeypatch):
    """Second alert within 1h of first must be suppressed."""
    from mml_edi.models.edi_processor import EdiProcessor  # adjust import to actual module path

    processor = object.__new__(EdiProcessor)

    recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    mock_env = types.SimpleNamespace(
        **{'ir.config_parameter': types.SimpleNamespace(sudo=lambda: MockConfigParam(recent_ts))}
    )
    processor.env = mock_env

    emails_sent = []
    monkeypatch.setattr(processor, '_do_send_alert', lambda *a, **kw: emails_sent.append(1))

    partner = types.SimpleNamespace(code='BRISCOES')
    processor._send_cron_alert('mml_edi', 'EDI poll failed', 'connection refused', partner=partner)

    assert len(emails_sent) == 0, "Alert should be suppressed within cooldown window"


def test_alert_sent_after_cooldown_expires(monkeypatch):
    """Alert must fire when last alert was > 1h ago."""
    from mml_edi.models.edi_processor import EdiProcessor

    processor = object.__new__(EdiProcessor)

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    mock_env = types.SimpleNamespace(
        **{'ir.config_parameter': types.SimpleNamespace(sudo=lambda: MockConfigParam(old_ts))}
    )
    processor.env = mock_env

    emails_sent = []
    monkeypatch.setattr(processor, '_do_send_alert', lambda *a, **kw: emails_sent.append(1))

    partner = types.SimpleNamespace(code='BRISCOES')
    processor._send_cron_alert('mml_edi', 'EDI poll failed', 'connection refused', partner=partner)

    assert len(emails_sent) == 1, "Alert should fire after cooldown expires"
```

NOTE: After reading the actual `_send_cron_alert` signature and implementation, adapt these tests to match the real parameter names and call pattern. The test structure above shows the intent — adapt to reality.

**Step 3: Run — confirm they fail**

**Step 4: Implement rate limiting in `_send_cron_alert`**

Refactor `_send_cron_alert` to:
1. Extract the actual send logic into `_do_send_alert` (internal)
2. Before calling `_do_send_alert`, check `ir.config_parameter` for `mml_edi.last_alert.{partner.code}`
3. If the stored timestamp is within 1 hour, log a debug message and return without sending
4. If sending, update the config param with the current UTC timestamp

```python
_ALERT_COOLDOWN_SECONDS = 3600  # 1 hour

def _send_cron_alert(self, module_name, subject, body, partner=None):
    partner_key = partner.code if partner else 'global'
    param_key = f'mml_edi.last_alert.{partner_key}'

    last_alert_str = self.env['ir.config_parameter'].sudo().get_param(param_key, '')
    if last_alert_str:
        try:
            from datetime import datetime, timezone
            last_alert = datetime.fromisoformat(last_alert_str)
            elapsed = (datetime.now(timezone.utc) - last_alert).total_seconds()
            if elapsed < _ALERT_COOLDOWN_SECONDS:
                _logger.debug(
                    'EDI alert suppressed for %s (last sent %.0fs ago, cooldown %ds)',
                    partner_key, elapsed, _ALERT_COOLDOWN_SECONDS,
                )
                return
        except (ValueError, TypeError):
            pass  # Malformed stored value — send the alert

    self._do_send_alert(module_name, subject, body)
    self.env['ir.config_parameter'].sudo().set_param(
        param_key,
        datetime.now(timezone.utc).isoformat(),
    )
```

**Step 5: Run — confirm tests pass**

**Step 6: Run full test suite**
```bash
pytest mml.edi/ -q
```

**Step 7: Commit**
```bash
git add mml.edi/models/edi_processor.py
git add mml.edi/tests/test_cron_alert_rate_limit.py
git commit -m "fix(mml_edi): rate-limit cron failure alerts to one per hour per partner"
```

---

### Task C3: Fix ASN silent skip — raise UserError on missing EAN-13

**Files:**
- Read first: `mml.edi/services/edi_service.py` — find ASN generation, the `len(barcode) != 13` branch
- Modify: same file
- Test: `mml.edi/tests/test_edi_service.py` — add test case

**Context:** The ASN generator silently skips stock moves where the product has no valid EAN-13. Trading partners may reject an incomplete ASN or process a partial shipment without knowing items are missing. The correct behaviour is to block the ASN and route the picking to a review queue.

**Step 1: Read `edi_service.py` to find the skip logic**

**Step 2: Write a failing test that expects a UserError instead of silent skip**

Read the existing `test_edi_service.py` to understand the test fixture pattern, then add:

```python
def test_asn_generation_raises_on_missing_barcode(self):
    """ASN generation must raise UserError when a move line has no valid EAN-13."""
    # Build a mock picking with a move that has a product without a barcode
    # Call the ASN generator
    # Assert that UserError is raised (not that the move is silently skipped)
    # Adapt the fixture construction to match the existing test helpers in this file
    pass
```

**Step 3: Run — confirm it fails (currently the code silently skips)**

**Step 4: Change the silent skip to a UserError**

```python
# BEFORE:
barcode = move.product_id.barcode or ''
if len(barcode) != 13:
    _logger.warning(
        'EDI ASN: product %s has no valid EAN-13 — line skipped',
        move.product_id.display_name,
    )
    continue

# AFTER:
barcode = move.product_id.barcode or ''
if len(barcode) != 13:
    raise UserError(
        f"Cannot generate ASN: product '{move.product_id.display_name}' "
        f"(ref: {move.product_id.default_code or 'N/A'}) has no valid EAN-13 barcode. "
        f"Assign a barcode before confirming despatch."
    )
```

Ensure `UserError` is imported from `odoo.exceptions` at the top of the file.

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.edi/services/edi_service.py
git add mml.edi/tests/test_edi_service.py
git commit -m "fix(mml_edi): raise UserError on missing EAN-13 during ASN generation instead of silently skipping"
```

---

### Task C4: Log replacement characters in EDIFACT encoding

**Files:**
- Read first: `mml.edi/parsers/briscoes.py` — find the `raw.decode("cp1252", errors="replace")` line
- Modify: same file
- Test: `mml.edi/tests/test_briscoes_edifact_parser.py` — add encoding test case

**Context:** Files encoded in anything other than Windows-1252 are silently corrupted. We cannot auto-detect encoding without a sample library, but we can at minimum log a warning when the Python replacement character (`\ufffd`) appears in the decoded text, alerting ops that data may be corrupt.

**Step 1: Read `briscoes.py` to find the decode call and understand the file structure**

**Step 2: Write a failing test**

```python
def test_non_cp1252_bytes_trigger_warning(caplog):
    """Bytes that are invalid in cp1252 must produce a logged warning."""
    import logging
    from mml_edi.parsers.briscoes import BriscoesParser  # adapt to actual class name

    # UTF-8 encoded em-dash (3 bytes: 0xE2 0x80 0x94) is invalid in cp1252
    invalid_bytes = b'UNA:+.? \rUNB+UNOA:1' + '\u2014'.encode('utf-8') + b'\rUNZ'

    with caplog.at_level(logging.WARNING):
        # Call whatever parse/decode entry point exists — read the file first
        # to find the right method name
        pass  # Replace with actual call

    assert any('replacement' in r.message.lower() or 'corrupt' in r.message.lower()
               for r in caplog.records), (
        "A warning must be logged when replacement characters are found"
    )
```

**Step 3: Run — confirm it fails (no warning currently emitted)**

**Step 4: Add the warning after the decode call**

```python
# BEFORE:
text = raw.decode("cp1252", errors="replace")

# AFTER:
text = raw.decode("cp1252", errors="replace")
replacement_count = text.count('\ufffd')
if replacement_count:
    _logger.warning(
        'EDI: file contains %d byte(s) invalid in cp1252 encoding; '
        'data may be corrupt. If the trading partner uses UTF-8 or '
        'ISO-8859-1, contact MML IT to update the encoding configuration.',
        replacement_count,
    )
```

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.edi/parsers/briscoes.py
git add mml.edi/tests/test_briscoes_edifact_parser.py
git commit -m "fix(mml_edi): log warning when EDIFACT file contains non-cp1252 bytes"
```

---

### Task C5: Encrypt FTP passwords at rest

**Files:**
- Read first: `mml.edi/models/edi_trading_partner.py` — find `ftp_password` field and any read/write of it
- Read also: `mml.3pl.intergration/addons/stock_3pl_core/utils/credential_store.py` — the Fernet pattern to copy
- Create: `mml.edi/utils/__init__.py` and `mml.edi/utils/credential_store.py`
- Modify: `mml.edi/models/edi_trading_partner.py`
- Modify: `mml.edi/models/edi_ftp.py` — wherever ftp_password is read for connection
- Test: `mml.edi/tests/test_ftp_credential_encryption.py`

**Context:** FTP passwords are stored as plain text in the database. A database dump exposes all trading partner FTP credentials. Apply Fernet AES encryption using the same pattern as `stock_3pl_core`.

**Step 1: Read `credential_store.py` in stock_3pl_core to understand the exact Fernet pattern**

**Step 2: Read `edi_trading_partner.py` to find ftp_password field, and `edi_ftp.py` to find where it is read**

**Step 3: Write failing tests**

```python
"""Tests for EDI FTP credential encryption."""
import pytest


def test_ftp_password_roundtrip():
    """Encrypted password must decrypt to the original value."""
    from mml_edi.utils.credential_store import encrypt_credential, decrypt_credential

    master_key = None  # Will generate a new one
    plaintext = 'hunter2'
    encrypted = encrypt_credential(plaintext, master_key)

    assert encrypted.startswith('enc:'), "Encrypted value must be prefixed with 'enc:'"
    assert plaintext not in encrypted, "Plaintext must not appear in encrypted value"

    decrypted = decrypt_credential(encrypted, master_key)
    assert decrypted == plaintext


def test_legacy_plaintext_passes_through():
    """Existing plaintext values must be returned as-is with a warning."""
    from mml_edi.utils.credential_store import decrypt_credential

    result = decrypt_credential('legacy_plain_password', None)
    assert result == 'legacy_plain_password', "Legacy plaintext must pass through unchanged"
```

**Step 4: Run — confirm they fail (module does not exist yet)**

**Step 5: Create `mml.edi/utils/` package**

Create `mml.edi/utils/__init__.py` (empty).

Create `mml.edi/utils/credential_store.py` — copy the Fernet pattern from `stock_3pl_core/utils/credential_store.py` with these adaptations:
- Change the `ir.config_parameter` key from `3pl.fernet_master_key` to `mml_edi.fernet_master_key`
- Function signatures must match: `encrypt_credential(plaintext, env)` and `decrypt_credential(ciphertext, env)` where `env` is passed in (not read from self)

**Step 6: Integrate into `edi_trading_partner.py`**

Override `create()` and `write()` to encrypt ftp_password before storing:

```python
def create(self, vals):
    if 'ftp_password' in vals and vals['ftp_password']:
        from odoo.addons.mml_edi.utils.credential_store import encrypt_credential
        vals['ftp_password'] = encrypt_credential(vals['ftp_password'], self.env)
    return super().create(vals)

def write(self, vals):
    if 'ftp_password' in vals and vals['ftp_password']:
        val = vals['ftp_password']
        if not val.startswith('enc:'):  # Don't double-encrypt
            from odoo.addons.mml_edi.utils.credential_store import encrypt_credential
            vals['ftp_password'] = encrypt_credential(val, self.env)
    return super().write(vals)
```

Add a `get_ftp_password()` method that decrypts and returns the plaintext:

```python
def get_ftp_password(self):
    self.ensure_one()
    from odoo.addons.mml_edi.utils.credential_store import decrypt_credential
    return decrypt_credential(self.ftp_password or '', self.env)
```

**Step 7: Update `edi_ftp.py`**

Replace any direct read of `partner.ftp_password` with `partner.get_ftp_password()`.

**Step 8: Run tests**
```bash
pytest mml.edi/ -q
```

**Step 9: Commit**
```bash
git add mml.edi/utils/__init__.py mml.edi/utils/credential_store.py
git add mml.edi/models/edi_trading_partner.py mml.edi/models/edi_ftp.py
git add mml.edi/tests/test_ftp_credential_encryption.py
git commit -m "fix(mml_edi): encrypt FTP passwords at rest using Fernet AES"
```

---

## WORKSTREAM D — mml_barcode_registry Critical + High Fixes
**Scope:** `mml.barcodes/mml_barcode_registry/`
**Parallel with:** All other workstreams

**Run tests with:**
```bash
cd E:\ClaudeCode\projects\mml.odoo.apps
pytest mml.barcodes/ -q
```

**Note:** The `mml.barcodes/docs/` directory contains PDFs of Odoo model field definitions from the live instance. Consult `product.product.pdf` and `stock.quant.pdf` when verifying field names used in product_product.py.

---

### Task D1: Add constraint preventing multiple active allocations per product

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/barcode_allocation.py`
- Read also: `mml.barcodes/mml_barcode_registry/models/product_product.py` — see `allocate_gtin()`
- Modify: `mml.barcodes/mml_barcode_registry/models/barcode_allocation.py`
- Test: `mml.barcodes/mml_barcode_registry/tests/test_allocation.py` — add test cases

**Context:** No constraint prevents a product from accumulating two `status='active'` allocations simultaneously. Need both an ORM-level `@api.constrains` guard and a pre-creation check in `allocate_gtin`.

**Step 1: Read both files**

**Step 2: Write failing tests**

Add to `test_allocation.py`:

```python
def test_cannot_create_second_active_allocation_for_same_product(self):
    """Creating a second active allocation for the same product must raise."""
    # Given: a product already has an active allocation
    # When: we try to create a second active allocation for the same product + company
    # Then: ValidationError must be raised
    # Adapt fixture construction to match existing test helpers in this file
    pass


def test_can_create_active_allocation_after_previous_is_dormant(self):
    """A product whose allocation is dormant may receive a new active one."""
    pass
```

**Step 3: Run — confirm they fail**

**Step 4: Add `@api.constrains` to `barcode_allocation.py`**

```python
from odoo.exceptions import ValidationError

@api.constrains('product_id', 'company_id', 'status')
def _check_unique_active_allocation(self):
    for rec in self:
        if rec.status != 'active':
            continue
        duplicate = self.search([
            ('product_id', '=', rec.product_id.id),
            ('company_id', '=', rec.company_id.id),
            ('status', '=', 'active'),
            ('id', '!=', rec.id),
        ], limit=1)
        if duplicate:
            raise ValidationError(
                f"Product '{rec.product_id.display_name}' already has an active "
                f"barcode allocation (GTIN: {duplicate.registry_id.gtin_13}). "
                f"Deactivate the existing allocation before creating a new one."
            )
```

Also add a pre-creation check in `product_product.py`'s `allocate_gtin()` method:

```python
# At the start of allocate_gtin():
existing_active = self.env['mml.barcode.allocation'].search([
    ('product_id', '=', self.id),
    ('company_id', '=', self.env.company.id),
    ('status', '=', 'active'),
], limit=1)
if existing_active:
    raise UserError(
        f"Product already has an active GTIN allocation: {existing_active.registry_id.gtin_13}"
    )
```

**Step 5: Run — confirm tests pass**

**Step 6: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/barcode_allocation.py
git add mml.barcodes/mml_barcode_registry/models/product_product.py
git add mml.barcodes/mml_barcode_registry/tests/test_allocation.py
git commit -m "fix(mml_barcode_registry): prevent multiple active GTIN allocations per product"
```

---

### Task D2: Add check digit validation constraint on sequence field

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/barcode_registry.py`
- Read also: `mml.barcodes/mml_barcode_registry/services/gs1.py` — find the check digit function
- Modify: `mml.barcodes/mml_barcode_registry/models/barcode_registry.py`
- Test: `mml.barcodes/mml_barcode_registry/tests/test_lifecycle.py` — add validation test

**Context:** `sequence` is a 12-digit string (the body without check digit). It can be stored as blank or non-numeric with no validation. The computed `gtin_13` field silently returns `False` in that case.

**Step 1: Read `barcode_registry.py` and `gs1.py`**

**Step 2: Write failing tests**

```python
def test_blank_sequence_rejected(self):
    """A registry record with blank sequence must fail validation."""
    pass

def test_non_numeric_sequence_rejected(self):
    """A sequence containing non-digits must fail validation."""
    pass

def test_valid_12digit_sequence_accepted(self):
    """A 12-digit numeric sequence must be accepted."""
    pass
```

**Step 3: Run — confirm they fail**

**Step 4: Add `@api.constrains` on `sequence`**

```python
from odoo.exceptions import ValidationError

@api.constrains('sequence')
def _check_sequence_format(self):
    for rec in self:
        if not rec.sequence:
            raise ValidationError("Barcode registry sequence cannot be empty.")
        if not rec.sequence.isdigit():
            raise ValidationError(
                f"Sequence '{rec.sequence}' must contain only digits."
            )
        if len(rec.sequence) != 12:
            raise ValidationError(
                f"Sequence must be exactly 12 digits (got {len(rec.sequence)})."
            )
```

**Step 5: Run — confirm tests pass**

**Step 6: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/barcode_registry.py
git add mml.barcodes/mml_barcode_registry/tests/test_lifecycle.py
git commit -m "fix(mml_barcode_registry): validate sequence field is exactly 12 digits"
```

---

### Task D3: Fix GS1 cool-down to count from allocation date, not discontinuation date

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/barcode_allocation.py` — find `action_dormant()`
- Modify: same file
- Test: `mml.barcodes/mml_barcode_registry/tests/test_lifecycle.py` — add cooldown test

**Context:** GS1 recommends the 48-month reuse cool-down starts from first allocation date, not from when the product is discontinued. The current code uses `today` (discontinuation date) as the start.

**Step 1: Read `barcode_allocation.py` to find `action_dormant()`**

**Step 2: Write a failing test**

```python
def test_reuse_eligible_date_counts_from_allocation_date(self):
    """
    reuse_eligible_date must be allocation_date + 48 months,
    not discontinue_date + 48 months.
    """
    from dateutil.relativedelta import relativedelta
    from datetime import date

    # allocation_date: 2020-01-01
    # discontinue_date: 2024-01-01 (4 years later)
    # Correct reuse_eligible: 2020-01-01 + 48m = 2024-01-01
    # Wrong reuse_eligible: 2024-01-01 + 48m = 2028-01-01

    allocation_date = date(2020, 1, 1)
    expected_reuse_eligible = allocation_date + relativedelta(months=48)

    # Construct a mock allocation with allocation_date set
    # Call action_dormant()
    # Assert rec.reuse_eligible_date == expected_reuse_eligible
    pass  # Adapt to actual model structure after reading the file
```

**Step 3: Run — confirm it fails (current code uses `today` as start)**

**Step 4: Fix `action_dormant()`**

```python
# BEFORE:
today = date.today()
rec.write({
    'status': 'dormant',
    'discontinue_date': today,
    'reuse_eligible_date': today + relativedelta(months=48),
})

# AFTER:
today = date.today()
# GS1 best practice: cool-down counts from first allocation date
reuse_start = rec.allocation_date or today
rec.write({
    'status': 'dormant',
    'discontinue_date': today,
    'reuse_eligible_date': reuse_start + relativedelta(months=48),
})
```

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/barcode_allocation.py
git add mml.barcodes/mml_barcode_registry/tests/test_lifecycle.py
git commit -m "fix(mml_barcode_registry): GS1 reuse cooldown starts from allocation_date per GS1 best practice"
```

---

### Task D4: Wrap import wizard auto-allocation in savepoint

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py`
- Modify: same file
- Test: `mml.barcodes/mml_barcode_registry/tests/test_import_wizard.py`

**Context:** The import wizard allocates a registry record and then writes to the product. If `product.write()` fails (e.g. validation error), the registry record is left in `in_use` state with no product assigned.

**Step 1: Read `barcode_import_wizard.py` to find the allocation block**

**Step 2: Write a failing test**

```python
def test_failed_product_write_rolls_back_registry_status(self):
    """
    If product.write() fails during auto-allocation,
    the registry record must revert to 'unallocated'.
    """
    pass  # Adapt after reading the wizard
```

**Step 3: Run — confirm it fails**

**Step 4: Wrap the allocation block in a savepoint**

```python
# In the auto-allocation block of the import wizard:
with self.env.cr.savepoint():
    alloc = Allocation.create({...})
    registry.write({'status': 'in_use', 'current_allocation_id': alloc.id})
    if not product.barcode:
        product.write({'barcode': expected_gtin13})  # If this raises, savepoint rolls back
```

Using `self.env.cr.savepoint()` as a context manager ensures that if any write inside the block raises, all changes within the savepoint are rolled back atomically.

**Step 5: Run — confirm test passes**

**Step 6: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py
git add mml.barcodes/mml_barcode_registry/tests/test_import_wizard.py
git commit -m "fix(mml_barcode_registry): wrap import wizard auto-allocation in savepoint to prevent orphaned registry records"
```

---

### Task D5: Re-check prefix availability after acquiring lock

**Files:**
- Read first: `mml.barcodes/mml_barcode_registry/models/product_product.py` — find `_find_allocation_prefix()` and `_claim_next_registry()`
- Modify: same file
- Test: `mml.barcodes/mml_barcode_registry/tests/test_allocation.py`

**Context:** Between `_find_allocation_prefix()` and `_claim_next_registry()` acquiring the `SELECT FOR UPDATE SKIP LOCKED`, another transaction can exhaust the prefix. The error message then shows a stale (incorrect) availability count.

**Step 1: Read `product_product.py` to understand the two-step allocation flow**

**Step 2: Write a test that describes the correct post-lock behaviour**

```python
def test_stale_availability_count_does_not_appear_in_error(self):
    """
    If prefix becomes exhausted between availability check and lock acquisition,
    the error message must reflect the post-lock state (0 available),
    not the stale pre-lock count.
    """
    pass
```

**Step 3: Run — confirm it fails or passes (understand current behaviour first)**

**Step 4: Add post-lock availability re-check**

After `_claim_next_registry()` acquires the lock row, re-query the count of remaining unallocated records for that prefix before raising any error. Use this live count in the error message:

```python
# After FOR UPDATE SKIP LOCKED returns no row:
live_available = self.env['mml.barcode.registry'].search_count([
    ('prefix_id', '=', prefix.id),
    ('status', '=', 'unallocated'),
])
if live_available == 0:
    raise UserError(
        f"No unallocated barcodes remain in prefix '{prefix.name}'. "
        f"Apply for a new GS1 prefix block."
    )
```

**Step 5: Run — confirm tests pass**

**Step 6: Commit**
```bash
git add mml.barcodes/mml_barcode_registry/models/product_product.py
git add mml.barcodes/mml_barcode_registry/tests/test_allocation.py
git commit -m "fix(mml_barcode_registry): re-check prefix availability post-lock for accurate error messages"
```

---

## WORKSTREAM E — Bridge Module Integration Tests
**Scope:** `mml_roq_freight/`, `mml_freight_3pl/`
**Parallel with:** All other workstreams
**Priority:** Medium — implement after critical/high fixes are merged

The bridge module handler logic (`_on_shipment_group_confirmed`, `_on_freight_booking_confirmed`) has no integration tests exercising the actual handlers. This workstream adds them.

---

### Task E1: Integration tests for mml_roq_freight bridge handler

**Files:**
- Read first: `mml_roq_freight/models/bridge_service.py`
- Create: `mml_roq_freight/tests/test_bridge_handler.py`

**Step 1: Read `bridge_service.py` to understand handler signatures and registry calls**

**Step 2: Write tests using mock registry services**

```python
"""Integration tests for mml_roq_freight bridge handlers."""
import types
import pytest


class MockFreightService:
    def __init__(self):
        self.create_tender_calls = []
        self.last_tender_id = 42

    def create_tender(self, shipment_group_id):
        self.create_tender_calls.append(shipment_group_id)
        return self.last_tender_id


class MockROQService:
    def __init__(self):
        self.update_calls = []

    def update_freight_ref(self, shipment_group_id, tender_id):
        self.update_calls.append((shipment_group_id, tender_id))


def test_on_shipment_group_confirmed_creates_tender(monkeypatch):
    """Handler must call freight.create_tender() and write tender_id back."""
    # Register mock services
    # Emit a roq.shipment_group.confirmed event
    # Assert MockFreightService.create_tender_calls == [shipment_group_id]
    # Assert freight_tender_id was written back on the shipment group
    pass


def test_on_shipment_group_confirmed_handles_freight_service_error(monkeypatch):
    """Handler must log and not raise when freight service errors."""
    pass


def test_on_freight_booking_confirmed_updates_roq(monkeypatch):
    """Handler must call roq service when booking is confirmed."""
    pass
```

Adapt to match the actual handler signatures found in `bridge_service.py`.

**Step 3: Run — confirm they fail with NotImplemented or missing mock wiring**

**Step 4: Implement the mocks and assertions properly**

**Step 5: Run full test suite for the bridge**
```bash
pytest mml_roq_freight/ -q
```

**Step 6: Commit**
```bash
git add mml_roq_freight/tests/test_bridge_handler.py
git commit -m "test(mml_roq_freight): add integration tests for bridge event handler logic"
```

---

### Task E2: Integration tests for mml_freight_3pl bridge handler

**Files:**
- Read first: `mml_freight_3pl/models/mml_3pl_bridge.py`
- Create: `mml_freight_3pl/tests/test_bridge_handler.py`

Same pattern as E1 — write mock-based tests for `_on_freight_booking_confirmed`. Specifically test:
1. Normal path: each PO gets a `queue_inward_order()` call
2. Empty `po_ids`: handler exits early without calling 3PL service
3. `queue_inward_order()` returns None: billable event is NOT emitted
4. `queue_inward_order()` raises: exception is caught and logged, does not propagate

**Step 1: Read `mml_3pl_bridge.py`**

**Step 2-5: Same TDD pattern as E1**

**Step 6: Commit**
```bash
git add mml_freight_3pl/tests/test_bridge_handler.py
git commit -m "test(mml_freight_3pl): add integration tests for 3PL bridge event handler logic"
```

---

## Final Verification

After all workstreams complete, run the full repo test suite:

```bash
cd E:\ClaudeCode\projects\mml.odoo.apps

# Freight workspace
pytest mml.fowarder.intergration/addons/ -q

# EDI workspace
pytest mml.edi/ -q

# Barcode workspace
pytest mml.barcodes/ -q

# 3PL workspace
pytest mml.3pl.intergration/ -q

# ROQ workspace
pytest mml.roq.model/ -q

# Forecasting workspace
pytest mml.forecasting/ -q

# Root (bridge modules, mml_base)
pytest -m "not odoo_integration" -q
```

All test suites must be green before declaring production-ready.

---

## Post-Deployment Ops Checklist

These items require ops action on the production instance — not code changes:

- [ ] Generate Mainfreight webhook secret: `python -c "import secrets; print(secrets.token_hex(32))"` and set `x_mf_webhook_secret` on the production `delivery.carrier` record
- [ ] Set `x_knplus_environment = 'production'` on all K+N carrier records (prevents sandbox mode being active on prod)
- [ ] Obtain Mainfreight SFTP host key: `ssh-keyscan xftp.mainfreight.com` and set `sftp_host_key` on the 3PL connector
- [ ] Activate crons one at a time after verifying each connector: outbound queue (5 min), inbound poll (15 min), tracking (30 min)
- [ ] Set `mml.instance_ref` in `ir.config_parameter` to the production instance UUID
- [ ] Verify `mml_roq_forecast` PO raise wizard: create a test PO from the wizard in the staging database and confirm `purchase.order.line` field names (`product_uom`, `date_planned`) are correct before activating in production
