# Odoo 19 Compliance Sprint — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all Odoo 19 API compliance issues identified in the deployment readiness review, add external dependency manifests, and scaffold i18n directories across all 15 modules.

**Architecture:** Surgical fixes across 6 git repositories. Tasks are ordered by severity (blockers first, then medium, then scaffolding). Each task commits to the repo it touches. No cross-module changes in a single commit.

**Tech Stack:** Python/Odoo ORM, standard Odoo i18n (.pot files), pip requirements.txt

---

## Context for implementer

### Repository map
```
E:\ClaudeCode\projects\mml.odoo.apps\          ← ROOT repo (mml_base, bridges, barcode)
E:\ClaudeCode\projects\mml.odoo.apps\mainfreight.3pl.intergration\  ← separate git repo
E:\ClaudeCode\projects\mml.odoo.apps\roq.model\                     ← separate git repo
E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\               ← separate git repo
E:\ClaudeCode\projects\mml.odoo.apps\fowarder.intergration\         ← separate git repo
E:\ClaudeCode\projects\mml.odoo.apps\briscoes.edi\                  ← separate git repo
```

All `git` commands must be run from inside the relevant sub-repo directory.

### Odoo 19 API changes that drive these tasks
- `@api.model` on `create()` must be `@api.model_create_multi` — the method receives `vals_list` (list of dicts), not a single `vals` dict
- `name_get()` was removed in Odoo 18 — use `_compute_display_name()` instead
- `read_group(domain, fields, groupby)` deprecated — use `_read_group(domain, groupby, aggregates)` which returns list of tuples (not list of dicts)

---

## Group A: Blockers — API Compatibility

### Task 1: Fix `@api.model_create_multi` in 3PL connector models

Three `create()` overrides in the `mainfreight.3pl.intergration` repo use `@api.model` (Odoo <16 style). In Odoo 19 this silently processes only the first record when bulk-creating connectors.

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\mainfreight.3pl.intergration`

**Files to modify:**
- `addons/stock_3pl_core/models/connector.py` lines 94–97
- `addons/stock_3pl_mainfreight/models/connector_mf.py` lines 41–46
- `addons/stock_3pl_mainfreight/models/connector_freightways.py` lines 18–23

**Step 1: Open and read all three files to confirm current state**

```bash
# In mainfreight.3pl.intergration repo
grep -n "@api.model" addons/stock_3pl_core/models/connector.py
grep -n "@api.model" addons/stock_3pl_mainfreight/models/connector_mf.py
grep -n "@api.model" addons/stock_3pl_mainfreight/models/connector_freightways.py
```
Expected: each prints one line with `@api.model` (without `_create_multi`).

**Step 2: Write the failing test**

Add to `addons/stock_3pl_core/tests/test_connector.py` (inside the existing Odoo test class, or create the file if absent):

```python
@tagged('post_install', '-at_install')
class TestConnectorCreateMulti(TransactionCase):
    """Verify that create() accepts a list of vals (Odoo 19 multi-create pattern)."""

    def test_create_multi_base_connector(self):
        """Bulk create two base connectors in one ORM call."""
        vals_list = [
            {
                'name': 'Test Connector A',
                'connector_type': 'rest',
                'api_base_url': 'https://test-a.example.com',
            },
            {
                'name': 'Test Connector B',
                'connector_type': 'rest',
                'api_base_url': 'https://test-b.example.com',
            },
        ]
        connectors = self.env['3pl.connector'].create(vals_list)
        self.assertEqual(len(connectors), 2)
        names = connectors.mapped('name')
        self.assertIn('Test Connector A', names)
        self.assertIn('Test Connector B', names)
```

**Step 3: Run test to verify it fails**

```bash
# From Odoo root (not inside the sub-repo)
odoo-bin --test-enable -d ODOOTEST --test-tags /stock_3pl_core:TestConnectorCreateMulti --stop-after-init
```
Expected: FAIL or test creates only 1 connector (assert `len == 2` fails).

**Step 4: Fix `connector.py`**

In `addons/stock_3pl_core/models/connector.py`, replace lines 94–97:

```python
# BEFORE:
    @api.model
    def create(self, vals):
        self._encrypt_credential_vals(vals)
        return super().create(vals)

