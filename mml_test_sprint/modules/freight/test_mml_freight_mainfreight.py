"""Tests for ``mml_freight_mainfreight`` — Mainfreight A&O carrier adapter.

Smoke
-----
* Freight Carriers list (auto-tender carriers) loads.

Spec
----
* Open a Mainfreight A&O delivery.carrier (if seeded) and verify the
  Mainfreight Configuration group is rendered with the
  ``x_mf_environment`` / ``x_mf_customer_code`` / ``x_mf_warehouse_code``
  / ``x_mf_api_key`` fields.

Mainfreight A&O has **no quote/booking API** — bookings are arranged via
the Mainchain portal. There is therefore no UI workflow to exercise here
beyond config-form validation.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_FREIGHT_CARRIER = "action-mml_freight.action_freight_carrier"
ACTION_DELIVERY_CARRIER = "action-delivery.action_delivery_carrier_form"


class MmlFreightMainfreightTests(BaseModuleTest):
    module_name = "mml_freight_mainfreight"
    module_label = "MML Freight — Mainfreight A&O Adapter"

    def run_smoke(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FREIGHT_CARRIER}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Freight Carriers list loads (Mainfreight uses it)")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Freight Carriers no error dialog"))

    def run_spec(self):
        # Mainfreight rows may have auto_tender=False (no booking API).
        # Use the raw delivery.carrier action so they appear regardless.
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DELIVERY_CARRIER}?view_type=list",
                    wait_ms=4000)

        # Drop the Active facet so inactive rows are visible.
        facet_x = self.s.page.locator('.o_facet_remove')
        if facet_x.count() > 0:
            try:
                facet_x.first.click()
                self.s.page.wait_for_timeout(1500)
            except Exception:
                pass

        rows = self.s.page.locator(".o_data_row")
        opened = False
        for i in range(min(rows.count(), 16)):
            row = rows.nth(i)
            text = row.inner_text() if row.count() else ""
            if "Mainfreight" in text or "MAINFREIGHT" in text.upper():
                row.click()
                self.s.page.wait_for_timeout(3500)
                self.s.scroll_to_top()
                opened = True
                break

        if not opened:
            self.add_spec(Check(
                "spec: Mainfreight provider config form",
                Status.SKIP,
                "No Mainfreight delivery.carrier on target instance"))
            return

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Mainfreight carrier form not blank")))
        self.add_spec(self.s.check_element_exists(
            '[name="mf_config"], [name="x_mf_environment"]',
            "spec: Mainfreight carrier exposes Mainfreight Configuration group"))
        self.add_spec(self.s.check_element_exists(
            '[name="x_mf_customer_code"]',
            "spec: Mainfreight carrier has x_mf_customer_code field"))
        self.add_spec(self.s.check_element_exists(
            '[name="x_mf_warehouse_code"]',
            "spec: Mainfreight carrier has x_mf_warehouse_code field"))
        self.add_spec(self.s.check_element_exists(
            '[name="x_mf_api_key"]',
            "spec: Mainfreight carrier has x_mf_api_key field"))

    def run_workflows(self):
        self.add_workflow(Check(
            "workflow: Mainfreight A&O booking workflow",
            Status.SKIP,
            "Skipped — Mainfreight A&O has no quote/booking API; "
            "ops use Mainchain portal"))
