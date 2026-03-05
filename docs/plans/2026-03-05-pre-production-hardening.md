# Pre-Production Hardening Sprint — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all outstanding bugs, security issues, and gaps identified in the 2026-03-05 readiness review, and implement the Briscoes ASN (DESADV) to reach deployment-ready state.

**Architecture:** Six parallel work streams gated on Group 1 completing first. Each stream touches a different module cluster — no cross-stream file conflicts. Groups 2–6 can execute simultaneously after Group 1 lands.

**Tech Stack:** Odoo 19, Python 3, paramiko (SFTP), EDIFACT D96A, PostgreSQL

---

## Parallelism Map

```
[Group 1: Module Cleanup] ← must land first
        |
   ┌────┼────┬────┬────┐
   2    3    4    5    6   ← all parallel after Group 1
```

**Group 1** must be committed before any other group starts.
**Groups 2–6** have no dependencies on each other — assign to separate subagents.

---

## GROUP 1 — Module Cleanup (Sequential Gate)

### Task 1: Cherry-pick `mml_forecast_demand` improvements into `mml_roq_forecast`

**Context:** `mml_forecast_demand` and `mml_roq_forecast` define identical model `_name` values across 12 models — both cannot be installed. `mml_forecast_demand` contains three improvements not yet in `mml_roq_forecast`: (1) `_safe_int`/`_safe_float` guards in `roq_forecast_run.py`, (2) fixed `roq_raise_po_wizard.py` (UserError on missing supplierinfo), (3) cleaner `settings_helper.py`. Cherry-pick these, then delete `mml_forecast_demand`.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_forecast_run.py`
- Modify: `roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py`
- Modify: `roq.model/mml_roq_forecast/services/settings_helper.py`
- Reference: `mml.forecasting/mml_forecast_demand/models/roq_forecast_run.py` (source)
- Reference: `mml.forecasting/mml_forecast_demand/models/roq_raise_po_wizard.py` (source)
- Reference: `mml.forecasting/mml_forecast_demand/services/settings_helper.py` (source)

**Step 1: Copy `_safe_int` / `_safe_float` helpers into `roq_forecast_run.py`**

Read `mml.forecasting/mml_forecast_demand/models/roq_forecast_run.py` lines 1-20. Add the same helper functions at the top of `roq.model/mml_roq_forecast/models/roq_forecast_run.py` after the imports:

```python
def _safe_int(val, default):
    try:
        return int(val) if val not in (None, '', False) else default
    except (ValueError, TypeError):
        return default


def _safe_float(val, default):
    try:
        return float(val) if val not in (None, '', False) else default
    except (ValueError, TypeError):
        return default
```

**Step 2: Replace `roq_raise_po_wizard.py` with the improved version**

Read both files. The key improvement in the `mml_forecast_demand` version is that `action_raise_pos()` raises `UserError` when no `supplierinfo` exists (instead of silently defaulting `price_unit` to 0.0). Copy the full `action_raise_pos()` method body from the demand version into the roq_forecast version, preserving the existing class/field definitions.

**Step 3: Replace `settings_helper.py` with the improved version**

Read both files. The `mml_forecast_demand` version has a correct `None`-safe `_get_param()` that avoids `int(False)` raising `TypeError`. Copy the full `SettingsHelper` class from demand version into `roq.model/mml_roq_forecast/services/settings_helper.py`.

**Step 4: Run existing tests to verify nothing broken**

```bash
cd "E:\ClaudeCode\projects\mml.odoo.apps"
python -m pytest roq.model/mml_roq_forecast/tests/ -v 2>&1 | tail -30
```
Expected: all previously-passing tests still pass.

**Step 5: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_forecast_run.py
git add roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py
git add roq.model/mml_roq_forecast/services/settings_helper.py
git commit -m "fix(mml_roq_forecast): cherry-pick safe_int, safe_float, PO wizard UserError from mml_forecast_demand"
```

---

### Task 2: Delete `mml_forecast_demand`, promote `mml_forecast_core` and `mml_forecast_financial`

**Context:** `mml_forecast_demand` is now redundant. `mml_forecast_core` (financial forecasting config) and `mml_forecast_financial` (P&L/cashflow wizard) are genuinely new modules worth keeping — but their manifests need `mml_base` added as a dependency since they reference `mml.capability`, `mml.registry`, etc. indirectly via the hooks pattern.

**Files:**
- Delete: `mml.forecasting/mml_forecast_demand/` (entire directory)
- Modify: `mml.forecasting/mml_forecast_core/__manifest__.py`
- Modify: `mml.forecasting/mml_forecast_financial/__manifest__.py`
- Verify: `mml.forecasting/mml_forecast_core/models/forecast_config.py` — check `env.get('forecast.generate.wizard')` pattern is correct (it is; no changes needed)

**Step 1: Delete `mml_forecast_demand`**

```bash
rm -rf "E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_demand"
```

**Step 2: Add `mml_base` to `mml_forecast_core` depends**

In `mml.forecasting/mml_forecast_core/__manifest__.py`, change:
```python
'depends': ['base', 'product', 'sale', 'purchase', 'account', 'mail'],
```
to:
```python
'depends': ['mml_base', 'base', 'product', 'sale', 'purchase', 'account', 'mail'],
```

**Step 3: Add `mml_base` and `mml_forecast_core` to `mml_forecast_financial` depends**

In `mml.forecasting/mml_forecast_financial/__manifest__.py`, change:
```python
'depends': ['mml_forecast_core', 'account'],
```
to:
```python
'depends': ['mml_base', 'mml_forecast_core', 'account'],
```
Also add `installable` key if missing:
```python
'installable': True,
```

**Step 4: Verify `mml_forecast_core` static icon exists**

```bash
ls "E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_core\static\description\"
```
If `icon.png` is missing, create the directory and copy from another module:
```bash
mkdir -p "E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_core\static\description"
cp "E:\ClaudeCode\projects\mml.odoo.apps\mml_base\static\description\icon.png" \
   "E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_core\static\description\icon.png"
```

**Step 5: Commit**

```bash
git rm -r mml.forecasting/mml_forecast_demand/
git add mml.forecasting/mml_forecast_core/__manifest__.py
git add mml.forecasting/mml_forecast_financial/__manifest__.py
git add mml.forecasting/mml_forecast_core/static/description/icon.png 2>/dev/null || true
git commit -m "refactor(mml.forecasting): delete mml_forecast_demand, fix mml_base deps on forecast_core/financial"
```

---

## GROUP 2 — Platform / mml_base

### Task 3: Fix `mml_base` service registry — survive worker forking

**Context:** `mml.registry` stores service classes in a module-level Python dict (`_SERVICE_REGISTRY`). Odoo forks worker processes *after* module load — post_init_hook runs once in the parent but the dict is empty in each new worker. Fix: add lazy re-hydration from DB on cache miss. Store the service class import path in `ir.config_parameter` keyed as `mml_registry.service.{name}` on `register()`. On `service()` cache miss, read from DB, import the class, populate the dict.

**Files:**
- Modify: `mml_base/models/mml_registry.py`
- Modify: `mml_base/tests/test_registry.py`

**Step 1: Read current `mml_registry.py` fully**

Read `mml_base/models/mml_registry.py`.

**Step 2: Write failing test for forked-worker re-hydration**

Add to `mml_base/tests/test_registry.py`:

```python
def test_service_rehydrates_after_registry_cleared(self):
    """Simulate forked worker: clear in-process dict, service() must still work."""
    from odoo.addons.mml_base.models import mml_registry as reg_module
    # Register a known service
    self.env['mml.registry'].register('test_rehydrate', _DummyService)
    # Simulate worker fork: wipe the in-process dict
    reg_module._SERVICE_REGISTRY.clear()
    # service() must re-hydrate from DB and return a working instance
    svc = self.env['mml.registry'].service('test_rehydrate')
    self.assertFalse(svc.is_null(), "Expected real service, got NullService after re-hydration")
```

