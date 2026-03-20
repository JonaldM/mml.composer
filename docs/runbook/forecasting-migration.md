# ROQ Forecasting Migration Guide

## Overview

The ROQ demand forecasting domain spans three separate codebases. This document
explains what each is, which is authoritative at each migration phase, and how
to complete the migration.

## Current State (as of 2026-03-21)

| Codebase | Location | Status | Purpose |
|----------|----------|--------|---------|
| `mml_roq_forecast` | `mml.roq.model/` | **Active — installed in prod** | Odoo 19 module; demand forecast, ROQ, 12-month plan |
| `mml_forecast_demand` | `mml.forecasting/` | In development — not yet in prod | New modular suite; more independently installable |
| `roq_forecast_job_new.py` | `mml.out.pro.fix/` | Calibration scripts — not production | Standalone scripts for parameter calibration against historical data |

## Why Three Codebases?

- `mml_roq_forecast` was the original implementation and is production.
- `mml.forecasting` separates demand (`mml_forecast_demand`) from financial
  (`mml_forecast_financial`) forecasting, making each independently installable as a
  SaaS product. Designed as the long-term target.
- `mml.out.pro.fix` contains one-off scripts used to calibrate ROQ constants against
  historical order data. Their default constants differ from the Odoo module defaults
  and should be treated as reference only, not authoritative.

## Canonical Default Constants

The new `mml_forecast_demand` module is the authoritative source. Use these values
everywhere:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Lookback weeks | 156 | 3 years of weekly demand history |
| SMA window weeks | 52 | Full year rolling average |
| LCL threshold | 50% container utilisation | Below 50% of smallest container → LCL |
| Safety stock service level | A=97%, B=95%, C=90%, D=0% | Z-scores: 1.881, 1.645, 1.282, 0 |
| ABC dampener | 4 runs | Tier must be stable 4 consecutive runs before taking effect |
| Max padding weeks cover | 26 weeks | A-tier padding ceiling |

`mml.out.pro.fix` scripts use different values — do not copy their constants into production.

## Migration Phases

### Phase 1: Stabilise (Current)
- `mml_roq_forecast` is primary and installed in prod
- `mml_forecast_demand` in development and testing in dev DB (MML_EDI_Compat)
- No changes to prod until Phase 2

### Phase 2: Parallel Run
- Install `mml_forecast_demand` alongside `mml_roq_forecast` in prod DB
- Run both for a minimum of one full 12-month plan cycle (4 weeks minimum)
- Compare outputs — document discrepancies in the project tracker

### Phase 3: Cutover
- Disable cron on `mml_roq_forecast` (set `active = False` on the weekly cron)
- `mml_forecast_demand` cron becomes primary
- Update `mml_roq_freight` bridge if event names changed

### Phase 4: Cleanup
- Uninstall `mml_roq_forecast` from prod (after confirming no regressions over 2 months)
- Archive `mml.roq.model/` directory
- Delete `mml.out.pro.fix/` calibration scripts (keep a git tag for reference)
- Remove any compatibility shims added during Phase 3

## Bridge Module Impact

`mml_roq_freight` bridges ROQ ↔ Freight via `mml.event`. When cutting over:

1. Check whether `mml_forecast_demand` emits `roq.shipment_group.confirmed` with the
   same payload as `mml_roq_forecast`
2. If event names or payloads changed, update `mml_roq_freight` bridge subscriptions
3. Run the E2E integration test after cutover:
   ```bash
   python odoo-bin --test-enable -u mml_roq_freight,mml_freight_3pl \
       -d <db> --test-tags mml_roq_freight:TestROQFreight3PLE2E
   ```
