"""Tests for mml_barcode_registry — Barcode Registry module."""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


class BarcodeRegistryTests(BaseModuleTest):
    module_name = "mml_barcode_registry"
    module_label = "Barcode Registry"

    def run_smoke(self):
        """Navigate to barcode registry views."""
        # Try common URL patterns for the app
        self.s.goto(f"{BASE_URL}/odoo/barcodes", wait_ms=4000)
        # If that 404s, try the app menu
        if "404" in self.s.page.url or self.s.page.locator('.o_action').count() == 0:
            # Try via app tile
            self.s.goto(f"{BASE_URL}/odoo", wait_ms=3000)
            app_tile = self.s.page.locator('.o_app:has-text("Barcode"), .o_app:has-text("barcode")')
            if app_tile.count() > 0:
                app_tile.first.click()
                self.s.page.wait_for_timeout(3000)
            else:
                self.add_smoke(Check("smoke: Barcode app accessible", Status.WARN,
                                    "Could not find Barcode app tile — may not be installed"))
                return

        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Barcode Registry loads")))

        # Try to find a list view
        list_btn = self.s.page.locator('button[name="list"], .o_switch_view[data-type="list"]')
        if list_btn.count() > 0:
            list_btn.first.click()
            self.s.page.wait_for_timeout(2000)

        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Barcode list loads")))

        # Open a record if any exist
        rows = self.s.page.locator('.o_data_row')
        if rows.count() > 0:
            rows.first.click()
            self.s.page.wait_for_timeout(3000)
            self.s.scroll_to_top()
            self.add_smoke(self.s.snap(self.s.check_no_blank_page("smoke: Barcode form not blank")))
        else:
            self.add_smoke(Check("smoke: Barcode record opens", Status.SKIP, "No records in DB"))

    def run_spec(self):
        """Verify key fields described in CLAUDE.md are present."""
        # CLAUDE.md: GTIN lifecycle, allocation state, GS1 company prefix
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            # Try to open new record form
            new_btn = self.s.page.locator('button.o_list_button_add, button:has-text("New")')
            if new_btn.count() > 0:
                new_btn.first.click()
                self.s.page.wait_for_timeout(2000)
            else:
                self.add_spec(Check("spec: Barcode fields", Status.SKIP, "No records and no New button"))
                return
        else:
            rows.first.click()
            self.s.page.wait_for_timeout(3000)
            self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page("spec: Barcode form renders")))

        # From CLAUDE.md: GTIN field
        self.add_spec(self.s.check_element_exists(
            '[name="name"], [name="gtin"], input[id*="gtin"]',
            "spec: Barcode has GTIN/name field"
        ))

        # Allocation state
        self.add_spec(self.s.check_element_exists(
            '[name="state"], [name="allocation_state"], .o_statusbar_status',
            "spec: Barcode has allocation state"
        ))

    def run_workflows(self):
        """Barcode registry: verify list loads, count records."""
        rows = self.s.page.locator('.o_data_row')
        count = rows.count()
        self.add_workflow(Check(
            "workflow: Barcode list has records",
            Status.PASS if count > 0 else Status.WARN,
            f"{count} barcode record(s) in DB"
        ))
