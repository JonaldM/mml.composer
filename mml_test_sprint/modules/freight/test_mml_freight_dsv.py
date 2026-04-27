"""Tests for ``mml_freight_dsv`` — DSV Generic + DSV XPress carrier adapters.

Smoke
-----
* Freight Carriers list (from mml_freight) is reachable.

Spec
----
* The ``delivery.carrier`` form, when a DSV carrier is selected,
  surfaces the ``DSV Configuration`` group injected by
  ``mml_freight_dsv/views/freight_carrier_dsv_views.xml``.
  We check by navigating to the Freight Carriers list, opening any
  existing DSV record, and asserting the dsv_config group exists.

If no DSV carrier is pre-seeded, the spec check is SKIPped — this
avoids polluting the test with delivery_type writes that would side-effect
the database.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_FREIGHT_CARRIER = "action-mml_freight.action_freight_carrier"


class MmlFreightDsvTests(BaseModuleTest):
    module_name = "mml_freight_dsv"
    module_label = "MML Freight — DSV Adapter"

    def run_smoke(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FREIGHT_CARRIER}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Freight Carriers list loads (DSV uses it)")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Freight Carriers no error dialog"))
        self.add_smoke(self.s.check_element_exists(
            ".o_list_view, .o_view_controller",
            "smoke: Freight Carriers list view present"))

    def run_spec(self):
        """Open a DSV carrier (if seeded) and verify the DSV config group."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FREIGHT_CARRIER}?view_type=list",
                    wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        opened_dsv = False
        for i in range(min(rows.count(), 12)):
            row = rows.nth(i)
            text = row.inner_text() if row.count() else ""
            if "dsv" in text.lower() or "DSV" in text:
                row.click()
                self.s.page.wait_for_timeout(3500)
                self.s.scroll_to_top()
                opened_dsv = True
                break

        if not opened_dsv:
            self.add_spec(Check(
                "spec: DSV provider config form",
                Status.SKIP,
                "No DSV-flavoured delivery.carrier on target instance"))
            return

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: DSV carrier form not blank")))
        # The DSV config group is rendered when delivery_type ∈ {dsv_generic, dsv_xpress}.
        # Group elements bear name="dsv_config" via the inherited view.
        self.add_spec(self.s.check_element_exists(
            '[name="dsv_config"], [name="x_dsv_environment"]',
            "spec: DSV carrier exposes DSV configuration group"))
        # x_dsv_environment is universal across both DSV adapter flavours.
        self.add_spec(self.s.check_element_exists(
            '[name="x_dsv_environment"]',
            "spec: DSV carrier has x_dsv_environment field"))

    def run_workflows(self):
        # No safe workflow here without a real DSV API endpoint.
        self.add_workflow(Check(
            "workflow: DSV booking workflow",
            Status.SKIP,
            "Skipped — exercising real DSV API would require live OAuth + APIM keys"))
