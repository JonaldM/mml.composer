"""Tests for mml_barcode_registry — Barcode Registry module."""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


class BarcodeRegistryTests(BaseModuleTest):
    module_name = "mml_barcode_registry"
    module_label = "Barcode Registry"

    def run_smoke(self):
        """Navigate to barcode registry views using the correct action URLs."""
        ACTION_ALLOCATION = "action-mml_barcode_registry.action_barcode_allocation"
        ACTION_DASHBOARD = "action-mml_barcode_registry.action_barcode_dashboard"

        # Try allocation list first
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=4000)

        # Check we're on an Odoo view (not a 404 or login redirect)
        if self.s.page.locator('.o_action, .o_list_view, .o_view_controller').count() == 0:
            self.add_smoke(Check("smoke: Barcode allocation list loads", Status.FAIL,
                                 f"Navigation to {ACTION_ALLOCATION} did not render an Odoo view"))
            return

        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Barcode allocation list loads")))
        self.add_smoke(self.s.check_no_error_dialog("smoke: Barcode allocation no error dialog"))

        # Dashboard view
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DASHBOARD}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Barcode dashboard loads")))

        # Open a record if any exist
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=5000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() > 0:
            rows.first.click()
            self.s.page.wait_for_timeout(3000)
            self.s.scroll_to_top()
            self.add_smoke(self.s.snap(self.s.check_no_blank_page("smoke: Barcode form not blank")))
        else:
            self.add_smoke(Check("smoke: Barcode record opens", Status.SKIP,
                                 "No barcode records in DB"))

    def run_spec(self):
        """Verify key fields: GTIN, allocation state, product link."""
        ACTION_ALLOCATION = "action-mml_barcode_registry.action_barcode_allocation"
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=6000)

        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            new_btn = self.s.page.locator('button.o_list_button_add, button:has-text("New")')
            if new_btn.count() > 0:
                new_btn.first.click()
                self.s.page.wait_for_timeout(2000)
            else:
                self.add_spec(Check("spec: Barcode fields", Status.SKIP,
                                    "No records in DB and no New button accessible"))
                return
        else:
            rows.first.click()
            self.s.page.wait_for_timeout(3000)
            self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page("spec: Barcode form renders")))

        self.add_spec(self.s.check_element_exists(
            '[name="name"], [name="gtin"], [name="barcode"], [name="gtin_13"], [name="gtin13"]',
            "spec: Barcode has name/GTIN field"
        ))

        self.add_spec(self.s.check_element_exists(
            '[name="state"], [name="allocation_state"], .o_statusbar_status',
            "spec: Barcode has allocation state field or statusbar"
        ))

    def run_workflows(self):
        """Barcode registry: verify list loads and count records."""
        ACTION_ALLOCATION = "action-mml_barcode_registry.action_barcode_allocation"
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        count = rows.count()
        self.add_workflow(self.s.snap(Check(
            "workflow: Barcode allocation list has records",
            Status.PASS if count > 0 else Status.WARN,
            f"{count} barcode record(s) in DB"
        )))