# AFTER:
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._encrypt_credential_vals(vals)
        return super().create(vals_list)
```

**Step 5: Fix `connector_mf.py`**

In `addons/stock_3pl_mainfreight/models/connector_mf.py`, replace lines 41–46:

```python
# BEFORE:
    @api.model
    def create(self, vals):
        for field in self._MF_CREDENTIAL_FIELDS:
            if field in vals and vals[field]:
                vals[field] = encrypt_credential(self.env, vals[field])
        return super().create(vals)

# AFTER:
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for field in self._MF_CREDENTIAL_FIELDS:
                if field in vals and vals[field]:
                    vals[field] = encrypt_credential(self.env, vals[field])
        return super().create(vals_list)
```

**Step 6: Fix `connector_freightways.py`**

In `addons/stock_3pl_mainfreight/models/connector_freightways.py`, replace lines 18–23:

```python
# BEFORE:
    @api.model
    def create(self, vals):
        for field in self._FW_CREDENTIAL_FIELDS:
            if field in vals and vals[field]:
                vals[field] = encrypt_credential(self.env, vals[field])
        return super().create(vals)

# AFTER:
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            for field in self._FW_CREDENTIAL_FIELDS:
                if field in vals and vals[field]:
                    vals[field] = encrypt_credential(self.env, vals[field])
        return super().create(vals_list)
```

**Step 7: Re-run the test**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /stock_3pl_core:TestConnectorCreateMulti --stop-after-init
```
Expected: PASS, 2 connectors created.

**Step 8: Run full module tests to check for regressions**

```bash
python -m pytest addons/stock_3pl_core/tests/ addons/stock_3pl_mainfreight/tests/ -q -m "not odoo_integration"
```
Expected: all pass.

**Step 9: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration"
git add addons/stock_3pl_core/models/connector.py \
        addons/stock_3pl_mainfreight/models/connector_mf.py \
        addons/stock_3pl_mainfreight/models/connector_freightways.py \
        addons/stock_3pl_core/tests/test_connector.py
git commit -m "fix(3pl): migrate create() to @api.model_create_multi (Odoo 19)"
```

---

### Task 2: Replace `name_get()` with `_compute_display_name()` in port models

`name_get()` was removed in Odoo 18. Both port models will silently fall back to showing the record ID in dropdowns and Many2one fields.

**Files to modify:**
- `E:\ClaudeCode\projects\mml.odoo.apps\roq.model\mml_roq_forecast\models\roq_port.py` (line 33)
- `E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_core\models\forecast_origin_port.py` (line 39)

These are in **different git repos** — commit separately.

#### Part A: `roq_port.py` (roq.model repo)

**Step 1: Write failing test**

Add to `E:\ClaudeCode\projects\mml.odoo.apps\roq.model\mml_roq_forecast\tests\test_roq_port.py`:

```python
@tagged('post_install', '-at_install')
class TestRoqPortDisplayName(TransactionCase):
    def test_display_name_format(self):
        port = self.env['roq.port'].create({'code': 'cnsha', 'name': 'Shanghai'})
        # display_name must use the code — name format (code uppercased by create())
        self.assertEqual(port.display_name, 'CNSHA — Shanghai')

    def test_display_name_used_in_name_search(self):
        port = self.env['roq.port'].create({'code': 'NZAKL', 'name': 'Auckland'})
        results = self.env['roq.port'].name_search('NZAKL')
        self.assertTrue(any(r[0] == port.id for r in results))
```

**Step 2: Run to confirm fail**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /mml_roq_forecast:TestRoqPortDisplayName --stop-after-init
```
Expected: FAIL — `display_name` returns just `'Shanghai'` (ORM default) not `'CNSHA — Shanghai'`.

**Step 3: Fix `roq_port.py`**

In `roq.model/mml_roq_forecast/models/roq_port.py`, **replace** lines 33–34:

```python
# REMOVE this:
    def name_get(self):
        return [(p.id, f'{p.code} — {p.name}') for p in self]

# ADD this:
    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} — {rec.name}'
```

No import changes needed (`api` already imported).

**Step 4: Run test**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /mml_roq_forecast:TestRoqPortDisplayName --stop-after-init
```
Expected: PASS.

**Step 5: Commit to roq.model repo**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/roq.model"
git add mml_roq_forecast/models/roq_port.py mml_roq_forecast/tests/test_roq_port.py
git commit -m "fix(roq): replace name_get() with _compute_display_name() (Odoo 19)"
```

