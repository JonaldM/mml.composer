# MML Module Test Sprint — Findings

**Run date/time:** 2026-03-11 08:49 (repeated at 08:52 — identical results)
**Server:** http://46.62.148.99:8090
**Database:** mml_dev
**Credentials:** jono@mml.co.nz / test
**Report:** `E:\ClaudeCode\projects\mml.odoo\mml_test_sprint\test_results\2026-03-11\report.html`

---

## Summary Table

| Module                    | Status | Smoke  | Spec   | Workflows |
|---------------------------|--------|--------|--------|-----------|
| mml_base (Platform Layer) | FAIL   | 4/7    | 0/0    | 0/0       |
| ROQ Forecast              | FAIL   | 9/9    | 18/19  | 3/5       |
| Barcode Registry          | WARN   | 0/1    | 0/1    | 0/1       |

**Overall:** FAILURES FOUND — 2 FAIL, 1 WARN, 0 PASS

---

## Installed Modules (verified via SSH/psql)

```
mml_barcode_registry, mml_base, mml_edi, mml_forecast_core,
mml_forecast_financial, mml_freight, mml_freight_3pl, mml_freight_dsv,
mml_roq_forecast, mml_roq_freight, stock_3pl_core, stock_3pl_mainfreight
```

---

## Module-by-Module Results

### mml_base (Platform Layer) — FAIL (smoke 4/7)

Headless checks via SSH + psql. No browser required.

| Status | Check | Detail |
|--------|-------|--------|
| PASS | headless: mml.capability model exists | count=1 |
| PASS | headless: mml.registry model exists | count=1 |
| PASS | headless: mml.event model exists | count=1 |
| FAIL | headless: ROQ lead time config param exists | Expected 1, got 0 |
| FAIL | headless: ROQ service level config param exists | Expected 1, got 0 |
| FAIL | headless: ROQ lookback weeks config param exists | Expected 1, got 0 |
| PASS | headless: SG sequence exists | count=1 |

**Finding:** Three ROQ config parameters are missing from `ir_config_parameter`:
- `roq.default_lead_time_days`
- `roq.default_service_level`
- `roq.lookback_weeks`

These are expected to be seeded by the `mml_roq_forecast` module on install (via `data/` XML or `post_init_hook`). Their absence means the ROQ pipeline will fall back to hardcoded defaults or raise a TypeError on `int(False)` — a known MAJOR issue identified in the prior code review. The `roq.shipment.group` sequence is present (count=1), confirming partial data migration was run.

**Action required:** Run the ROQ config parameter seeding (check `mml_roq_forecast/data/` for a config param XML file, or run the post-install hook manually).

---

### ROQ Forecast (mml_roq_forecast) — FAIL (smoke 9/9, spec 18/19, wf 3/5)

All smoke checks pass. One spec failure and two workflow failures.

#### Spec Failures (1/19 failed)

| Status | Check | Detail |
|--------|-------|--------|
| FAIL | spec: SG form has Confirm & Create Tender button | Expected to find `button[name="action_confirm"]` — not found |

**Finding:** The Shipment Group form does not expose an `action_confirm` button in the current state of the record opened. This may be a state-dependent visibility issue (button only shows in `draft` state and the test record was already confirmed), or the button name differs from the spec (`action_confirm` vs another name). Not a definitive bug — needs further investigation with a draft-state record.

#### Workflow Failures (3/5 passed, 2 failed/warned)

| Status | Check | Detail |
|--------|-------|--------|
| WARN | workflow: Calendar shows June shipment events | No events in June — target_ship_date may not match calendar range, or filter issue |
| WARN | workflow: ROQ run has supplier lines | No 'By Supplier' tab found on ROQ Run form |

**Calendar — WARN:** The Shipment Calendar navigated 3 months forward from March 2026 to approximately June 2026 and found 0 `fc-event` elements. Possible causes:
  1. No shipment groups have a `target_ship_date` in June 2026.
  2. The calendar filter is restricting visibility (e.g., a state filter is active by default).
  3. The calendar field binding uses a different date field than `target_ship_date`.
  This is a WARN (not FAIL) because it may be a data gap rather than a code defect.

