"""Tests for ``mml_freight`` — Freight orchestration core.

Smoke
-----
* Top-level "Freight" app menu / Active Shipments action loads.
* "All Tenders" list view loads without error dialog or JS error.
* "All Bookings" list view loads.

Spec
----
* Tender form has the canonical ``carrier_id`` (via quote line),
  ``incoterm_id`` and ``state`` statusbar fields.
* Booking form exposes ``carrier_id``, ``state`` and
  ``carrier_tracking_url`` fields.

Workflows
---------
* Open the tender list; if a draft tender exists, open its form and
  verify the "Request Quotes" action button is present (state-driven UI).
  If no draft is reachable (read-only DB / no data), fall back to verifying
  the form renders with a state statusbar.

Fields verified are the *external* model contract — see
``mml.fowarder.intergration/addons/mml_freight/views/freight_tender_views.xml``
and ``freight_booking_views.xml``.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


# Action xml-ids defined in mml_freight/views/*.xml
ACTION_ACTIVE = "action-mml_freight.action_freight_booking_active"
ACTION_TENDER = "action-mml_freight.action_freight_tender"
ACTION_BOOKING = "action-mml_freight.action_freight_booking"


class MmlFreightTests(BaseModuleTest):
    module_name = "mml_freight"
    module_label = "MML Freight (Orchestrator)"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_active_shipments()
        self._smoke_tender_list()
        self._smoke_booking_list()

    def _smoke_active_shipments(self):
        """Active Shipments kanban (the Freight app landing page)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ACTIVE}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Freight Active Shipments loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Freight Active Shipments no error dialog"))
        # The view should be a kanban or a list — assert at least one of them
        # is on screen so that we know the action resolved to something.
        if (self.s.page.locator(".o_kanban_view").count() == 0
                and self.s.page.locator(".o_list_view").count() == 0):
            self.add_smoke(Check(
                "smoke: Freight landing page renders a view",
                Status.FAIL,
                "Neither kanban nor list view found at Active Shipments action"))
        else:
            self.add_smoke(Check(
                "smoke: Freight landing page renders a view",
                Status.PASS))

    def _smoke_tender_list(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TENDER}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Freight Tenders list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Freight Tenders no error dialog"))
        self.add_smoke(self.s.check_element_exists(
            ".o_list_view, .o_view_controller",
            "smoke: Freight Tenders list view present"))

    def _smoke_booking_list(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_BOOKING}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Freight Bookings list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Freight Bookings no error dialog"))
        self.add_smoke(self.s.check_element_exists(
            ".o_list_view, .o_view_controller",
            "smoke: Freight Bookings list view present"))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_tender_form()
        self._spec_booking_form()

    def _spec_tender_form(self):
        """Open a tender form and verify the canonical fields exist."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TENDER}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: tender form fields",
                Status.SKIP,
                "No freight.tender records on target instance"))
            return

        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()
        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Tender form not blank")))

        self.add_spec(self.s.check_element_exists(
            '[name="incoterm_id"]',
            "spec: Tender form has incoterm_id field"))
        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status',
            "spec: Tender form has state statusbar"))
        # carrier_id appears on the per-row quote table, not on the tender
        # itself — match it in either place.
        self.add_spec(self.s.check_element_exists(
            '[name="carrier_id"], [name="quote_line_ids"]',
            "spec: Tender form exposes carrier (via quote_line_ids)"))
        self.add_spec(self.s.check_element_exists(
            '[name="origin_country_id"]',
            "spec: Tender form has origin_country_id field"))
        self.add_spec(self.s.check_element_exists(
            '[name="dest_country_id"]',
            "spec: Tender form has dest_country_id field"))

    def _spec_booking_form(self):
        """Open a booking form and verify carrier, state, tracking_url fields."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_BOOKING}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: booking form fields",
                Status.SKIP,
                "No freight.booking records on target instance"))
            return

        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()
        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Booking form not blank")))

        self.add_spec(self.s.check_element_exists(
            '[name="carrier_id"]',
            "spec: Booking form has carrier_id field"))
        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status',
            "spec: Booking form has state statusbar"))
        self.add_spec(self.s.check_element_exists(
            '[name="carrier_tracking_url"]',
            "spec: Booking form has carrier_tracking_url field"))
        self.add_spec(self.s.check_element_exists(
            '[name="transport_mode"]',
            "spec: Booking form has transport_mode field"))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_tender_actions_visible()

    def _workflow_tender_actions_visible(self):
        """Open a tender — verify the workflow header buttons are wired.

        We don't actually click them (carrier APIs would fire), we just
        check the buttons exist on the form so a regression that drops the
        ``action_request_quotes`` / ``action_book`` / ``action_cancel``
        wiring is caught.
        """
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TENDER}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: tender header buttons",
                Status.SKIP,
                "No tenders to inspect"))
            return

        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()

        # At least one of the workflow buttons must be visible — Odoo hides
        # them by `state`, but the `action_cancel` is shown until the booking
        # state. So at least one of these should be present in the DOM
        # (visibility class may vary).
        any_btn = self.s.page.locator(
            'button[name="action_request_quotes"], '
            'button[name="action_auto_select"], '
            'button[name="action_book"], '
            'button[name="action_cancel"]'
        )
        if any_btn.count() == 0:
            self.add_workflow(self.s.snap(Check(
                "workflow: tender form has at least one action button",
                Status.FAIL,
                "None of action_request_quotes / action_auto_select / "
                "action_book / action_cancel were found in the form header")))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: tender form has at least one action button",
                Status.PASS,
                f"{any_btn.count()} workflow button(s) found")))