#### Part B: `forecast_origin_port.py` (mml.forecasting repo)

**Step 6: Write failing test**

Add to `E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting\mml_forecast_core\tests\test_forecast_origin_port.py`:

```python
@tagged('post_install', '-at_install')
class TestForecastOriginPortDisplayName(TransactionCase):
    def test_display_name_format(self):
        port = self.env['forecast.origin.port'].create({
            'code': 'cnsha', 'name': 'Shanghai', 'transit_days_nz': 22,
        })
        self.assertEqual(port.display_name, 'CNSHA — Shanghai')
```

**Step 7: Run to confirm fail**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /mml_forecast_core:TestForecastOriginPortDisplayName --stop-after-init
```

**Step 8: Fix `forecast_origin_port.py`**

In `mml.forecasting/mml_forecast_core/models/forecast_origin_port.py`, **replace** lines 39–40:

```python
# REMOVE:
    def name_get(self):
        return [(p.id, f'{p.code} — {p.name}') for p in self]

# ADD:
    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.code} — {rec.name}'
```

**Step 9: Run test**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /mml_forecast_core:TestForecastOriginPortDisplayName --stop-after-init
```
Expected: PASS.

**Step 10: Commit to mml.forecasting repo**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mml.forecasting"
git add mml_forecast_core/models/forecast_origin_port.py \
        mml_forecast_core/tests/test_forecast_origin_port.py
git commit -m "fix(forecast): replace name_get() with _compute_display_name() (Odoo 19)"
```

---

### Task 3: Migrate `read_group()` to `_read_group()` in KPI dashboard

Three calls in `kpi_dashboard.py` use the deprecated `read_group()` API. In Odoo 19, `_read_group()` is the internal API with a different signature and return type.

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\mainfreight.3pl.intergration`
**File:** `addons/stock_3pl_mainfreight/models/kpi_dashboard.py`

**Old API:** `read_group(domain, fields, groupby)` → list of dicts
**New API:** `_read_group(domain, groupby, aggregates)` → list of tuples

**Step 1: Write a test that validates KPI computation**

If `addons/stock_3pl_mainfreight/tests/test_kpi.py` does not exist, create it:

```python
from odoo.tests import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestKpiDashboard(TransactionCase):
    """Smoke tests for KPI dashboard compute methods — verify they return float values."""

    def test_ira_returns_100_when_no_stock(self):
        """IRA should be 100.0 when there is no internal stock."""
        dashboard = self.env['mf.kpi.dashboard'].new({})
        since = fields.Datetime.now() - timedelta(days=30)
        result = dashboard._compute_ira_value(since, tolerance=0.05)
        self.assertIsInstance(result, float)
        self.assertEqual(result, 100.0)

    def test_shrinkage_returns_zero_when_no_losses(self):
        """Shrinkage should be 0.0 when there is no stock and no discrepancies."""
        dashboard = self.env['mf.kpi.dashboard'].new({})
        result = dashboard._compute_shrinkage_value()
        self.assertIsInstance(result, float)
```

Add necessary imports at the top of the file:
```python
from datetime import timedelta
from odoo import fields
from odoo.tests import TransactionCase, tagged
```

**Step 2: Run test to confirm it fails (on old API)**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /stock_3pl_mainfreight:TestKpiDashboard --stop-after-init
```

**Step 3: Fix `_compute_ira_value` — calls at lines 205–209 and 215–223**

In `kpi_dashboard.py`, replace the two `read_group` calls inside `_compute_ira_value`:

```python
# BEFORE (lines 205–209):
        quant_groups = self.env['stock.quant'].read_group(
            [('location_id.usage', '=', 'internal'), ('quantity', '>', 0)],
            ['product_id'],
            ['product_id'],
        )
        total_skus = len(quant_groups)

# AFTER:
        quant_groups = self.env['stock.quant']._read_group(
            domain=[('location_id.usage', '=', 'internal'), ('quantity', '>', 0)],
            groupby=['product_id'],
            aggregates=['__count'],
        )
        total_skus = len(quant_groups)
