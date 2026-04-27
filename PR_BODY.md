# ci: GitHub Actions baseline for pure-Python tests

PR URL: https://github.com/JonaldM/mml.composer/compare/master...claude-sprint/github-actions-ci?expand=1

## Summary
Adds a minimal GitHub Actions workflow that runs the pure-Python (non-Odoo) test suite on every PR against `master` and on pushes to `master`. This is a baseline regression gate — not a deploy pipeline.

## What it does
- Triggers on `pull_request` and `push` to `master`.
- Checks out with `submodules: recursive` so the future nested-repo restructure (P1) will pick up sub-repos automatically once they become submodules.
- Sets up Python 3.11 with pip cache.
- Installs `requirements.txt` plus `pytest`.
- Runs `pytest -m "not odoo_integration" -q mml_base mml_roq_freight mml_freight_3pl`.

## Why scoped to specific dirs
The nested-repo placeholder directories (`mml.3pl.intergration`, `mml.fowarder.intergration`, `mml.forecasting`, `mml.roq.model`) are currently empty in the parent repo — they're tracked as separate repositories and not yet wired up as git submodules. Running pytest from the repo root would either skip them silently (today) or fail collection (once content is restored without proper packaging). Scoping to the three top-level modules that contain working pure-Python tests (`mml_base`, `mml_roq_freight`, `mml_freight_3pl`) keeps the gate green and meaningful today.

Once the P1 nested-repos restructure lands and these directories become real submodules, the `submodules: recursive` checkout flag will pull them in automatically and the pytest invocation can be widened (or replaced with a bare `pytest`).

## Test plan
- [ ] Open the PR and confirm the workflow runs.
- [ ] Confirm `Test / test` job passes (or matches the local `pytest -m "not odoo_integration" -q mml_base mml_roq_freight mml_freight_3pl` result).
- [ ] Verify required-status-check is enabled in branch protection settings (manual repo admin step).
