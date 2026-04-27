# PW-C — Data, Forecasting, and Barcode Module Coverage

This package extends `mml_test_sprint` with Playwright UI coverage for MML's
data, forecasting, and barcode modules. It is **additive** — the existing
`modules/mml_roq_forecast.py` and `modules/mml_barcode_registry.py` files
are left untouched and run alongside the extensions below.

## Modules and Coverage

### `mml_edi` (EDI Engine)
- **Smoke:** EDI Dashboard, Pending Review, EDI Sales Orders, Logs, and
  Trading Partners list views all render without JS errors.
- **Spec:** Trading-partner form has the `pricelist_id`, `edi_format`,
  `environment`, and `auto_confirm_clean` fields demanded by the M1 design.
- **Workflow:** EDI Dashboard renders either rows or the empty-state panel.
  M1 GST gate observation is captured: current code logs an ex-GST advisory
  but does not hard-reject GST-inclusive pricelists, so this is recorded as
  a `WARN` until the gate is upgraded to a `UserError`.

### `mml_barcode_registry` (extension)
- **Smoke:** Dashboard, Status Breakdown graph, Prefix list, Brand list.
- **Spec:** Allocation form fields (`gtin_13`, `product_id`, `registry_id`,
  status statusbar). Search view exposes Active/Dormant/Discontinued filters.
- **Workflow:** Re-tests the prior `2026-03-11` FINDINGS access WARN —
  verifies the Allocate-Barcode button surfaces on the product form, and
  Set-Dormant button surfaces on active allocations.

### `mml_forecast_core`
- **Smoke:** Forecasting app menu, Financial Forecasts list, Origin Ports list.
- **Spec:** Forecast Config form has `name`, `date_start`, `horizon_months`,
  `scenario`, state statusbar. Notebook tabs: FX Rates, Payment Terms,
  Supplier Payment Terms. Origin Port list columns.
- **Workflow:** Origin Port row inline-edit activates the editor.

### `mml_forecast_financial`
- **Smoke:** P&L Summary, Cashflow, Balance Sheet, Variance views all load.
- **Spec:** Generate Forecast button visible on draft forecasts. KPI strip
  (Revenue, EBITDA, Ending Cash, Cash Low) renders on generated forecasts.
- **Workflow:** Generate Forecast clickable on a draft without crashing the UI.
  M2 GST gate observation: wizard logs ex-GST assumption only — captured
  as `WARN` for the same reason as the M1 case.

### `mml_roq_forecast` (extension — re-tests prior WARNs)
- **Workflow 1:** "Confirm & Create Tender" button on draft Shipment Groups
  (prior result: `SKIP` — no draft SG existed). Iterates kanban + list views.
- **Workflow 2:** Calendar shows shipment events within 6 months of the
  default landing (prior result: `WARN` — June 2026 events were missing
  before the `2026-03-11` `target_delivery_date` backfill).

## How to Run

The harness is invoked from the repo root and uses Python + Playwright:

```bash
cd E:/ClaudeCode/projects/mml.odoo
python -m mml_test_sprint.runner
```

Output is written to `mml_test_sprint/test_results/<YYYY-MM-DD>/report.html`.
The runner queries the Odoo server via SSH to determine which modules are
installed and skips any that are not. Tests record `PASS`/`FAIL`/`WARN`/`SKIP`
per check; the run exits non-zero if any check is `FAIL`.

The data/ tests are wired into `runner.py` alongside the existing
RoqForecast / Barcode tests, so a single invocation runs everything.

## What Is NOT Tested Here

These tests are pure UI smoke + spec + light workflow. They deliberately
do not duplicate logic already proven by pure-Python and Odoo-integration
unit tests:

- **EDI:** Actual ingest pipeline (Briscoes EDIFACT parser, FTP poll,
  ASN/DESADV generation) is covered by `mml_edi/tests/` — pure-Python
  parser tests + Odoo integration tests for `edi.processor`.
- **ROQ math:** ABC tier classification, SMA/EWMA forecast, (s,S) ROQ
  calculation, container fitting are covered by
  `mml.roq.model/mml_roq_forecast/tests/` (pure Python on services).
- **Forecast pipeline:** The full revenue/COGS/P&L/cashflow generation
  pipeline is exercised by `mml.forecasting/tests/test_forecast_e2e.py`
  and the Odoo integration tests in `mml_forecast_financial/tests/`.
- **Barcode GS1 math:** MOD-10 check digits and GTIN-13/14 build are
  covered by `mml.barcodes/mml_barcode_registry/tests/test_gs1.py`
  (pure Python).
- **Negative-path GST gates:** M1 (mml_edi) and M2
  (mml_forecast_financial) currently emit *warnings* rather than hard
  validation errors when a GST-inclusive pricelist is present, so a
  reliable negative-path UI test is not yet possible. These are
  captured as `WARN` so the gap shows up in the report.