Where `_DummyService` is a test service class with `is_null()` returning `False`.

**Step 3: Run test to confirm it fails**

```bash
python -m pytest mml_base/tests/test_registry.py -v -k test_service_rehydrates 2>&1 | tail -20
```
Expected: FAIL — `is_null()` returns True (NullService returned after dict cleared).

**Step 4: Implement lazy re-hydration**

Replace `mml_registry.py` with:

```python
import importlib
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# In-process cache — fast path, populated lazily.
# Empty in fresh worker processes after fork — re-hydrated from DB on first miss.
_SERVICE_REGISTRY: dict[str, type] = {}

_PARAM_PREFIX = 'mml_registry.service.'


class MmlRegistry(models.AbstractModel):
    _name = 'mml.registry'
    _description = 'MML Service Locator'

    @api.model
    def register(self, service_name: str, service_class: type) -> None:
        """Register a service class. Persists class path to DB for worker re-hydration."""
        _SERVICE_REGISTRY[service_name] = service_class
        class_path = '%s.%s' % (service_class.__module__, service_class.__qualname__)
        self.env['ir.config_parameter'].sudo().set_param(
            _PARAM_PREFIX + service_name, class_path
        )

    @api.model
    def deregister(self, service_name: str) -> None:
        """Remove a service. Called from uninstall_hook."""
        _SERVICE_REGISTRY.pop(service_name, None)
        self.env['ir.config_parameter'].sudo().set_param(
            _PARAM_PREFIX + service_name, False
        )

    @api.model
    def service(self, service_name: str):
        """
        Return an instance of the registered service, or a NullService.
        Fast path: in-process dict. Slow path: DB lookup + dynamic import.
        """
        from odoo.addons.mml_base.services.null_service import NullService

        cls = _SERVICE_REGISTRY.get(service_name)
        if cls is None:
            cls = self._load_from_db(service_name)
        if cls is None:
            return NullService()
        return cls(self.env)

    @api.model
    def _load_from_db(self, service_name: str):
        """Import service class from DB-stored path and cache in process dict."""
        class_path = self.env['ir.config_parameter'].sudo().get_param(
            _PARAM_PREFIX + service_name
        )
        if not class_path:
            return None
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            _SERVICE_REGISTRY[service_name] = cls
            _logger.info('mml.registry: re-hydrated service %r from DB', service_name)
            return cls
        except Exception:
            _logger.exception('mml.registry: failed to re-hydrate service %r', service_name)
            return None
```

**Step 5: Run test — confirm it passes**

```bash
python -m pytest mml_base/tests/test_registry.py -v 2>&1 | tail -20
```
Expected: all tests PASS.

**Step 6: Commit**

```bash
git add mml_base/models/mml_registry.py mml_base/tests/test_registry.py
git commit -m "fix(mml_base): persist service class path to DB for worker re-hydration"
```

---

### Task 4: Add `group_user` read ACL to `mml.license`

**Context:** Regular users hitting any code path that reads license status get `AccessError` because `mml.license` has no read ACL for `base.group_user`.

**Files:**
- Modify: `mml_base/security/ir.model.access.csv`

**Step 1: Read current ACL file**

Read `mml_base/security/ir.model.access.csv`.

**Step 2: Add user read line**

Find the block for `mml.license` and add a read-only user row. The line to add:

```
access_mml_license_user,mml.license user,model_mml_license,base.group_user,1,0,0,0
```

**Step 3: Run license tests**

```bash
python -m pytest mml_base/tests/test_license.py -v 2>&1 | tail -20
```
Expected: PASS.

**Step 4: Commit**

```bash
git add mml_base/security/ir.model.access.csv
git commit -m "fix(mml_base): add group_user read ACL for mml.license — prevents AccessError in user context"
```

---

## GROUP 3 — mml_edi Security + Reliability

### Task 5: SFTP host key verification

**Context:** `_connect_sftp()` in `briscoes.edi/models/edi_ftp.py` uses `paramiko.Transport.connect()` without checking the server's host key. A MITM attacker can intercept EDI documents or inject orders. Fix: use `paramiko.SSHClient` with `RejectPolicy` and store/verify the server fingerprint.

**Files:**
- Modify: `briscoes.edi/models/edi_ftp.py`
- Modify: `briscoes.edi/models/edi_trading_partner.py`
- Modify: `briscoes.edi/tests/test_ftp_handler.py`

**Step 1: Add `sftp_host_key` field to `edi.trading.partner`**

In `edi_trading_partner.py`, add after `ftp_test_outbox_path`:

```python
sftp_host_key = fields.Char(
    string='SFTP Host Key (base64)',
    groups='base.group_system',
    help=(
        'Base64-encoded server public key fingerprint. '
        'Obtain with: ssh-keyscan -t rsa <host> | awk \'{print $3}\'. '
        'Required when ftp_protocol = sftp. Leave blank to REJECT all SFTP connections '
        '(fail-safe: no key = no connection).'
    ),
)
```

**Step 2: Write failing test**

In `briscoes.edi/tests/test_ftp_handler.py`, add:

```python
def test_sftp_rejects_connection_when_no_host_key(self):
    """SFTP connect must raise EDIFTPError when sftp_host_key is not configured."""
    from ..models.edi_ftp import EDIFTPHandler
    from ..parsers.base_parser import EDIFTPError
    partner = self._make_partner(ftp_protocol='sftp', sftp_host_key=False)
    handler = EDIFTPHandler(partner)
    with self.assertRaises(EDIFTPError):
        handler.connect()
```

**Step 3: Run test to confirm it fails**

```bash
python -m pytest "briscoes.edi/tests/test_ftp_handler.py" -v -k test_sftp_rejects 2>&1 | tail -20
```
Expected: FAIL — no error raised currently.

**Step 4: Replace `_connect_sftp()` with host-key-verified version**

In `briscoes.edi/models/edi_ftp.py`, replace the `_connect_sftp` method:

```python
def _connect_sftp(self):
    try:
        import base64
        import paramiko
    except ImportError:
        raise EDIFTPError(
            "paramiko is required for SFTP. Install with: pip install paramiko"
        )

    stored_key_b64 = self.partner.sftp_host_key
    if not stored_key_b64:
        raise EDIFTPError(
            "SFTP host key not configured for partner '%s'. "
            "Set sftp_host_key on the trading partner before enabling SFTP." % self.partner.code
        )

    try:
        key_bytes = base64.b64decode(stored_key_b64)
        server_key = paramiko.RSAKey(data=key_bytes)
    except Exception as exc:
        raise EDIFTPError(
            "Invalid sftp_host_key format for partner '%s': %s" % (self.partner.code, exc)
        )

    client = paramiko.SSHClient()
    client.get_host_keys().add(
        self.partner.ftp_host, 'ssh-rsa', server_key
    )
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        client.connect(
            hostname=self.partner.ftp_host,
            port=self.partner.ftp_port,
            username=self.partner.ftp_user,
            password=self.partner.ftp_password,
            timeout=_CONNECT_TIMEOUT,
            look_for_keys=False,
            allow_agent=False,
        )
    except paramiko.SSHException as exc:
        raise EDIFTPError(
            "SFTP connection failed for '%s': %s" % (self.partner.code, exc)
        )

    self._ftp = client.open_sftp()
    # Keep reference for cleanup — SSHClient wraps the transport
    self._transport = client
```

Also update `disconnect()` to handle `SSHClient` (it has a `.close()` method, same as `Transport`):