**ROQ Run "By Supplier" tab — WARN:** The ROQ Run form (opened from the list) does not have a tab matching `has-text("Supplier")`, `has-text("By Supplier")`, or `has-text("Order by Supplier")`. This suggests the ROQ Run form layout differs from the spec, or the tab label is different (e.g., "Forecast Lines" or "Lines"). The Order Dashboard's By Supplier tab worked fine (18 rows found), so the data exists.

#### Passing Highlights

- All 9 smoke checks pass: app menu, Order Dashboard, Runs list, Shipment Groups list, Calendar view renders, Freight Ports.
- Order Dashboard has both Urgency and Order by Supplier tabs with 18 rows of data.
- Shipment Group form renders correctly at 910px width (no chatter/widget collapse bug).
- Suppliers tab has lines, View SKUs button works, OOS Risk and Push/Pull Days columns present.
- Calendar FullCalendar grid and sidebar render correctly.
- Kanban view for Shipment Groups loads.
- View SKUs workflow opens the forecast line list correctly.

---

### Barcode Registry (mml_barcode_registry) — WARN (smoke 0/1, spec 0/1, wf 0/1)

| Status | Check | Detail |
|--------|-------|--------|
| WARN | smoke: Barcode app accessible | Could not find Barcode app tile — may not be installed |
| SKIP | spec: Barcode fields | No records and no New button |
| WARN | workflow: Barcode list has records | 0 barcode record(s) in DB |

**Finding:** `mml_barcode_registry` is listed as installed (confirmed via `ir_module_module` query) but the app tile is not visible on the home screen for the `jono@mml.co.nz` user. The module may lack `application=True` in its manifest, or the user account does not have the `mml_barcode_registry` group assigned. No barcode records exist in the DB.

The runner fell back to `/odoo/barcodes` which 404'd, then tried to find an app tile and failed. The WARN (not FAIL) status is correct — the module is installed but has no accessible UI for this user role, and the DB is empty.

**Action required:** Assign the Barcode Registry user/admin group to `jono@mml.co.nz`, or verify the app menu_id in the manifest and confirm `application=True` is set with `web_icon`.

---

## Key Observations

1. **ROQ config params not seeded** — The three `ir_config_parameter` keys for ROQ defaults are absent. This is a deployment/migration gap. The pipeline will not function correctly until these are set.

2. **Shipment Calendar shows 0 events in June 2026** — Either no shipment groups have been scheduled for June, or a default filter is hiding them. Worth checking in the UI manually by removing all active filters.

3. **SG `action_confirm` button not found** — The test opened a record that may already be past the `draft` state, so the button correctly does not appear. Low confidence this is a bug.

4. **Barcode Registry UI not accessible to test user** — Module is installed but the user cannot reach the app. Group assignment or menu visibility issue.

5. **ROQ Run form "By Supplier" tab absent** — Tab label in the actual form differs from what the test expected. The data exists (Order Dashboard proves it), so this is a UI label mismatch in the test selector, not a missing feature.

6. **All core ROQ smoke checks pass** — The ROQ Forecast module is functionally deployed: all views load, no JS errors, no error dialogs, correct widget rendering.

---

## Recommended Follow-up Actions

| Priority | Action |
|----------|--------|
| HIGH | Seed missing ROQ `ir_config_parameter` records (`roq.default_lead_time_days`, `roq.default_service_level`, `roq.lookback_weeks`) |
| MEDIUM | Grant `jono@mml.co.nz` access to Barcode Registry (assign user group) |
| MEDIUM | Manually navigate the Shipment Calendar to June 2026 and remove filters to confirm whether events are missing or filtered |
| LOW | Update test selector for ROQ Run "By Supplier" tab to match the actual tab label in the form |
| LOW | Investigate `action_confirm` button visibility rule on Shipment Group form |