```

```python
# BEFORE (lines 215–223):
        discrepancy_groups = self.env['mf.soh.discrepancy'].read_group(
            [
                ('state', '=', 'open'),
                ('detected_date', '>=', since),
                ('variance_pct', '>', tolerance * 100),
            ],
            ['product_id'],
            ['product_id'],
        )
        skus_with_discrepancy = len(discrepancy_groups)

# AFTER:
        discrepancy_groups = self.env['mf.soh.discrepancy']._read_group(
            domain=[
                ('state', '=', 'open'),
                ('detected_date', '>=', since),
                ('variance_pct', '>', tolerance * 100),
            ],
            groupby=['product_id'],
            aggregates=['__count'],
        )
        skus_with_discrepancy = len(discrepancy_groups)
```

**Step 4: Fix `_compute_shrinkage_value` — call at line 264–268**

`read_group` with empty `groupby=[]` returns a single group with aggregate totals. The new API returns a list of tuples where each position corresponds to one aggregate.

```python
# BEFORE (lines 264–268):
        result = self.env['stock.quant'].read_group(
            [('location_id.usage', '=', 'internal'), ('quantity', '>', 0)],
            ['quantity'],
            [],
        )
        total_stock = float(result[0]['quantity']) if result and result[0]['quantity'] else 1.0

# AFTER:
        result = self.env['stock.quant']._read_group(
            domain=[('location_id.usage', '=', 'internal'), ('quantity', '>', 0)],
            groupby=[],
            aggregates=['quantity:sum'],
        )
        # _read_group with no groupby returns [(agg_val,)] — one tuple with one element per aggregate
        total_stock = float(result[0][0]) if result and result[0][0] else 1.0
```

**Step 5: Run test**

```bash
odoo-bin --test-enable -d ODOOTEST --test-tags /stock_3pl_mainfreight:TestKpiDashboard --stop-after-init
```
Expected: PASS.

**Step 6: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration"
git add addons/stock_3pl_mainfreight/models/kpi_dashboard.py \
        addons/stock_3pl_mainfreight/tests/test_kpi.py
git commit -m "fix(3pl): migrate read_group() to _read_group() in KPI dashboard (Odoo 19)"
```

---

## Group B: External Dependencies

### Task 4: Add `requirements.txt` files

Odoo will fail to import modules at startup if `paramiko`, `numpy`, or `scipy` are missing. A `requirements.txt` at each repo root ensures deployment scripts can install them.

**Files to create:**
- `E:\ClaudeCode\projects\mml.odoo.apps\requirements.txt` (root — aggregates all)
- `E:\ClaudeCode\projects\mml.odoo.apps\mainfreight.3pl.intergration\requirements.txt`
- `E:\ClaudeCode\projects\mml.odoo.apps\roq.model\requirements.txt`

**Step 1: Create root-level `requirements.txt`**

```
# MML Odoo Apps — Python dependencies required before installing Odoo modules.
# Install with: pip install -r requirements.txt

# stock_3pl_core / stock_3pl_mainfreight — SFTP transport
paramiko>=2.10.0

# mml_roq_forecast — statistical forecasting (demand curves, safety stock)
numpy>=1.24.0
scipy>=1.10.0
```

**Step 2: Create `mainfreight.3pl.intergration/requirements.txt`**

```
# stock_3pl_core / stock_3pl_mainfreight Python dependencies.
# Install with: pip install -r requirements.txt

paramiko>=2.10.0
```

**Step 3: Create `roq.model/requirements.txt`**

```
# mml_roq_forecast Python dependencies.
# Install with: pip install -r requirements.txt

numpy>=1.24.0
scipy>=1.10.0
```

**Step 4: Update `docs/runbook/pre-production-deploy.md` to reference requirements.txt**

Find the "Pre-Installation" section in `E:\ClaudeCode\projects\mml.odoo.apps\docs\runbook\pre-production-deploy.md` and ensure it says:

```markdown
### Pre-Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This installs: `paramiko` (SFTP for 3PL/EDI), `numpy` and `scipy` (ROQ forecasting).
```

**Step 5: Commit each repo**