The existing `disconnect()` calls `self._transport.close()` which works for both `paramiko.Transport` and `paramiko.SSHClient`. No change needed there.

**Step 5: Run all FTP handler tests**

```bash
python -m pytest "briscoes.edi/tests/test_ftp_handler.py" -v 2>&1 | tail -30
```
Expected: all PASS.

**Step 6: Commit**

```bash
git add "briscoes.edi/models/edi_ftp.py" "briscoes.edi/models/edi_trading_partner.py" "briscoes.edi/tests/test_ftp_handler.py"
git commit -m "fix(mml_edi): SFTP host key verification — replace paramiko.Transport with SSHClient+RejectPolicy"
```

---

### Task 6: `edi.bulk.action` ACL + error message sanitisation

**Context:** Two related mml_edi gaps: (1) `edi.bulk.action` TransientModel is missing from `ir.model.access.csv`, leaving it unprotected. (2) `edi_processor.py` stores raw exception detail (including internal paths) in `edi.log.detail` visible to EDI Users. Fix both.

**Files:**
- Modify: `briscoes.edi/security/ir.model.access.csv`
- Modify: `briscoes.edi/models/edi_log.py`
- Modify: `briscoes.edi/models/edi_processor.py`

**Step 1: Read current ACL file**

Read `briscoes.edi/security/ir.model.access.csv`. Note all existing rows.

**Step 2: Add `edi.bulk.action` rows**

Append to the ACL file:

```
access_edi_bulk_action_user,edi.bulk.action user,model_edi_bulk_action,mml_edi.group_edi_user,1,1,1,1
access_edi_bulk_action_manager,edi.bulk.action manager,model_edi_bulk_action,mml_edi.group_edi_manager,1,1,1,1
```

**Step 3: Sanitise error detail in `edi_log.py`**

In `briscoes.edi/models/edi_log.py`, add a new field:

```python
detail = fields.Text(
    string='Technical Detail',
    groups='mml_edi.group_edi_manager',
    help='Raw exception detail — visible to EDI Managers only.',
)
```

And rename or remove any existing plain `detail` field that is visible to `group_edi_user`. Read the file first to check the current field definition.

**Step 4: Update `edi_processor.py` log calls**

Read `briscoes.edi/models/edi_processor.py`. Find all calls to `self.env["edi.log"].log(...)` that pass `detail=str(exc)`. The `detail` field is now manager-only, so this is safe as-is. Verify no detail is being surfaced in user-visible views.

**Step 5: Commit**

```bash
git add "briscoes.edi/security/ir.model.access.csv" "briscoes.edi/models/edi_log.py"
git commit -m "fix(mml_edi): add edi.bulk.action ACL; restrict error detail to EDI Manager group"
```

---

### Task 7: EAN-13 validation before ORDRSP generation

**Context:** ORDRSP generation doesn't validate EAN-13 barcodes. Briscoes requires valid EAN-13 on all ASN lines — if a product is missing a valid barcode, the follow-on ASN will fail Briscoes validation.

**Files:**
- Read: `briscoes.edi/parsers/briscoes.py` or wherever ORDRSP is generated
- Modify: the ORDRSP generation method
- Modify: `briscoes.edi/tests/test_briscoes_ordrsp.py`

**Step 1: Read the ORDRSP generator to find generation point**

Read `briscoes.edi/tests/test_briscoes_ordrsp.py` and trace back to the generation code.

**Step 2: Write failing test**

In `briscoes.edi/tests/test_briscoes_ordrsp.py`, add:

```python
def test_ordrsp_raises_on_missing_ean13(self):
    """ORDRSP generation must raise UserError if any line product has no valid EAN-13."""
    from odoo.exceptions import UserError
    # Create an order review with a product that has no barcode
    review = self._make_review_with_unbarcode_product()
    with self.assertRaises(UserError) as ctx:
        review.action_generate_ordrsp()
    self.assertIn('barcode', str(ctx.exception).lower())
```

**Step 3: Run test to confirm it fails**

Expected: FAIL — no UserError raised.

**Step 4: Add EAN-13 validation**

In the ORDRSP generation method, before building the EDIFACT message, add:

```python
def _validate_ean13(self, order_lines):
    """Raise UserError if any line product has no valid EAN-13 barcode."""
    import re
    ean13_re = re.compile(r'^\d{13}$')
    missing = []
    for line in order_lines:
        barcode = line.product_id.barcode or ''
        if not ean13_re.match(barcode) or not self._ean13_check_digit_valid(barcode):
            missing.append(line.product_id.display_name)
    if missing:
        raise UserError(
            "Cannot generate ORDRSP: the following products have no valid EAN-13 barcode:\n%s\n\n"
            "Add a 13-digit barcode with a valid check digit to each product before generating."
            % '\n'.join('  - %s' % name for name in missing)
        )

def _ean13_check_digit_valid(self, barcode: str) -> bool:
    digits = [int(c) for c in barcode]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1]))
    return (10 - total % 10) % 10 == digits[-1]
```

Call `self._validate_ean13(order_review.line_ids)` at the start of the ORDRSP generation method.

**Step 5: Run tests**

```bash
python -m pytest "briscoes.edi/tests/test_briscoes_ordrsp.py" -v 2>&1 | tail -20
```
Expected: PASS.

**Step 6: Commit**

```bash
git add "briscoes.edi/"
git commit -m "fix(mml_edi): validate EAN-13 before ORDRSP generation — prevent silent Briscoes rejection"
```

---

## GROUP 4 — mml_freight Security + mml_roq_forecast Fixes

### Task 8: `roq_raise_po_wizard` — duplicate PO guard + multi-warehouse linking + sudo scope

**Context:** Three related issues in `roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py` (which now has the improved code from Task 1): (1) No duplicate PO guard — re-running creates a second draft PO for same run/supplier/warehouse. (2) Multi-warehouse: only `po_ids[0]` linked back to shipment group, remaining POs are invisible to the workflow. (3) `sudo().create()` on `purchase.order` bypasses PO approval — should check user permission first.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py`
- Modify: `roq.model/mml_roq_forecast/tests/test_raise_po_wizard.py`

**Step 1: Read the current wizard file**

Read `roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py` fully (it now has the Task 1 improvements).

**Step 2: Write failing tests**

In `roq.model/mml_roq_forecast/tests/test_raise_po_wizard.py`, add:

```python
def test_duplicate_po_guard_raises_on_second_run(self):
    """Running the wizard twice for the same run/supplier/warehouse raises UserError."""
    wizard = self._make_wizard()
    wizard.action_raise_pos()
    # Second run — same run_id/supplier/warehouse — must raise, not create second PO
    with self.assertRaises(UserError):
        wizard.action_raise_pos()

def test_multi_warehouse_all_pos_linked_to_shipment_group(self):
    """All POs from multi-warehouse run must be linked to shipment group po_ids."""
    wizard = self._make_multi_warehouse_wizard()
    wizard.action_raise_pos()
    all_po_ids = wizard.shipment_group_line_id.group_id.po_ids.ids
    self.assertEqual(len(all_po_ids), 2, "Both warehouse POs must be linked")
```

**Step 3: Run to confirm they fail**

```bash
python -m pytest "roq.model/mml_roq_forecast/tests/test_raise_po_wizard.py" -v -k "duplicate_or_multi" 2>&1 | tail -20
```

**Step 4: Add duplicate guard and fix multi-warehouse linking**

In `action_raise_pos()`, before the `po = self.env['purchase.order'].sudo().create(po_vals)` line, add:

```python
# Duplicate guard — reject if an existing draft PO exists for this run/supplier/warehouse
existing = self.env['purchase.order'].search([
    ('state', '=', 'draft'),
    ('partner_id', '=', self.supplier_id.id),
    ('picking_type_id', '=', warehouse.in_type_id.id),
    ('origin', 'like', self.run_id.name),
], limit=1)
if existing:
    raise exceptions.UserError(
        _("A draft PO already exists for supplier '%s' at warehouse '%s' "
          "for this ROQ run (%s). Cancel or delete it before raising a new one.")
        % (self.supplier_id.name, warehouse.name, self.run_id.name)
    )
