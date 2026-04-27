# Freight + 3PL Playwright UI Tests

This sprint adds Playwright UI coverage for the MML Freight orchestrator,
its three carrier adapters, and the Mainfreight 3PL implementation. The
tests are wired into the existing `mml_test_sprint` harness — same
`BaseModuleTest` subclass shape, same browser session helpers, same
HTML report.

## Modules covered

| Module | Smoke | Spec | Workflow |
|--------|-------|------|----------|
| `mml_freight` (orchestrator) | Active Shipments + tender list + booking list load cleanly | Tender form: `incoterm_id`, `carrier_id`/`quote_line_ids`, `state` statusbar, `origin_country_id`, `dest_country_id`. Booking form: `carrier_id`, `state`, `carrier_tracking_url`, `transport_mode` | Tender form has at least one workflow header button (`action_request_quotes`/`action_book`/`action_cancel`) |
| `mml_freight_dsv` | Freight Carriers list loads | DSV carrier form exposes the DSV configuration group with `x_dsv_environment` | SKIP — exercising real DSV API would require live OAuth + APIM keys |
| `mml_freight_knplus` | Pre-seeded inactive K+N row visible on `delivery.carrier` list (validates M17 default-inactive seed) | K+N carrier form shows K+N config group + `x_knplus_*` fields, `active=False` by default | **Toggling `active=True` raises a `UserError` with the gate copy referencing `MML_KNPLUS_ENABLE` — this is the M17 invariant.** |
| `mml_freight_mainfreight` | Freight Carriers list loads | Mainfreight carrier form shows the Mainfreight Configuration group with `x_mf_environment`, `x_mf_customer_code`, `x_mf_warehouse_code`, `x_mf_api_key` | SKIP — Mainfreight A&O has no quote/booking API |
| `stock_3pl_core` | 3PL Connectors list + 3PL Message Queue list load cleanly with the state + retry_count columns | `3pl.message` form has `state` widget, `retry_count`, `last_error`, `connector_id`, `document_type` fields | Dead-letter filter action shows only `state=dead` rows |
| `stock_3pl_mainfreight` | 3PL KPI dashboard, Order Pipeline list, Exception Queue list all load | Warehouse form exposes `x_mf_enabled` (and `x_mf_latitude`/`x_mf_longitude` when enabled) | SKIP — exercising real Mainfreight API requires live REST/SFTP creds |

## How to run

The harness is reachable as a Python module — the new CLI flags push the
target into `os.environ` *before* `config.py` is imported, so a single
invocation can hit any environment without editing source.

```sh
# All modules (including platform + data work)
python -m mml_test_sprint

# Freight + 3PL only against the Hetzner pre-prod replica
python -m mml_test_sprint \
  --module freight \
  --target http://100.94.135.90:8090 \
  --user jono@mml.co.nz \
  --password Test123 \
  --database MML_19_prod_test
```

`--no-installed-check` skips the SSH module-existence query — useful when
the target is reachable over Tailscale but SSH isn't.

`--headed` runs Chromium with a visible window (handy when locally
debugging a failing spec).

The HTML report is written to `mml_test_sprint/test_results/<date>/report.html`,
the same place as before.

## What is NOT tested

These checks exist to catch UI/regression breakage. Anything that needs a
real third-party response is intentionally skipped — wire those into
contract/integration suites with the carrier-side stubs already used in
`mml.fowarder.intergration/addons/*/tests/`:

- **Real carrier quote/booking calls** — DSV, K+N, Mainfreight all skip.
  These require live OAuth tokens, APIM subscription keys, or REST
  credentials that should never live in a UI test runner.
- **Webhook receipts** (`/dsv/webhook/...`, `/mf/webhook/...`) — secured
  by HMAC; fired by carrier servers, not the UI. Covered by Python unit
  tests in each adapter module.
- **Tender → quote → book → ship → land-cost full lifecycle** — the
  state machine spans pessimistic locks and adapter calls. Pure-Python
  tests in `mml_freight/tests/test_tender_lifecycle.py` cover the
  business logic; no UI-level value in re-running it.
- **3PL outbound dispatch / SOH reconciliation** — depends on the
  Mainfreight REST API and the SFTP poll. Covered by
  `stock_3pl_mainfreight/tests/test_*.py` against canned fixtures.
- **Freight tender wizard from a PO** — the Freight orchestrator is
  triggered automatically on `purchase.order.action_confirm` for
  EXW/FCA/FOB/FAS incoterms; there is no user-facing wizard to drive
  via UI. The tender list smoke test confirms records show up; the
  workflow check confirms the button bar is intact.

If a check is `SKIP` because a record-type is missing on the target
instance (no DSV carrier seeded, no `freight.tender` records yet), the
report shows it greyed-out — that's a data gap, not a code regression.