```bash
# Root repo
cd "E:/ClaudeCode/projects/mml.odoo.apps"
git add requirements.txt docs/runbook/pre-production-deploy.md
git commit -m "chore: add requirements.txt for external Python dependencies"

# mainfreight repo
cd "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration"
git add requirements.txt
git commit -m "chore: add requirements.txt (paramiko for SFTP transport)"

# roq.model repo
cd "E:/ClaudeCode/projects/mml.odoo.apps/roq.model"
git add requirements.txt
git commit -m "chore: add requirements.txt (numpy + scipy for forecasting)"
```

---

## Group C: i18n Scaffolding

All 15 modules need an `i18n/` directory with a stub `.pot` file so:
1. Git tracks the directory (git ignores empty dirs)
2. Odoo knows where to write translations on export
3. Future translators have the correct PO file header

**Standard `.pot` file header template:**
```
# Translation template for Odoo module.
# Copyright (C) 2026 MML Consumer Products Ltd
# This file is distributed under the same license as the module.
#
msgid ""
msgstr ""
"Project-Id-Version: \n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2026-03-05 00:00+0000\n"
"PO-Revision-Date: 2026-03-05 00:00+0000\n"
"Last-Translator: MML Consumer Products <ops@mml.co.nz>\n"
"Language-Team: \n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
```

**To regenerate with real strings after installation:**
```bash
odoo-bin --i18n-export -l en_US --modules=<module_name> --i18n-overwrite -d <db>
```

---

### Task 5: i18n — Root repo modules

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps`

**Modules:** `mml_base`, `mml_barcode_registry` (bridges are `application=False` with minimal strings — still scaffold)

**Files to create:**
- `mml_base/i18n/mml_base.pot`
- `mml_barcode_registry/i18n/mml_barcode_registry.pot`
- `mml_roq_freight/i18n/mml_roq_freight.pot`
- `mml_freight_3pl/i18n/mml_freight_3pl.pot`

**Step 1: Create all four stub `.pot` files**

For each, create the file with the header template above (replace module name in the comment).

Example for `mml_base/i18n/mml_base.pot`:
```
# Translation template for mml_base.
# Copyright (C) 2026 MML Consumer Products Ltd
# This file is distributed under the same license as the module.
#
msgid ""
msgstr ""
"Project-Id-Version: \n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2026-03-05 00:00+0000\n"
"PO-Revision-Date: 2026-03-05 00:00+0000\n"
"Last-Translator: MML Consumer Products <ops@mml.co.nz>\n"
"Language-Team: \n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
```

Repeat for the other three modules (swap module name in first comment line).

**Step 2: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps"
git add mml_base/i18n/ mml_barcode_registry/i18n/ mml_roq_freight/i18n/ mml_freight_3pl/i18n/
git commit -m "chore(i18n): scaffold i18n/ directories for root repo modules"
```

---

### Task 6: i18n — briscoes.edi

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\briscoes.edi`
**Module path:** `mml.edi/` (the Odoo module lives in this subdirectory)

**Step 1: Identify module root**

```bash
ls "E:/ClaudeCode/projects/mml.odoo.apps/briscoes.edi/"
```
Look for the directory containing `__manifest__.py`. It should be `mml.edi/`.

**Step 2: Create stub `.pot` file**

Create `E:\ClaudeCode\projects\mml.odoo.apps\briscoes.edi\mml.edi\i18n\mml_edi.pot` with:

```
# Translation template for mml_edi.
# Copyright (C) 2026 MML Consumer Products Ltd
# This file is distributed under the same license as the module.
#
msgid ""
msgstr ""
"Project-Id-Version: \n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2026-03-05 00:00+0000\n"
"PO-Revision-Date: 2026-03-05 00:00+0000\n"
"Last-Translator: MML Consumer Products <ops@mml.co.nz>\n"
"Language-Team: \n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
```

**Step 3: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/briscoes.edi"
git add mml.edi/i18n/
git commit -m "chore(i18n): scaffold i18n/ directory for mml_edi"
```

---