```

Add `origin=self.run_id.name` to `po_vals` so the duplicate guard works.

Fix multi-warehouse linking — replace the single-PO write block after the loop with:

```python
if sg_line and po_ids:
    sg_line.sudo().write({'purchase_order_id': po_ids[0]})
    if sg_line.group_id and hasattr(sg_line.group_id, 'po_ids'):
        sg_line.group_id.sudo().write({'po_ids': [(4, pid) for pid in po_ids]})
```

(This was already correct in the demand version — verify it's in the roq_forecast version after Task 1.)

**Step 5: Narrow sudo scope**

Replace:
```python
po = self.env['purchase.order'].sudo().create(po_vals)
```
with a permission check first:
```python
if not self.env.user.has_group('purchase.group_purchase_user'):
    raise exceptions.UserError(
        _("You need Purchase User access to raise purchase orders.")
    )
po = self.env['purchase.order'].create(po_vals)
```
Remove `.sudo()` — the user's own permissions should apply.

**Step 6: Run all wizard tests**

```bash
python -m pytest "roq.model/mml_roq_forecast/tests/test_raise_po_wizard.py" -v 2>&1 | tail -20
```

**Step 7: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_raise_po_wizard.py
git add roq.model/mml_roq_forecast/tests/test_raise_po_wizard.py
git commit -m "fix(mml_roq_forecast): duplicate PO guard, multi-warehouse linking, remove sudo on PO create"
```

---

### Task 9: `roq_shipment_group` ACL + `abc_classifier` falsy-zero + multi-company guards

**Context:** Three security/correctness fixes in mml_roq_forecast: (1) `group_user` can write/create on `roq.shipment.group` — confirmed shipment groups should be manager-only for edits. (2) `abc_classifier.py` uses `val or default` which ignores intentional zero band percentages. (3) No company filter on warehouse/SO/product queries.

**Files:**
- Modify: `roq.model/mml_roq_forecast/security/ir.model.access.csv`
- Modify: `roq.model/mml_roq_forecast/services/abc_classifier.py`
- Modify: `roq.model/mml_roq_forecast/services/demand_history.py` (company filter)
- Modify: `roq.model/mml_roq_forecast/tests/test_abc_classifier.py`

**Step 1: Tighten shipment group ACL**

Read `roq.model/mml_roq_forecast/security/ir.model.access.csv`.

Find the `roq.shipment.group` row for `base.group_user` and change `perm_write` and `perm_create` from `1` to `0`:

```
access_roq_shipment_group_user,roq.shipment.group user,model_roq_shipment_group,base.group_user,1,0,0,0
```

Same for `roq.shipment.group.line`:
```
access_roq_shipment_group_line_user,roq.shipment.group.line user,model_roq_shipment_group_line,base.group_user,1,0,0,0
```

**Step 2: Fix `abc_classifier.py` falsy-zero pattern**

Read `roq.model/mml_roq_forecast/services/abc_classifier.py`.

Find all occurrences of the pattern:
```python
some_val = settings.get_something() or default_value
```
where `some_val` might legitimately be `0`. Replace with explicit None/False check:
```python
raw = settings.get_something()
some_val = raw if raw is not None else default_value
```

Specifically look at band percentage lookups. The issue is `'0' or default` — the string `'0'` is falsy. After the `_get_param()` fix in Task 1, values come back as typed (float/int), so the falsy check now catches genuine `0.0`. Change the pattern.

**Step 3: Write failing test for falsy-zero**

In `roq.model/mml_roq_forecast/tests/test_abc_classifier.py`, add:

```python
def test_zero_band_percentage_is_honoured(self):
    """Band percentage of 0 must not be replaced by the default."""
    # If the A-band cutoff is 0%, no products should be classified A
    classifier = self._make_classifier(a_band_pct=0.0)
    result = classifier.classify({'PROD1': 100.0})
    self.assertNotEqual(result.get('PROD1'), 'A', "Zero band pct was ignored — falsy-or pattern bug")
```

**Step 4: Add company filter to demand history queries**

Read `roq.model/mml_roq_forecast/services/demand_history.py`.

Find `sale.order.line` and `stock.warehouse` search calls. Add `('company_id', '=', env.company.id)` to each domain. If the service doesn't receive `env`, it receives it via `__init__(self, env)` — use `self.env.company.id`.

Example before:
```python
orders = self.env['sale.order'].search([('state', 'in', ['sale', 'done']), ...])
```
After:
```python
orders = self.env['sale.order'].search([
    ('state', 'in', ['sale', 'done']),
    ('company_id', '=', self.env.company.id),
    ...
])
```

**Step 5: Run abc_classifier tests**

```bash
python -m pytest "roq.model/mml_roq_forecast/tests/test_abc_classifier.py" -v 2>&1 | tail -20
```

**Step 6: Commit**

```bash
git add roq.model/mml_roq_forecast/security/ir.model.access.csv
git add roq.model/mml_roq_forecast/services/abc_classifier.py
git add roq.model/mml_roq_forecast/services/demand_history.py
git add roq.model/mml_roq_forecast/tests/test_abc_classifier.py
git commit -m "fix(mml_roq_forecast): tighten shipment group ACL, fix falsy-zero band, add company filter to queries"
```

---

### Task 10: mml_freight security — K+N token, DSV SSRF, MF webhook, stock_3pl signed_by

**Context:** Four security fixes across freight modules: (1) K+N `x_knplus_access_token` missing `password=True`. (2) K+N webhook leaks `carrier.id` in error response. (3) DSV document download uses server-returned URL without domain validation (SSRF). (4) MF webhook logs `messageType`/`messageId` before auth validation. (5) `stock_3pl/tracking_cron.py` writes `signed_by` from carrier payload without length/content validation.

**Files:**
- Modify: `fowarder.intergration/addons/mml_freight_knplus/models/` — find the delivery.carrier extension with `x_knplus_access_token`
- Modify: `fowarder.intergration/addons/mml_freight_knplus/controllers/kn_webhook.py`
- Modify: `fowarder.intergration/addons/mml_freight_dsv/models/freight_carrier_dsv.py` or DSV service
- Modify: `fowarder.intergration/addons/mml_freight_mainfreight/controllers/` — MF webhook
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/cron/tracking_cron.py`

**Step 1: Read each affected file**

Read the files listed above to find exact line numbers for each issue.

**Step 2: Fix K+N access token — add `password=True`**

Find the field definition of `x_knplus_access_token` on `delivery.carrier` extension. Change:
```python
x_knplus_access_token = fields.Char(string='K+N Access Token')
```
to:
```python
x_knplus_access_token = fields.Char(string='K+N Access Token', password=True)
```

**Step 3: Fix K+N webhook — remove `carrier.id` from error response**

In `kn_webhook.py`, find any error response that includes `carrier.id` or carrier identifiers. Replace with generic error:
```python
# Before:
return Response(json.dumps({'error': 'carrier %s not found' % carrier.id}), status=404)
# After:
return Response(json.dumps({'error': 'not found'}), status=404)
```

**Step 4: Fix DSV download URL — allowlist validation**

Find where `downloadUrl` is fetched. Add domain validation:

```python
import urllib.parse

