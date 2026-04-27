# `mml_test_sprint/playwright/freight/`

Reserved namespace for Playwright artefacts owned by agent **PW-B**
(freight + 3PL UI sprint).

The actual test code lives under
`mml_test_sprint/modules/freight/test_*.py` because the existing
`mml_test_sprint` harness is a **Playwright-Python** suite — every check
is a `BaseModuleTest` subclass invoked from `runner.py`. That is the
established convention for this repo, so the freight tests slot in
alongside the existing `mml_roq_forecast` / `mml_barcode_registry`
modules without duplicating the harness.

This directory is reserved for:

- traces / videos captured under `--headed` debugging runs (gitignored)
- ad-hoc fixture JSONs / payload mocks specific to the freight stack
- any future Playwright-trace artefacts the carrier adapters need

It is intentionally kept empty in source control today — peer agents
PW-A and PW-C should not put files in here; their trees are
`mml_test_sprint/playwright/{platform,data}/` (or whatever they elect).

See `../../modules/freight/README.md` for what the suite covers and how
to run it.
