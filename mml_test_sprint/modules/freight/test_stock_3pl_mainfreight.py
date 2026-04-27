"""Tests for ``stock_3pl_mainfreight`` — Mainfreight 3PL implementation.

Smoke
-----
* The "3PL Operations" KPI dashboard / order pipeline action loads.
* The Exception Queue list loads (action_mf_exceptions).

Spec
----
* Open a stock.warehouse form and verify the "Mainfreight Routing" group
  injected by ``warehouse_mf_views.xml`` is rendered with the
  ``x_mf_enabled`` / ``x_mf_latitude`` / ``x_mf_longitude`` fields.

The order pipeline / exception queue are simple list views — no
workflow checks here that don't require a live Mainfreight API response.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


# Action xml-ids declared under stock_3pl_mainfreight/views/.
ACTION_KPI_DASHBOARD = "action-stock_3pl_mainfreight.action_mf_kpi_dashboard"
ACTION_ORDER_PIPELINE = "action-stock_3pl_mainfreight.action_mf_order_pipeline"
ACTION_EXCEPTIONS = "action-stock_3pl_mainfreight.action_mf_exceptions"
ACTION_DISCREPANCY = "action-stock_3pl_mainfreight.action_mf_discrepancy"
# The native warehouse form (Inventory > Configuration > Warehouses).
ACTION_WAREHOUSE = "action-stock.action_warehouse_form"


class Stock3plMainfreightTests(BaseModuleTest):
    module_name = "stock_3pl_mainfreight"
    module_label = "stock_3pl_mainfreight (3PL Mainfreight)"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_dashboard()
        self._smoke_pipeline()
        self._smoke_exceptions()

    def _smoke_dashboard(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_KPI_DASHBOARD}", wait_ms=5000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: 3PL KPI Dashboard loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: KPI Dashboard no error dialog"))

    def _smoke_pipeline(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORDER_PIPELINE}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: 3PL Order Pipeline list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: 3PL Order Pipeline no error dialog"))

    def _smoke_exceptions(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_EXCEPTIONS}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: 3PL Exception Queue list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: 3PL Exception Queue no error dialog"))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        """Open a stock.warehouse — verify the Mainfreight Routing group."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_WAREHOUSE}?view_type=list",
                    wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: stock.warehouse Mainfreight tab",
                Status.SKIP,
                "No stock.warehouse records on target instance"))
            return

        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()
        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: warehouse form not blank")))

        # The Mainfreight Routing group is injected by warehouse_mf_views.xml.
        self.add_spec(self.s.check_element_exists(
            '[name="x_mf_enabled"]',
            "spec: warehouse form has x_mf_enabled field"))
        # Latitude / longitude are conditionally rendered only when
        # x_mf_enabled=True. Use a non-strict locator so the test passes
        # whether or not enabled is on for the picked record.
        if self.s.page.locator('[name="x_mf_enabled"] input[type="checkbox"]:checked').count() > 0:
            self.add_spec(self.s.check_element_exists(
                '[name="x_mf_latitude"]',
                "spec: warehouse form has x_mf_latitude field (when enabled)"))
            self.add_spec(self.s.check_element_exists(
                '[name="x_mf_longitude"]',
                "spec: warehouse form has x_mf_longitude field (when enabled)"))
        else:
            self.add_spec(Check(
                "spec: warehouse form has x_mf_latitude / x_mf_longitude",
                Status.SKIP,
                "Mainfreight not enabled on first warehouse — fields hidden by view condition"))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        # No safe end-to-end workflow without a live Mainfreight API.
        self.add_workflow(Check(
            "workflow: 3PL Mainfreight outbound dispatch",
            Status.SKIP,
            "Skipped — exercising real Mainfreight API requires live REST/SFTP creds"))