_ALLOWED_DSV_DOMAINS = frozenset({
    'api.dsv.com',
    'api.sandbox.dsv.com',
    'documentservice.dsv.com',
})

def _safe_download_url(self, url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https':
        raise UserError('DSV download URL must use HTTPS')
    if parsed.netloc.lower() not in _ALLOWED_DSV_DOMAINS:
        raise UserError('DSV download URL hostname not in allowlist: %s' % parsed.netloc)
    return url
```

Call `_safe_download_url(downloadUrl)` before `requests.get(downloadUrl, ...)`.

**Step 5: Fix MF webhook — move logging after auth validation**

In the Mainfreight webhook controller, find the pattern:
```python
data = request.get_json()
message_type = data.get('messageType')  # logged before auth
_logger.info('MF webhook: %s', message_type)  # ← move this AFTER auth check
if not _validate_webhook_secret(...):
    return Response(..., status=403)
```
Move the `_logger.info` call to after the auth check passes.

**Step 6: Fix `signed_by` validation in `tracking_cron.py`**

Find where `signed_by` is written to `stock.picking`:
```python
picking.signed_by = payload.get('signedBy')
```
Replace with:
```python
import re
raw = str(payload.get('signedBy') or '')
# Strip non-printable characters and truncate
signed_by = re.sub(r'[^\x20-\x7E]', '', raw)[:128]
picking.signed_by = signed_by
```

**Step 7: Commit all freight security fixes**

```bash
git add fowarder.intergration/ mainfreight.3pl.intergration/
git commit -m "fix(mml_freight): K+N token password=True, remove carrier.id leak, DSV SSRF domain check, MF webhook post-auth logging, signed_by sanitisation"
```

---

### Task 11: App icons + `mml_freight_demo` disable

**Context:** `mml_freight` and `mml_roq_forecast` declare `application=True` but are missing `static/description/icon.png`. `mml_freight_demo` must be disabled for production.

**Files:**
- Create: `fowarder.intergration/addons/mml_freight/static/description/icon.png`
- Create: `roq.model/mml_roq_forecast/static/description/icon.png`
- Modify: `fowarder.intergration/addons/mml_freight/__manifest__.py` — add `web_icon`
- Modify: `roq.model/mml_roq_forecast/__manifest__.py` — add `web_icon`
- Modify: `fowarder.intergration/addons/mml_freight_demo/__manifest__.py`

**Step 1: Create icon directories and copy placeholder icons**

```bash
mkdir -p "fowarder.intergration/addons/mml_freight/static/description"
mkdir -p "roq.model/mml_roq_forecast/static/description"
cp "mml_base/static/description/icon.png" "fowarder.intergration/addons/mml_freight/static/description/icon.png"
cp "mml_base/static/description/icon.png" "roq.model/mml_roq_forecast/static/description/icon.png"
```

**Step 2: Add `web_icon` to each manifest**

In `mml_freight/__manifest__.py`, add:
```python
'web_icon': 'mml_freight,static/description/icon.png',
```

In `mml_roq_forecast/__manifest__.py`, add:
```python
'web_icon': 'mml_roq_forecast,static/description/icon.png',
```

**Step 3: Disable `mml_freight_demo`**

Read `fowarder.intergration/addons/mml_freight_demo/__manifest__.py`. Change:
```python
'installable': True,
```
to:
```python
'installable': False,
```
If not present, add `'installable': False,`.

**Step 4: Commit**

```bash
git add fowarder.intergration/addons/mml_freight/ roq.model/mml_roq_forecast/
git commit -m "fix: add app icons for mml_freight and mml_roq_forecast; disable mml_freight_demo for production"
```

---

## GROUP 5 — Briscoes ASN (DESADV) Implementation

### Task 12: `BriscoesASNGenerator` — synthesised EDIFACT DESADV

**Context:** `EDIService.on_3pl_despatch_confirmed()` is a stub. Implement the full outbound ASN flow. The DESADV format is synthesised from Briscoes EDIFACT PO conventions (UNOA:3, D96A, EAN008, `'` terminator, date format 102, GLN-14 qualifiers).

**DESADV structure (Briscoes conventions):**
```
UNB+UNOA:3+{MML_EDIS_ID}:14+9469313000007:14+{YYMMDD}:{HHMM}+{REF}++DESADV'
UNH+1+DESADV:D:96A:UN:EAN008'
BGM+351+{DESPATCH_REF}+9'
DTM+137:{YYYYMMDD}:102'    (document date)
DTM+11:{YYYYMMDD}:102'     (actual despatch date)
NAD+SE+{MML_EDIS_ID}::14'  (seller = MML)
NAD+BY+9469313000007::14'  (buyer = Briscoes Group)
RFF+ON:{PO_NUMBER}'         (Briscoes PO reference)
-- per store delivery:
CPS+{N}'
NAD+DP+{STORE_GLN}::9'     (deliver-to store GLN)
-- per line:
LIN+{SEQ}++{EAN13}:EN'
QTY+12:{DESPATCH_QTY}:EA'
UNS+S'
CNT+2:{LINE_COUNT}'
UNT+{SEGMENT_COUNT}+1'
UNZ+1+{REF}'
```

**Files:**
- Create: `briscoes.edi/parsers/briscoes_asn.py`
- Modify: `briscoes.edi/services/edi_service.py`
- Create: `briscoes.edi/tests/test_briscoes_asn.py`
- Create: `briscoes.edi/tests/fixtures/desadv_4500038166_expected.txt`

**Step 1: Create the expected DESADV fixture**

Create `briscoes.edi/tests/fixtures/desadv_4500038166_expected.txt` with a representative DESADV for PO 4500038166 based on the known PO data (stores 1005, 1007):

```
UNB+UNOA:3+MMLEDI:14+9469313000007:14+260305:0900+1++DESADV'
UNH+1+DESADV:D:96A:UN:EAN008'
BGM+351+DASN-4500038166+9'
DTM+137:20260305:102'
DTM+11:20260305:102'
NAD+SE+MMLEDI::14'
NAD+BY+9469313000007::14'
RFF+ON:4500038166'
CPS+1'
NAD+DP+1005::92'
LIN+10++9414844375629:EN'
QTY+12:10:EA'
LIN+20++9414844375636:EN'
QTY+12:7:EA'
CPS+2'
NAD+DP+1007::92'
LIN+30++9414844375629:EN'
QTY+12:7:EA'
UNS+S'
CNT+2:3'
UNT+20+1'
UNZ+1+1'
```

**Step 2: Write failing test**

Create `briscoes.edi/tests/test_briscoes_asn.py`:

```python
"""Tests for BriscoesASNGenerator (pure-Python, no Odoo ORM required)."""
import unittest
from ..parsers.briscoes_asn import BriscoesASNGenerator


class TestBriscoesASNGenerator(unittest.TestCase):

    def _make_despatch(self):
        """Build a minimal despatch data dict matching what EDIService extracts from stock.picking."""
        return {
            'po_number': '4500038166',
            'despatch_ref': 'DASN-4500038166',
            'despatch_date': '20260305',
            'mml_edis_id': 'MMLEDI',
            'ctrl_ref': '1',
            'deliveries': [
                {
                    'store_gln': '1005',
                    'lines': [
                        {'ean13': '9414844375629', 'qty': 10, 'seq': 10},
                        {'ean13': '9414844375636', 'qty': 7, 'seq': 20},
                    ],
                },
                {
                    'store_gln': '1007',
                    'lines': [
                        {'ean13': '9414844375629', 'qty': 7, 'seq': 30},
                    ],
                },
            ],
        }

    def test_generate_produces_valid_desadv(self):
        gen = BriscoesASNGenerator()
        despatch = self._make_despatch()
        result = gen.generate(despatch)
        self.assertIn("DESADV:D:96A:UN:EAN008", result)
        self.assertIn("BGM+351", result)
        self.assertIn("9414844375629:EN", result)
        self.assertIn("QTY+12:10:EA", result)

    def test_segment_count_in_unt_is_correct(self):
        gen = BriscoesASNGenerator()
        result = gen.generate(self._make_despatch())
        segments = [s for s in result.split("'") if s.strip()]
        # UNT should contain the count of all segments between UNH and UNT (inclusive)
        unt_line = next(s for s in segments if s.startswith('UNT'))
        count_in_unt = int(unt_line.split('+')[1])
        self.assertEqual(count_in_unt, len(segments) - 2)  # excluding UNB and UNZ

    def test_line_count_in_cnt_equals_lin_count(self):
        gen = BriscoesASNGenerator()
        result = gen.generate(self._make_despatch())
        segments = [s for s in result.split("'") if s.strip()]
        lin_count = sum(1 for s in segments if s.startswith('LIN+'))
        cnt_line = next(s for s in segments if s.startswith('CNT+2:'))
        count_in_cnt = int(cnt_line.split(':')[1])
        self.assertEqual(count_in_cnt, lin_count)

    def test_ean13_check_digit_validated(self):
        gen = BriscoesASNGenerator()
        bad = self._make_despatch()
        bad['deliveries'][0]['lines'][0]['ean13'] = '9414844375620'  # wrong check digit
        with self.assertRaises(ValueError):
            gen.generate(bad)
```

**Step 3: Run tests to confirm they fail**

```bash
python -m pytest "briscoes.edi/tests/test_briscoes_asn.py" -v 2>&1 | tail -20
```
Expected: FAIL — `BriscoesASNGenerator` doesn't exist yet.

**Step 4: Implement `BriscoesASNGenerator`**

Create `briscoes.edi/parsers/briscoes_asn.py`:

```python
"""
BriscoesASNGenerator — generates EDIFACT DESADV D96A for Briscoes Group.

Synthesised from Briscoes EDIFACT conventions (ORDERS D96A, EAN008, UNOA:3).
No Briscoes-specific ASN spec exists; this implementation follows the inbound
ORDERS structure and standard EDIFACT DESADV segment usage.

Segment terminator: '
Component separator: :
Data separator: +
"""
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)

_BRISCOES_GLN = '9469313000007'
_SEG_TERM = "'"
_COMP_SEP = ':'
_DATA_SEP = '+'


def _ean13_valid(barcode: str) -> bool:
    if not barcode or len(barcode) != 13 or not barcode.isdigit():
        return False
    digits = [int(c) for c in barcode]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1]))
    return (10 - total % 10) % 10 == digits[-1]


class BriscoesASNGenerator:
    """Generates an EDIFACT DESADV D96A message for a Briscoes despatch."""

    def generate(self, despatch: dict) -> str:
        """
        Generate and return the full EDIFACT DESADV message as a string.

        despatch dict keys:
          po_number      str   Briscoes PO number (e.g. '4500038166')
          despatch_ref   str   Unique ASN reference (e.g. 'DASN-4500038166')
          despatch_date  str   YYYYMMDD
          mml_edis_id    str   MML's EDIS sender ID (from ir.config_parameter)
          ctrl_ref       str   Interchange control reference (auto-increment)
          deliveries     list  [{store_gln, lines:[{ean13, qty, seq}]}]
        """
        self._validate_despatch(despatch)

        now = datetime.now(timezone.utc)
        date_str = now.strftime('%y%m%d')
        time_str = now.strftime('%H%M')

        segments = []

        # Interchange header
        segments.append(
            'UNB+UNOA:3+{mml}:14+{briscoes}:14+{date}:{time}+{ref}++DESADV'.format(
                mml=despatch['mml_edis_id'],
                briscoes=_BRISCOES_GLN,
                date=date_str,
                time=time_str,
                ref=despatch['ctrl_ref'],
            )
        )

        # Message header
        segments.append('UNH+1+DESADV:D:96A:UN:EAN008')

        # Beginning of message
        segments.append('BGM+351+{ref}+9'.format(ref=despatch['despatch_ref']))

        # Document date
        segments.append('DTM+137:{date}:102'.format(date=despatch['despatch_date']))

        # Despatch date
        segments.append('DTM+11:{date}:102'.format(date=despatch['despatch_date']))

        # Seller (MML)
        segments.append('NAD+SE+{mml}::14'.format(mml=despatch['mml_edis_id']))

        # Buyer (Briscoes Group)
        segments.append('NAD+BY+{gln}::14'.format(gln=_BRISCOES_GLN))

        # PO reference
        segments.append('RFF+ON:{po}'.format(po=despatch['po_number']))

        # Consignment packing sequences (one per store delivery)
        lin_count = 0
        for cps_seq, delivery in enumerate(despatch['deliveries'], start=1):
            segments.append('CPS+{n}'.format(n=cps_seq))
            segments.append('NAD+DP+{gln}::92'.format(gln=delivery['store_gln']))

            for line in delivery['lines']:
                segments.append('LIN+{seq}++{ean}:EN'.format(
                    seq=line['seq'], ean=line['ean13']
                ))
                segments.append('QTY+12:{qty}:EA'.format(qty=int(line['qty'])))
                lin_count += 1

        # Section control
        segments.append('UNS+S')

        # Control total — line count
        segments.append('CNT+2:{n}'.format(n=lin_count))

        # Message trailer — segment count includes UNH and UNT
        seg_count = len(segments)  # UNT will be segment count + 1 (itself)
        segments.append('UNT+{n}+1'.format(n=seg_count + 1))

        # Interchange trailer
        segments.append('UNZ+1+{ref}'.format(ref=despatch['ctrl_ref']))

        return _SEG_TERM.join(segments) + _SEG_TERM

    def _validate_despatch(self, despatch: dict) -> None:
        for delivery in despatch.get('deliveries', []):
            for line in delivery.get('lines', []):
                ean = line.get('ean13', '')
                if not _ean13_valid(str(ean)):
                    raise ValueError(
                        "Invalid EAN-13 barcode in despatch: '%s'. "
                        "Verify the product barcode before generating ASN." % ean
                    )
```

**Step 5: Run tests — confirm they pass**

```bash
python -m pytest "briscoes.edi/tests/test_briscoes_asn.py" -v 2>&1 | tail -20
```
Expected: all PASS.

**Step 6: Commit generator**

```bash
git add "briscoes.edi/parsers/briscoes_asn.py"
git add "briscoes.edi/tests/test_briscoes_asn.py"
git add "briscoes.edi/tests/fixtures/desadv_4500038166_expected.txt"
git commit -m "feat(mml_edi): add BriscoesASNGenerator — synthesised EDIFACT DESADV D96A"
```

---

### Task 13: Wire `EDIService.on_3pl_despatch_confirmed()` + ASN enable flag

**Context:** Connect the ASN generator to the 3PL despatch event. The legacy .NET service currently owns the EDIS VAN FTP path — the Odoo ASN uploader must be gated behind an `ir.config_parameter` flag so it can be activated independently of the .NET service retirement.

**Files:**
- Modify: `briscoes.edi/services/edi_service.py`
- Modify: `briscoes.edi/tests/test_edi_service.py`

**Step 1: Write failing test**

In `briscoes.edi/tests/test_edi_service.py`, add:

```python
def test_on_3pl_despatch_confirmed_uploads_asn_when_enabled(self):
    """When ASN is enabled and despatch event fires, ASN file must be uploaded via FTP."""
    # Set the enable flag
    self.env['ir.config_parameter'].sudo().set_param('mml_edi.asn_enabled', '1')

    # Create a mock event pointing to a stock.picking with an EDI-linked SO
    picking = self._make_edi_picking()
    event = self._make_event(res_model='stock.picking', res_id=picking.id)

    with patch('briscoes.edi.models.edi_ftp.EDIFTPHandler.upload_file') as mock_upload:
        svc = EDIService(self.env)
        svc.on_3pl_despatch_confirmed(event)
        self.assertTrue(mock_upload.called, "upload_file should have been called")
        uploaded_bytes = mock_upload.call_args[0][1]
        self.assertIn(b'DESADV', uploaded_bytes)

def test_on_3pl_despatch_confirmed_skips_when_disabled(self):
    """When ASN flag is disabled (default), no upload occurs."""
    self.env['ir.config_parameter'].sudo().set_param('mml_edi.asn_enabled', '0')
    event = self._make_event(res_model='stock.picking', res_id=1)
    with patch('briscoes.edi.models.edi_ftp.EDIFTPHandler.upload_file') as mock_upload:
        svc = EDIService(self.env)
        svc.on_3pl_despatch_confirmed(event)
        self.assertFalse(mock_upload.called)
```

**Step 2: Run to confirm they fail**

Expected: FAIL — `on_3pl_despatch_confirmed` is a no-op stub.

**Step 3: Implement `on_3pl_despatch_confirmed()`**

Replace the stub in `briscoes.edi/services/edi_service.py`:

```python
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)


class EDIService:
    """Public API for mml_edi. Retrieved via mml.registry.service('edi')."""

    def __init__(self, env):
        self.env = env

    def on_3pl_despatch_confirmed(self, event) -> None:
        """
        Called when Mainfreight confirms despatch of a stock.picking.
        Generates and uploads a Briscoes DESADV to the EDIS VAN FTP outbox.

        Gated by ir.config_parameter 'mml_edi.asn_enabled' = '1'.
        Default is disabled — activate once the legacy .NET service is retired.

        event.res_model = 'stock.picking'
        event.res_id    = picking.id
        """
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'mml_edi.asn_enabled', '0'
        )
        if enabled != '1':
            _logger.info('EDI ASN: disabled via mml_edi.asn_enabled — skipping')
            return

        if not event.res_id or event.res_model != 'stock.picking':
            _logger.warning('EDI ASN: event has no picking id — skipping')
            return

        picking = self.env['stock.picking'].browse(event.res_id)
        if not picking.exists():
            _logger.warning('EDI ASN: picking id=%s not found', event.res_id)
            return

        # Resolve the trading partner from the linked sale order
        sale_order = picking.sale_id
        if not sale_order:
            _logger.info('EDI ASN: picking %s has no linked SO — not an EDI order, skipping', picking.name)
            return

        partner = self.env['edi.trading.partner'].search([
            ('partner_id', '=', sale_order.partner_id.id),
            ('active', '=', True),
        ], limit=1)
        if not partner:
            _logger.info('EDI ASN: no EDI trading partner for SO %s — skipping', sale_order.name)
            return

        despatch = self._build_despatch_dict(picking, sale_order, partner)
        if not despatch:
            return

        try:
            self._generate_and_upload_asn(despatch, partner, picking)
        except Exception:
            _logger.exception('EDI ASN: failed to generate/upload ASN for picking %s', picking.name)
            # Log to edi.log but do not re-raise — don't block 3PL confirmation
            self.env['edi.log'].log(
                partner, 'outbound', 'error', 'error',
                'ASN generation failed for picking %s' % picking.name,
                detail='See server log for traceback.',
            )

    def _build_despatch_dict(self, picking, sale_order, partner) -> dict:
        """Extract despatch data from the stock.picking for the ASN generator."""
        mml_edis_id = self.env['ir.config_parameter'].sudo().get_param(
            'mml_edi.sender_id', 'MMLEDI'
        )
        ctrl_ref = self.env['ir.sequence'].sudo().next_by_code('edi.asn.ctrl.ref') or '1'

        # Group move lines by destination location (store)
        deliveries = {}
        seq = 10
        for move in picking.move_ids.filtered(lambda m: m.state == 'done'):
            store_gln = move.location_dest_id.edi_store_gln or ''
            if not store_gln:
                _logger.warning('EDI ASN: location %s has no edi_store_gln — line skipped', move.location_dest_id.name)
                continue
            barcode = move.product_id.barcode or ''
            if len(barcode) != 13:
                _logger.warning('EDI ASN: product %s has no valid EAN-13 — line skipped', move.product_id.display_name)
                continue
            deliveries.setdefault(store_gln, []).append({
                'ean13': barcode,
                'qty': move.quantity_done,
                'seq': seq,
            })
            seq += 10

        if not deliveries:
            _logger.warning('EDI ASN: no valid lines for picking %s — ASN not sent', picking.name)
            return {}

        po_number = sale_order.client_order_ref or sale_order.name

        return {
            'po_number': po_number,
            'despatch_ref': 'DASN-%s' % po_number,
            'despatch_date': datetime.now(timezone.utc).strftime('%Y%m%d'),
            'mml_edis_id': mml_edis_id,
            'ctrl_ref': ctrl_ref,
            'deliveries': [
                {'store_gln': gln, 'lines': lines}
                for gln, lines in deliveries.items()
            ],
        }

    def _generate_and_upload_asn(self, despatch: dict, partner, picking) -> None:
        """Generate DESADV bytes and upload to partner EDIS VAN outbox."""
        from ..parsers.briscoes_asn import BriscoesASNGenerator
        from ..models.edi_ftp import EDIFTPHandler

        gen = BriscoesASNGenerator()
        asn_content = gen.generate(despatch).encode('ascii')

        filename = 'DESADV_%s_%s.edi' % (
            despatch['po_number'],
            despatch['despatch_date'],
        )

        handler = EDIFTPHandler(partner)
        with handler.connection():
            handler.upload_file(filename, asn_content)

        # Audit trail
        self.env['ir.attachment'].create({
            'name': filename,
            'datas': __import__('base64').b64encode(asn_content).decode(),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'mimetype': 'text/plain',
        })
        picking.message_post(body='ASN sent to Briscoes: %s' % filename)

        self.env['edi.log'].log(
            partner, 'outbound', 'ack_sent', filename,
            'DESADV uploaded to EDIS VAN: %s (%d bytes)' % (filename, len(asn_content)),
        )
        _logger.info('EDI ASN: uploaded %s (%d bytes)', filename, len(asn_content))
```

**Step 4: Add `edi_store_gln` field to `stock.location`**

The despatch builder reads `move.location_dest_id.edi_store_gln`. This field must be added to `stock.location` via the mml_edi module. Create or modify `briscoes.edi/models/stock_location_ext.py`:

```python
from odoo import fields, models


class StockLocationEdiExt(models.Model):
    _inherit = 'stock.location'

    edi_store_gln = fields.Char(
        string='EDI Store GLN',
        help='Briscoes GLN for this delivery location. Used in DESADV (ASN) generation.',
    )
```

Add to `briscoes.edi/models/__init__.py`:
```python
from . import stock_location_ext
```

Add to manifest `data` list (after existing views):
```python
'views/stock_location_views.xml',
```

Create `briscoes.edi/views/stock_location_views.xml` with a field added to the stock.location form.

**Step 5: Add ASN ctrl ref sequence to data/ir_sequence.xml**

In `briscoes.edi/data/ir_sequence.xml`, add:
```xml
<record id="seq_edi_asn_ctrl_ref" model="ir.sequence">
    <field name="name">EDI ASN Control Reference</field>
    <field name="code">edi.asn.ctrl.ref</field>
    <field name="prefix"></field>
    <field name="padding">6</field>
    <field name="number_next">1</field>
    <field name="number_increment">1</field>
</record>
```

**Step 6: Run service tests**

```bash
python -m pytest "briscoes.edi/tests/test_edi_service.py" -v 2>&1 | tail -30
```
Expected: PASS.

**Step 7: Commit**

```bash
git add "briscoes.edi/"
git commit -m "feat(mml_edi): implement on_3pl_despatch_confirmed ASN upload — gated by mml_edi.asn_enabled flag"
```

---

## GROUP 6 — Operational Hardening

### Task 14: Cron failure alerting

**Context:** When scheduled polls or ROQ runs fail silently overnight, ops won't know until a customer complains. Add email alerts on critical cron failures in `edi_processor.py`, `mml_roq_forecast` cron, and `stock_3pl` tracking cron.

**Files:**
- Modify: `briscoes.edi/models/edi_processor.py` — `run_scheduled_poll()`
- Modify: `roq.model/mml_roq_forecast/models/roq_forecast_run.py` — cron action
- Modify: `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/cron/tracking_cron.py`

**Step 1: Create a shared alert helper**

In each module's main cron method, after the existing exception catch, add:

```python
def _send_cron_alert(self, module: str, subject: str, body: str) -> None:
    """Send an email alert when a cron job fails. Uses the standard mail.mail mechanism."""
    alert_email = self.env['ir.config_parameter'].sudo().get_param(
        'mml.cron_alert_email', False
    )
    if not alert_email:
        return
    self.env['mail.mail'].sudo().create({
        'subject': '[MML ALERT] %s: %s' % (module, subject),
        'body_html': '<pre>%s</pre>' % body,
        'email_to': alert_email,
    }).send()
```

**Step 2: Wire into each cron**

In `edi_processor.py` `run_scheduled_poll()`, update the exception handler:

```python
except Exception as exc:
    _logger.exception("[EDI] Poll failed for partner %s", partner.code)
    self.env["edi.log"].log(...)
    self._send_cron_alert(
        'mml_edi',
        'EDI poll failed for %s' % partner.code,
        str(exc),
    )
```

Apply the same pattern to the ROQ forecast run cron and the 3PL tracking cron.

**Step 3: Document the config parameter**

Add to the deploy runbook (Task 15): set `mml.cron_alert_email` in Settings → Technical → Parameters to `ops@mml.co.nz` or equivalent.

**Step 4: Commit**

```bash
git add briscoes.edi/models/edi_processor.py
git add roq.model/mml_roq_forecast/
git add mainfreight.3pl.intergration/
git commit -m "feat: add cron failure email alerting via mml.cron_alert_email config parameter"
```

---

### Task 15: Deployment runbook

**Context:** No documented procedure for installing this module set on the MML Odoo 19 instance. Write the runbook covering install order, credential configuration, sandbox testing, and go-live cutover steps.

**Files:**
- Create: `docs/runbook/pre-production-deploy.md`

**Step 1: Create the runbook**

Create `docs/runbook/pre-production-deploy.md` with the following sections:

```markdown
# MML Odoo Apps — Pre-Production Deployment Runbook

## Module Install Order

Install in this exact order (Odoo respects depends[] but explicit order prevents partial upgrades):

1. `mml_base`
2. `mml_forecast_core`
3. `mml_barcode_registry`
4. `mml_forecast_financial`
5. `mml_freight` + `mml_freight_dsv` + `mml_freight_knplus` + `mml_freight_mainfreight`
6. `stock_3pl_core` + `stock_3pl_mainfreight`
7. `mml_freight_3pl` (bridge — auto_install should handle, but verify)
8. `mml_roq_forecast` (+ `mml_roq_freight` bridge auto_install)
9. `mml_edi` (briscoes.edi module — note: directory must be named `mml_edi` in addons path)

## Required ir.config_parameter Values

Set these in Settings → Technical → System Parameters before go-live:

| Key | Value | Description |
|-----|-------|-------------|
| `mml.cron_alert_email` | `ops@mml.co.nz` | Cron failure alert destination |
| `mml_edi.sender_id` | `MMLEDI` | MML EDIS VAN sender ID |
| `mml_edi.asn_enabled` | `0` | Keep 0 until .NET service retired |
| `stock_3pl_mainfreight.webhook_secret` | `<secret>` | Mainfreight webhook HMAC secret |
| `mml_freight.dsv_api_url` | `<url>` | DSV API base URL |
| `mml_freight_dsv.access_token` | `<token>` | DSV access token |

## SFTP Host Key Configuration

For each EDI trading partner using SFTP:
1. Run: `ssh-keyscan -t rsa <ftp_host> | awk '{print $3}'`
2. Set the base64 output in Settings → EDI → Trading Partners → SFTP Host Key

## Briscoes Store GLN Configuration

For each Briscoes store delivery location in Odoo (Inventory → Configuration → Locations):
- Set EDI Store GLN to the Briscoes GLN from the PO NAD+UD / LOC+7 segments

## Sandbox Testing Checklist

- [ ] Install all modules on ODOOTEST database
- [ ] Configure test EDIS VAN credentials (Test/FromEDIS path)
- [ ] Run EDI poll manually — confirm PO ingested
- [ ] Approve order in review queue — confirm SO created
- [ ] Generate ORDRSP — confirm uploaded to Test/ToEDIS
- [ ] Confirm Mainfreight webhook receives test payload with correct HMAC
- [ ] Run ROQ forecast run — confirm no AccessError
- [ ] Raise draft PO via wizard — confirm duplicate guard fires on second attempt
- [ ] Confirm cron alert email arrives on scheduled poll failure

## Go-Live Cutover: EDI ASN

1. Confirm legacy .NET BriscoesEditOrder service is stopped (or in monitoring-only mode)
2. Set `mml_edi.asn_enabled` = `1` in ir.config_parameter
3. Process a test despatch and confirm DESADV appears in EDIS VAN `/ToEDIS/`
4. Monitor `edi.log` for any upload errors

## Rollback Procedure

If critical issues found post-install:
1. Set all `mml_edi.asn_enabled` = `0` immediately
2. Restart the legacy .NET service
3. Do NOT uninstall modules with existing data — use `installable=False` and restart
```

**Step 2: Commit**

```bash
git add docs/runbook/pre-production-deploy.md
git commit -m "docs: add pre-production deployment runbook with install order and config checklist"
```

---

## Completion Checklist

Before declaring the sprint done, verify:

- [ ] Group 1 committed: `mml_forecast_demand` deleted, improvements in `mml_roq_forecast`
- [ ] `mml_base` service registry re-hydrates after `_SERVICE_REGISTRY.clear()`
- [ ] `mml.license` read accessible to `base.group_user`
- [ ] SFTP connects with host key verification; connection refused without key configured
- [ ] `edi.bulk.action` in ACL
- [ ] EAN-13 validated before ORDRSP
- [ ] `roq_raise_po_wizard`: second raise → UserError; multi-warehouse → both POs linked
- [ ] PO create no longer uses `sudo()`
- [ ] `roq.shipment.group` write blocked for `group_user`
- [ ] ABC classifier honours zero band percentages
- [ ] Company filter present in demand history queries
- [ ] K+N access token has `password=True`
- [ ] DSV download rejects non-DSV URLs
- [ ] MF webhook logs only after auth passes
- [ ] `signed_by` truncated and stripped before write
- [ ] App icons present for `mml_freight` and `mml_roq_forecast`
- [ ] `mml_freight_demo` has `installable=False`
- [ ] `BriscoesASNGenerator` generates valid DESADV; EAN-13 validated
- [ ] `on_3pl_despatch_confirmed` uploads ASN when flag enabled; skips when disabled
- [ ] Cron alert emails fire on failure
- [ ] Runbook committed to `docs/runbook/`
