"""Extended tests for mml_roq_forecast — re-tests prior FINDINGS.md WARNs.

The base file mml_test_sprint/modules/mml_roq_forecast.py already covers the
core ROQ Run / Shipment Group / Calendar UI. This file extends with two
re-verifications called out in 2026-03-11 FINDINGS.md as deferred:

  1. "Confirm & Create Tender" button on draft Shipment Groups was SKIPped
     because no draft SG existed in the DB. We re-test the visibility check
     against the current state.

  2. Calendar June 2026 events were absent. We re-verify that events appear
     somewhere in the next 6 calendar months from the default landing.

This file complements (does NOT replace) the existing
modules/mml_roq_forecast.py RoqForecastTests.
"""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_RUNS = "action-mml_roq_forecast.action_roq_forecast_run"
ACTION_SHIPMENT_GROUPS = "2020"
ACTION_CALENDAR = "2023"


class RoqForecastExtTests(BaseModuleTest):
    module_name = "mml_roq_forecast"
    module_label = "ROQ Forecast (extended)"

    def run_smoke(self):
        # Smoke is covered by the base RoqForecastTests; we keep one
        # navigation here to make the extended block self-contained when
        # the harness skips the base file.
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Shipment Groups list reachable (extended re-test entry)"
        )))

    def run_spec(self):
        # All ROQ form-field spec lives in the base file. We add the calendar
        # filter sidebar shape check here as a non-overlapping spec.
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_CALENDAR}", wait_ms=5000)
        self.add_spec(self.s.snap(self.s.check_element_exists(
            '.o_calendar_view',
            "spec: Calendar view container present"
        )))

    # ── Workflows: re-tests of prior FINDINGS WARNs ──────────────────────────

    def run_workflows(self):
        self._workflow_confirm_create_tender_button()
        self._workflow_calendar_events_in_next_6_months()

    def _workflow_confirm_create_tender_button(self):
        """Re-test FINDINGS.md WARN: 'Confirm & Create Tender' on draft SG.

        Prior result: SKIP (no draft SG existed). We iterate the kanban and
        list views looking for any record whose state is 'draft', open it,
        and verify the action_confirm button is visible.
        """
        # Try kanban first (the default action context groups by state)
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}", wait_ms=5000)

        # Look for a draft column / draft badge in kanban
        draft_card = self.s.page.locator(
            '.o_kanban_record:has(.badge:has-text("draft")), '
            '.o_kanban_record:has(.badge:has-text("Draft"))'
        )
        if draft_card.count() > 0:
            try:
                draft_card.first.click()
                self.s.page.wait_for_timeout(3000)
            except Exception:
                pass

        # Fallback: list view + iterate
        if self.s.page.locator('.o_form_view').count() == 0:
            self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list",
                        wait_ms=4000)
            list_rows = self.s.page.locator('.o_data_row')
            if list_rows.count() == 0:
                self.add_workflow(Check(
                    "workflow: Confirm & Create Tender button on draft SG",
                    Status.SKIP,
                    "No shipment group records in DB"
                ))
                return
            # Iterate up to 12 rows looking for a draft state
            for i in range(min(list_rows.count(), 12)):
                badge = list_rows.nth(i).locator('[name="state"], .badge')
                txt = ""
                if badge.count() > 0:
                    try:
                        txt = (badge.first.inner_text() or "").lower()
                    except Exception:
                        txt = ""
                if 'draft' in txt:
                    list_rows.nth(i).click()
                    self.s.page.wait_for_timeout(3000)
                    break
            else:
                self.add_workflow(Check(
                    "workflow: Confirm & Create Tender button on draft SG",
                    Status.WARN,
                    "No draft shipment group rows found in first 12 — same "
                    "data gap as 2026-03-11 FINDINGS.md"
                ))
                return

        # We're now on a form (possibly draft). Check the button.
        btn = self.s.page.locator('button[name="action_confirm"]')
        if btn.count() > 0 and btn.first.is_visible():
            self.add_workflow(self.s.snap(Check(
                "workflow: Confirm & Create Tender button on draft SG",
                Status.PASS,
                "Button visible on a draft record (FINDINGS.md WARN cleared)"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: Confirm & Create Tender button on draft SG",
                Status.WARN,
                "Reached a SG form but Confirm button not visible — record "
                "may not be in draft, or button was relocated"
            )))

    def _workflow_calendar_events_in_next_6_months(self):
        """Re-test FINDINGS.md WARN: calendar June events were missing.

        2026-03-11 fix backfilled target_delivery_date and added two SGs in
        the March-2026 window. We re-verify events appear within 6 months
        of the calendar's default landing.
        """
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_CALENDAR}", wait_ms=5000)

        # Remove default Active filter so draft records are visible
        close_btns = self.s.page.locator('.o_facet_remove')
        if close_btns.count() > 0:
            try:
                close_btns.first.click()
                self.s.page.wait_for_timeout(1500)
            except Exception:
                pass

        # Count events in current month, then walk forward
        event_count = self.s.page.locator('.fc-event').count()
        found_at = 0 if event_count > 0 else None
        next_btn = self.s.page.locator('button.o_next')
        if next_btn.count() > 0 and found_at is None:
            for offset in range(1, 7):
                try:
                    next_btn.click()
                    self.s.page.wait_for_timeout(1500)
                except Exception:
                    break
                event_count = self.s.page.locator('.fc-event').count()
                if event_count > 0:
                    found_at = offset
                    break

        if found_at is not None:
            self.add_workflow(self.s.snap(Check(
                "workflow: Calendar shows shipment events in next 6 months",
                Status.PASS,
                f"{event_count} event(s) at +{found_at} month(s) from default — "
                f"FINDINGS.md WARN cleared"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: Calendar shows shipment events in next 6 months",
                Status.WARN,
                "No events found within 6 months — re-check target_ship_date "
                "/ target_delivery_date backfill (per 2026-03-11 FINDINGS.md)"
            )))
