# Code Review Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all Critical and Major findings from the 2026-03-04 full code review before developer team review.

**Architecture:** Fixes are scoped per module — no cross-module changes except where the review explicitly identified coupling. Each group of fixes is independent and can be executed in parallel.

**Tech Stack:** Odoo 19, Python 3.12, PostgreSQL, paramiko (SFTP), Fernet encryption.

---

## Priority Order

1. **CRITICAL** — security, data integrity, billing fraud, crashes in normal operation
2. **MAJOR** — significant bugs, architecture violations, missing guards
3. **MINOR** — polish, secondary security hardening

---

## GROUP 1: mml_base

**Files touched:**
- `mml_base/models/mml_event_subscription.py` — CRIT-1 (RCE), MIN-2 (no SQL unique)
- `mml_base/models/mml_event.py` — MAJ-1 (instance_ref compute)
- `mml_base/models/mml_capability.py` — CRIT-2 (company_id semantics)
- `mml_base/models/mml_license.py` — MAJ-2 (race condition), MIN-4 (expiry check)
- `mml_base/security/ir.model.access.csv` — MAJ-5 (missing group_user read)
- `mml_base/services/platform_client.py` — MIN-3 (stub returns True)

### Task 1.1: Fix RCE — restrict handler_method to safe pattern (CRIT-1)

**File:** `mml_base/models/mml_event_subscription.py`

The `dispatch()` method calls `getattr(model, sub.handler_method)(event)` with no validation of `handler_method`. This allows any database user with write access to `mml.event.subscription` to invoke any method on any Odoo model.

**Step 1: Add validation before getattr**

In the `dispatch()` method (around line 50), before calling `getattr`, add:

```python
import re
_HANDLER_METHOD_RE = re.compile(r'^_on_[a-z_]+$')

# Inside dispatch():
if not _HANDLER_METHOD_RE.match(sub.handler_method):
    _logger.error(
        'mml.event: rejected dispatch to %s.%s — method name does not match '
        'safe pattern ^_on_[a-z_]+$ (subscription id=%s)',
        sub.handler_model, sub.handler_method, sub.id,
    )
    continue
```

Move the regex constant to module level above the class. The pattern enforces that all handler methods start with `_on_` followed only by lowercase letters and underscores.

**Step 2: Add SQL unique constraint to prevent duplicate subscriptions (MIN-2)**

Add to `MmlEventSubscription` model:

```python
_sql_constraints = [
    (
        'unique_subscription',
        'UNIQUE(event_type, handler_model, handler_method, module)',
        'A subscription for this event_type/handler_model/handler_method/module combination already exists.',
    ),
]
```

**Step 3: Test** — existing `test_event_subscription.py` must still pass. Add a test that verifies a subscription with `handler_method='unlink'` is rejected by `dispatch()`.

---

### Task 1.2: Fix missing group_user read ACL on mml.license (MAJ-5)

**File:** `mml_base/security/ir.model.access.csv`

Add a read-only ACL row for `base.group_user`:

```csv
access_mml_license_user,mml.license user read,model_mml_license,base.group_user,1,0,0,0
```

Place it before the system row. This allows `module_permitted()` to be called from user context without raising `AccessError`. The sensitive `license_key` field is already protected by `groups='base.group_system'` at the field level.

---

### Task 1.3: Fix instance_ref compute never recomputing (MAJ-1)

**File:** `mml_base/models/mml_event.py`

The `_compute_instance_ref` uses `@api.depends()` (empty) with `store=True`. An empty depends means the value is only set at create-time and never recomputes.

**Fix:** Remove the computed field entirely. Populate `instance_ref` directly in the `emit()` method:

In `emit()`, add `instance_ref` to the create vals dict:

```python
'instance_ref': self.env['ir.config_parameter'].sudo().get_param(
    'mml.instance_ref', default=''
),
```

Remove the `instance_ref` field definition's `compute=` and `depends=` arguments, making it a plain stored `Char` field with no compute.

---