### Task 7: i18n — roq.model

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\roq.model`
**Module:** `mml_roq_forecast/`

**Step 1: Create stub `.pot` file**

Create `E:\ClaudeCode\projects\mml.odoo.apps\roq.model\mml_roq_forecast\i18n\mml_roq_forecast.pot`:

```
# Translation template for mml_roq_forecast.
# Copyright (C) 2026 MML Consumer Products Ltd
# This file is distributed under the same license as the module.
#
msgid ""
msgstr ""
"Project-Id-Version: \n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2026-03-05 00:00+0000\n"
"PO-Revision-Date: 2026-03-05 00:00+0000\n"
"Last-Translator: MML Consumer Products <ops@mml.co.nz>\n"
"Language-Team: \n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
```

**Step 2: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/roq.model"
git add mml_roq_forecast/i18n/
git commit -m "chore(i18n): scaffold i18n/ directory for mml_roq_forecast"
```

---

### Task 8: i18n — fowarder.intergration

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\fowarder.intergration`
**Modules:** `addons/mml_freight/`, `addons/mml_freight_dsv/`, `addons/mml_freight_knplus/`, `addons/mml_freight_mainfreight/`

**Step 1: Create four stub `.pot` files**

- `addons/mml_freight/i18n/mml_freight.pot`
- `addons/mml_freight_dsv/i18n/mml_freight_dsv.pot`
- `addons/mml_freight_knplus/i18n/mml_freight_knplus.pot`
- `addons/mml_freight_mainfreight/i18n/mml_freight_mainfreight.pot`

Each file uses the standard header template with its own module name in the comment.

**Step 2: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/fowarder.intergration"
git add addons/mml_freight/i18n/ \
        addons/mml_freight_dsv/i18n/ \
        addons/mml_freight_knplus/i18n/ \
        addons/mml_freight_mainfreight/i18n/
git commit -m "chore(i18n): scaffold i18n/ directories for freight modules"
```

---

### Task 9: i18n — mainfreight.3pl.intergration

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\mainfreight.3pl.intergration`
**Modules:** `addons/stock_3pl_core/`, `addons/stock_3pl_mainfreight/`

**Step 1: Create two stub `.pot` files**

- `addons/stock_3pl_core/i18n/stock_3pl_core.pot`
- `addons/stock_3pl_mainfreight/i18n/stock_3pl_mainfreight.pot`

Standard header template, module name swapped.

**Step 2: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration"
git add addons/stock_3pl_core/i18n/ \
        addons/stock_3pl_mainfreight/i18n/
git commit -m "chore(i18n): scaffold i18n/ directories for 3PL modules"
```

---

### Task 10: i18n — mml.forecasting

**Repo:** `E:\ClaudeCode\projects\mml.odoo.apps\mml.forecasting`
**Modules:** `mml_forecast_core/`, `mml_forecast_financial/`

**Step 1: Create two stub `.pot` files**

- `mml_forecast_core/i18n/mml_forecast_core.pot`
- `mml_forecast_financial/i18n/mml_forecast_financial.pot`

Standard header template.

**Step 2: Commit**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mml.forecasting"
git add mml_forecast_core/i18n/ \
        mml_forecast_financial/i18n/
git commit -m "chore(i18n): scaffold i18n/ directories for forecasting modules"
```

---

## Final Verification

After all tasks are complete, run this checklist:

```bash
# Verify no name_get() remains
grep -r "def name_get" \
  "E:/ClaudeCode/projects/mml.odoo.apps/roq.model" \
  "E:/ClaudeCode/projects/mml.odoo.apps/mml.forecasting"
# Expected: no output

# Verify no @api.model on create()
grep -rn "@api.model" \
  "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration/addons/stock_3pl_core/models/connector.py" \
  "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/models/connector_mf.py" \
  "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/models/connector_freightways.py"
# Expected: no output (grep -n @api.model_create_multi should show results instead)

# Verify no read_group() remains in kpi_dashboard
grep -n "\.read_group(" \
  "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration/addons/stock_3pl_mainfreight/models/kpi_dashboard.py"
# Expected: no output

# Verify requirements.txt files exist
ls "E:/ClaudeCode/projects/mml.odoo.apps/requirements.txt"
ls "E:/ClaudeCode/projects/mml.odoo.apps/mainfreight.3pl.intergration/requirements.txt"
ls "E:/ClaudeCode/projects/mml.odoo.apps/roq.model/requirements.txt"

# Verify i18n directories exist (one per module)
find "E:/ClaudeCode/projects/mml.odoo.apps" -name "*.pot" | sort
# Expected: 15 .pot files (one per module)
```
