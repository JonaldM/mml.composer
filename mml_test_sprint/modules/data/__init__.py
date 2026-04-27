"""Data, forecasting, and barcode module Playwright tests (PW-C scope).

Modules covered:
  - mml_edi (EDI engine: Briscoes parser, FTP poll, ASN gen)
  - mml_barcode_registry (GS1 barcode lifecycle) — extension
  - mml_forecast_core (FX rates, ports, customer terms)
  - mml_forecast_financial (P&L + cashflow)
  - mml_roq_forecast (demand forecast + ROQ engine) — extension

These tests are additive; they import (and re-use) the shared harness
defined in mml_test_sprint/{browser,checks,base_module}.py.
"""