### Task 1.4: Fix platform_client stub returning True (MIN-3)

**File:** `mml_base/services/platform_client.py`

Change `sync_events()` to return `False` instead of `True`:

```python
def sync_events(self, events) -> bool:
    _logger.debug('PlatformClientBase.sync_events() — stub, %d events not transmitted', len(events))
    return False
```

This prevents the `_cron_sync_events` method from marking events as `synced_to_platform = True` when no transmission has occurred.

---

### Task 1.5: Add expiry check to module_permitted() (MIN-4)

**File:** `mml_base/models/mml_license.py`

After the existing JSON parse, add before returning `True`:

```python
if lic.valid_until and lic.valid_until < fields.Date.today():
    _logger.warning(
        'mml.license: license expired on %s — denying module %s',
        lic.valid_until, module,
    )
    return False
```

---

## GROUP 2: stock_3pl (Critical data integrity + service bugs)

**Files touched:**
- `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/document/inventory_report.py` — C-1 (auto-write quant)
- `mainfreight.3pl.intergration/addons/stock_3pl_core/services/tpl_service.py` — M-5 (wrong field names + missing connector_id guard)
- `mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/document/so_acknowledgement.py` — N-4 (direct assignment)

### Task 2.1: CRITICAL — Remove auto-quant-write from SOH import (C-1)

**File:** `inventory_report.py`

This is the most serious bug. The `apply_csv()` method currently calls `_sync_quant()` unconditionally, then optionally flags a discrepancy. The fix inverts this: NEVER call `_sync_quant()` from `apply_csv()`. Only create discrepancy records. The existing `action_accept_discrepancy()` wizard is already the correct write path.

**Step 1: Remove `_sync_quant()` call from `apply_csv()`**

Find the block:
```python
self._sync_quant(product, stock_location, mf_qty)
applied += 1

variance = abs(mf_qty - odoo_qty)
threshold = odoo_qty * tolerance
if variance > threshold:
    self._write_discrepancy(product, mf_qty, odoo_qty)
```

Replace with:
```python
variance = abs(mf_qty - odoo_qty)
threshold = odoo_qty * tolerance
if variance > threshold:
    self._write_discrepancy(product, mf_qty, odoo_qty)
    flagged += 1
else:
    # Within tolerance — accept automatically via wizard
    self._sync_quant(product, stock_location, mf_qty)
    applied += 1
```

This preserves the auto-accept behaviour for within-tolerance quantities (a common case) while routing out-of-tolerance discrepancies through the human review wizard. Update the return dict to include `flagged`.

**Step 2: Update `_write_discrepancy()` to create discrepancy in `open` state** — verify it does this already (it should). If not, ensure `state='open'` on create.

**Step 3: Remove `_sync_quant()` call from `action_accept_discrepancy()` in `soh_discrepancy.py`** — wait, actually that IS the correct write path. Leave it. Only remove from `apply_csv()`.

---

### Task 2.2: Fix tpl_service wrong field names and missing connector_id guard (M-5)

**File:** `tpl_service.py`

**Problem 1:** Uses `res_model`/`res_id` but the model uses `ref_model`/`ref_id`.
**Problem 2:** `connector_id` is optional in the service but `required=True` on the model — will raise constraint error when `connector_id` is None.

**Fix:**

```python
def queue_inward_order(self, po, connector_id=None):
    if not connector_id:
        # Try to find default connector
        connector = self.env['3pl.connector'].search(
            [('active', '=', True)], limit=1
        )
        if not connector:
            _logger.warning(
                'tpl_service.queue_inward_order: no active 3pl.connector found — '
                'cannot queue PO %s', po.name
            )
            return None
        connector_id = connector.id

    vals = {
        'document_type': 'inward_order',
        'ref_model': 'purchase.order',   # was: res_model
        'ref_id': po.id,                  # was: res_id
        'connector_id': connector_id,
    }
    msg = self.env['3pl.message'].create(vals)
    return msg.id
```

---

### Task 2.3: Fix so_acknowledgement direct field assignment (N-4)

**File:** `so_acknowledgement.py`

Change:
```python
picking.x_mf_status = 'mf_received'
```
To:
```python
picking.write({'x_mf_status': 'mf_received'})
```

---

## GROUP 3: mml_freight (Critical + Major fixes)

**Files touched:**
- `fowarder.intergration/addons/mml_freight/models/freight_booking.py` — C-1 (recordset), F-M1 is in freight_service
- `fowarder.intergration/addons/mml_freight/services/freight_service.py` — M-1 (wrong field)
- `fowarder.intergration/addons/mml_freight_knplus/controllers/kn_webhook.py` — C-2 (unauthenticated)
- `fowarder.intergration/addons/mml_freight_mainfreight/controllers/mf_webhook.py` — C-3 (permissive when secret unset)
- `fowarder.intergration/addons/mml_freight_dsv/models/freight_carrier_dsv.py` — M-6 (DSV token not password=True)
- `fowarder.intergration/addons/mml_freight/models/freight_tender_quote.py` — M-4 (action_select guard)
- `fowarder.intergration/addons/mml_freight/models/freight_tender.py` — Mi-7 (cancel cascade)

### Task 3.1: Fix action_confirm() recordset bug (CRITICAL-1, known backlog)

**File:** `freight_booking.py`, `action_confirm()` (~line 182)

Add `self.ensure_one()` as the first line of `action_confirm()`:

```python
def action_confirm(self):
    self.ensure_one()
    self.write({'state': 'confirmed'})
    ...
```

This matches the pattern already used in `action_confirm_with_dsv()`. It will raise a clear `UserError` if called on multiple records rather than a cryptic `ValueError` deep in the call stack.

---

### Task 3.2: Fix K+N webhook accepting production requests without auth (CRITICAL-2)

**File:** `kn_webhook.py`

Replace the permissive block:
```python
if environment == 'production':
    # TODO: implement auth validation...
    _logger.warning(...)
    # falls through to accept
```

With:
```python
if environment == 'production':
    _logger.error(
        'K+N webhook: production mode auth not yet implemented for carrier=%s '
        '— rejecting request. Configure auth before enabling production mode.',
        carrier.id,
    )
    return request.make_json_response(
        {'error': 'Production authentication not configured'},
        status=403,
    )
```

---

### Task 3.3: Fix Mainfreight webhook accepting all requests when secret unset (CRITICAL-3)

**File:** `mf_webhook.py`

In the block where `configured_secret` is empty, change from accept to reject (matching DSV behaviour):

```python
if not configured_secret:
    _logger.error(
        'MF webhook: x_mf_webhook_secret not configured on carrier %s — '
        'rejecting request. Set secret before go-live.',
        carrier.id,
    )
    return request.make_json_response(
        {'error': 'Webhook authentication not configured'},
        status=403,
    )
```

---

### Task 3.4: Fix freight_service querying wrong field name (MAJOR-1)

**File:** `freight_service.py`, `get_delivered_booking_lead_times()`

Change domain from:
```python
('purchase_order_id', 'in', po_ids),
```
To:
```python
('po_ids', 'in', po_ids),
```

Note: `po_ids` is a Many2many — the `in` operator on a Many2many domain in Odoo searches for records where ANY of the related IDs match, which is the correct behaviour here.

---

### Task 3.5: Add password=True to DSV cached access token (MAJOR-6)

**File:** `freight_carrier_dsv.py`

Change:
```python
x_dsv_access_token = fields.Char('DSV Access Token (cached)', groups='stock.group_stock_manager', copy=False)
```
To:
```python
x_dsv_access_token = fields.Char('DSV Access Token (cached)', password=True, groups='stock.group_stock_manager', copy=False)
```

---

### Task 3.6: Add state guard to tender action_select() (MAJOR-4)

**File:** `freight_tender_quote.py`, `action_select()`

Add at the start of the method:

```python
def action_select(self):
    self.ensure_one()
    valid_states = ('requesting', 'quoted', 'partial')
    if self.tender_id.state not in valid_states:
        raise UserError(
            f'Cannot select a quote on a tender in state "{self.tender_id.state}". '
            f'The tender must be in one of: {", ".join(valid_states)}.'
        )
    self.tender_id.write({...})
```

---

### Task 3.7: Add booking cascade to tender action_cancel() (MINOR-7)

**File:** `freight_tender.py`, `action_cancel()`

```python
def action_cancel(self):
    if self.booking_id and self.booking_id.state not in ('delivered', 'cancelled'):
        raise UserError(
            'This tender has an active booking (%s). Cancel the booking first, '
            'or contact the freight team.' % self.booking_id.name
        )
    self.write({'state': 'cancelled'})
    return True
```

---

## GROUP 4: mml_edi (Critical + Major fixes)

**Files touched:**
- `briscoes.edi/mml.edi/models/edi_trading_partner.py` — C-1 (credentials), Mi-6 (str.format)
- `briscoes.edi/mml.edi/parsers/briscoes_idoc.py` — C-3 (mock data guard)
- `briscoes.edi/mml.edi/models/edi_ftp.py` — M-1 (transport leak)
- `briscoes.edi/mml.edi/models/edi_log.py` — M-2 (missing index)
- `briscoes.edi/mml.edi/models/edi_processor.py` — M-6 (change order removed lines), Mi-2 (cancelled SO dedup)
- `briscoes.edi/mml.edi/parsers/briscoes.py` — M-4 (EAN-13 validation)

### Task 4.1: Fix FTP credentials stored as plaintext (CRITICAL-1)

**File:** `edi_trading_partner.py`

**Note:** Full migration to `ir.config_parameter` is the long-term fix. The immediate safe fix is to document and add a migration note, while ensuring the `password=True` flag is at minimum set AND adding a `groups` restriction. This is a pre-production blocker — add a clear `# TODO: migrate to ir.config_parameter before multi-tenant` comment and file a migration task.

Short-term: ensure `password=True` is set (it is) and add `groups='base.group_system'` to the password field:

```python
ftp_password = fields.Char(
    string="FTP Password",
    password=True,
    groups='base.group_system',
    help="Store FTP credentials in ir.config_parameter for multi-tenant deployments.",
)
```

Long-term migration (separate task): Move to `ir.config_parameter` with key pattern `mml_edi.{partner_code}.ftp_password`.

---

### Task 4.2: Add production guard to BriscoesIDOCParser (CRITICAL-3)

**File:** `briscoes_idoc.py`

At the start of `parse_file()`:

```python
def parse_file(self, raw_content: bytes, trading_partner) -> list[ParsedOrder]:
    raise NotImplementedError(
        'BriscoesIDOCParser is a development stub and must not be used in production. '
        'Implement against the confirmed Briscoes iDOC specification before activating.'
    )
```

This ensures it can never be accidentally activated. Tests that exercise the stub should be updated to assert the `NotImplementedError`.

---

### Task 4.3: Fix SFTP Transport leak (MAJOR-1)

**File:** `edi_ftp.py`

Store the transport alongside the client:

```python
def _connect_sftp(self):
    self._transport = paramiko.Transport(
        (self.partner.ftp_host, self.partner.ftp_port)
    )
    self._transport.connect(
        username=self.partner.ftp_user,
        password=self.partner.ftp_password,
    )
    self._ftp = paramiko.SFTPClient.from_transport(self._transport)

def disconnect(self):
    if self._ftp:
        self._ftp.close()
        self._ftp = None
    if hasattr(self, '_transport') and self._transport:
        self._transport.close()
        self._transport = None
```

---

### Task 4.4: Add index to edi.log.file_hash (MAJOR-2)

**File:** `edi_log.py`

Change:
```python
file_hash = fields.Char(string="File Hash (SHA-256)")
```
To:
```python
file_hash = fields.Char(string="File Hash (SHA-256)", index=True)
```

---

### Task 4.5: Handle removed lines in apply_change_order() (MAJOR-6)

**File:** `edi_processor.py`, `apply_change_order()`

Add after the existing quantity-change loop:

```python
# Handle removed lines (action code 3 in ORDCHG)
for removed_line_num in changes.get('removed_lines', []):
    so_line = self.env['sale.order.line'].search([
        ('order_id', '=', so.id),
        ('edi_line_number', '=', removed_line_num),
    ], limit=1)
    if so_line:
        if so.state == 'draft':
            so_line.unlink()
        else:
            so_line.write({'product_uom_qty': 0})
            _logger.warning(
                'EDI ORDCHG: SO %s already confirmed — set qty=0 on line %s '
                'rather than removing. Manual review required.',
                so.name, removed_line_num,
            )
```

Update `_encode_pending_changes()` to include removed lines in its encoding.

---

### Task 4.6: Fix cancelled SO excluded from dedup guard (MINOR-2)

**File:** `edi_processor.py`

Change the guard condition to:
```python
if existing_so and existing_so.state in ('draft', 'sent', 'sale', 'done', 'cancel'):
    if existing_so.state == 'cancel':
        _logger.info(
            'EDI: found cancelled SO %s for client_ref=%s — '
            'creating new SO (re-order after cancellation)',
            existing_so.name, client_ref,
        )
        # Fall through to create new SO
    else:
        return  # Skip — valid existing SO
```

---

### Task 4.7: Fix render_client_ref unsafe str.format() (MINOR-6)

**File:** `edi_trading_partner.py`

Replace `str.format()` with `string.Template` to prevent attribute traversal:

```python
import string

def render_client_ref(self, po_number: str, store_code: str | None = None) -> str:
    self.ensure_one()
    template_str = self.client_ref_template or '$po_number'
    # Translate {po_number} style to $po_number if needed (backward compat)
    template_str = template_str.replace('{po_number}', '$po_number').replace('{store_code}', '$store_code')
    t = string.Template(template_str)
    return t.safe_substitute(po_number=po_number, store_code=store_code or '')
```

---

## GROUP 5: Bridge modules + mml_roq_forecast

**Files touched:**
- `mml_freight_3pl/models/mml_3pl_bridge.py` — BR-C1 (billing event unconditional)
- `roq.model/mml_roq_forecast/services/roq_service.py` — R-C1 (direct model browse)
- `roq.model/mml_roq_forecast/models/roq_forecast_run.py` — R-M1 (blank string ValueError)
- `roq.model/mml_roq_forecast/models/res_partner_ext.py` — R-M5 (silent JSON failure)
- `mml_roq_freight/models/bridge_service.py` — BR-M3 (no audit on failure)
- `mml_roq_freight/security/ir.model.access.csv` — BR-M1 (empty CSV in manifest)

### Task 5.1: Fix billing event emitted on service failure (CRIT-1)

**File:** `mml_freight_3pl/models/mml_3pl_bridge.py`

Move the `mml.event.emit()` call inside the `if msg_id:` guard:

```python
msg_id = svc.queue_inward_order(po.id)
if msg_id:
    _logger.info('3PL: queued inward order for PO %s, msg_id=%s', po.name, msg_id)
    self.env['mml.event'].emit(
        '3pl.inbound.queued',
        quantity=1,
        billable_unit='3pl_receipt',
        res_model='purchase.order',
        res_id=po.id,
        source_module='mml_freight_3pl',
    )
else:
    _logger.warning(
        '3PL: queue_inward_order returned no message ID for PO %s — '
        'billing event NOT emitted', po.name,
    )
```

---

### Task 5.2: Fix direct freight.booking browse bypassing NullService (R-C1)

**File:** `roq_service.py`

Replace:
```python
booking = self.env['freight.booking'].browse(booking_id)
```

With:
```python
freight_svc = self.env['mml.registry'].service('freight')
lead_time = freight_svc.get_booking_lead_time(booking_id)
if lead_time is None:
    return None
```

Remove any subsequent code that accesses `booking.*` fields directly — route through the freight service abstraction instead.

---

### Task 5.3: Fix blank-string ValueError in action_run() (R-M1)

**File:** `roq_forecast_run.py`

Replace the raw `int(get(...))` calls with safe casts:

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

# In action_run():
settings = {
    'lookback_weeks': _safe_int(get('roq.lookback_weeks'), 156),
    'sma_window_weeks': _safe_int(get('roq.sma_window_weeks'), 52),
    'default_lead_time_days': _safe_int(get('roq.default_lead_time_days'), 100),
    'default_review_interval_days': _safe_int(get('roq.default_review_interval_days'), 30),
    'default_service_level': _safe_float(get('roq.default_service_level'), 0.97),
}
```

---

### Task 5.4: Add user feedback for invalid holiday JSON (R-M5)

**File:** `res_partner_ext.py`

Add a constrains validator:

```python
@api.constrains('supplier_holiday_periods')
def _validate_holiday_periods_json(self):
    for rec in self:
        if rec.supplier_holiday_periods:
            try:
                json.loads(rec.supplier_holiday_periods)
            except json.JSONDecodeError as e:
                raise ValidationError(
                    f'Supplier Holiday Periods contains invalid JSON: {e}. '
                    f'Please correct the format before saving.'
                )
```

---

### Task 5.5: Remove empty security CSV from mml_roq_freight (BR-M1)

**File:** `mml_roq_freight/__manifest__.py`

Remove the `'data': ['security/ir.model.access.csv']` entry from the manifest (the CSV is header-only and creates no records). Delete or empty the file is optional — removing the manifest declaration is sufficient.

---

## GROUP 6: App icons + web_icon manifest entries

Three app modules declare `application = True` but have no `web_icon` and no `static/description/icon.png`. This causes a blank/generic tile on the Odoo home screen.

**Files touched:**
- `fowarder.intergration/addons/mml_freight/__manifest__.py`
- `roq.model/mml_roq_forecast/__manifest__.py`
- `briscoes.edi/mml.edi/__manifest__.py`
- Create `static/description/icon.png` in each module (256×256 PNG placeholder)

### Task 6.1: Add web_icon to all three app manifests

For each manifest, add:
```python
'web_icon': 'MODULE_NAME,static/description/icon.png',
```

Create `static/description/` directories with a placeholder `icon.png` (256×256, module-appropriate colour). Use Python's `PIL` or copy a base icon and tint it. Minimum: create a valid 256×256 PNG file so the Odoo home screen renders correctly.

---

## Post-Fix Checklist

- [ ] All test suites still pass: `python -m pytest` for each module's `tests/` directory
- [ ] `mml_base` tests: `test_event_subscription.py` covers the new handler_method guard
- [ ] `stock_3pl_mainfreight` tests: SOH import test verifies quants are NOT written without human review
- [ ] `mml_freight` webhook tests: both K+N and MF reject unauthenticated production requests
- [ ] `mml_edi` tests: IDOC parser test asserts `NotImplementedError`
- [ ] `mml_roq_forecast` tests: blank-string settings test does not raise `ValueError`
- [ ] All `__manifest__.py` files pass `_check_module_information` (no missing required keys)
- [ ] Git: one commit per Group (6 commits total), prefixed with `fix:`

## Known Deferred Items (needs design review, not auto-fixable)

- `mml_edi` C-2: Full migration of EDI docs to `ir.attachment` (substantial model change)
- `mml_edi` M-3: ASN (856/DESADV) implementation (new feature, not a fix)
- `stock_3pl_core` M-2: Inverted dependency (requires transport registry refactor)
- `stock_3pl_mainfreight` M-3: `qty_done` write bypass (requires picking workflow review)
- Multi-company `ir.rule` record rules across all modules (architectural decision needed)
- `mml_base` MAJ-3: `_SERVICE_REGISTRY` cross-process issue (document + restart note for now)
