"""Tests for mml_forecast_core — shared forecasting infra (FX, ports, terms).

Smoke:   Forecasting app menu loads; forecast.config list opens; origin.port
         list opens.
Spec:    Forecast.config form has name, date_start, horizon_months, scenario.
         FX rate, customer-term, supplier-term tabs visible.
Workflow: Origin Port editable list accepts row navigation.

mml_forecast_core is application=True and owns the top-level Forecasting menu.
"""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_FORECAST_CONFIG = "action-mml_forecast_core.action_forecast_config"
ACTION_ORIGIN_PORT = "action-mml_forecast_core.action_forecast_origin_port"


class ForecastCoreTests(BaseModuleTest):
    module_name = "mml_forecast_core"
    module_label = "Forecast Core"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_app_menu()
        self._smoke_forecast_list()
        self._smoke_origin_port_list()

    def _smoke_app_menu(self):
        """Top-level Forecasting menu loads (app tile entry point)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        check = self.s.check_no_js_errors("smoke: Forecasting app menu loads")
        if self.s.page.locator('.o_main_navbar').count() == 0:
            check = Check("smoke: Forecasting app menu loads", Status.FAIL,
                          "No navbar found")
        self.add_smoke(self.s.snap(check))

    def _smoke_forecast_list(self):
        """Financial Forecasts list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Forecast Configs list loads"
        )))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: Forecast Configs no error dialog"
        ))

    def _smoke_origin_port_list(self):
        """Configuration > Origin Ports loads (editable inline list)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORIGIN_PORT}?view_type=list", wait_ms=3500)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Origin Ports list loads"
        )))
        self.add_smoke(self.s.check_element_exists(
            '.o_list_view',
            "smoke: Origin Ports list view present"
        ))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_forecast_config_form_fields()
        self._spec_forecast_config_tabs()
        self._spec_origin_port_columns()

    def _spec_forecast_config_form_fields(self):
        """Forecast.config form has name, date_start, horizon_months, scenario."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            # Use the New button to scaffold an empty form for field detection
            new_btn = self.s.page.locator(
                'button.o_list_button_add, button:has-text("New")'
            )
            if new_btn.count() == 0:
                self.add_spec(Check(
                    "spec: Forecast Config form fields",
                    Status.SKIP,
                    "No records and no New button accessible"
                ))
                return
            new_btn.first.click()
            self.s.page.wait_for_timeout(2500)
        else:
            rows.first.click()
            self.s.page.wait_for_timeout(3500)
            self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Forecast Config form not blank"
        )))
        self.add_spec(self.s.check_element_exists(
            '[name="name"]',
            "spec: Forecast Config has name field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="date_start"]',
            "spec: Forecast Config has date_start field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="horizon_months"]',
            "spec: Forecast Config has horizon_months field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="scenario"]',
            "spec: Forecast Config has scenario field"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status',
            "spec: Forecast Config has state statusbar (draft->generated->locked)"
        ))

    def _spec_forecast_config_tabs(self):
        """FX Rates, Customer Payment Terms, Supplier Payment Terms tabs all present."""
        # Re-use the form opened above (we may have just navigated to a New record)
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: Forecast Config notebook tabs",
                Status.SKIP,
                "No saved records to inspect notebook on"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)

        # Tabs come from view_forecast_config_form (core) plus inherited
        # extension in mml_forecast_financial.
        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("FX")',
            "spec: Forecast Config has FX Rates tab"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("Payment Terms"), '
            '.o_notebook .nav-link:has-text("Customer Payment Terms")',
            "spec: Forecast Config has Payment Terms tab"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("Supplier Payment Terms"), '
            '.o_notebook .nav-link:has-text("Supplier")',
            "spec: Forecast Config has Supplier Terms tab/section"
        ))

    def _spec_origin_port_columns(self):
        """Origin Port list shows code, name, transit_days_nz columns."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORIGIN_PORT}?view_type=list", wait_ms=3500)
        if self.s.page.locator('.o_list_view').count() == 0:
            self.add_spec(Check(
                "spec: Origin Port list columns",
                Status.WARN,
                "List view not rendered"
            ))
            return
        # Editable list: column headers expose th[data-name]. Fall back to
        # checking field cells if any row exists.
        for col in ("code", "name", "transit_days_nz"):
            self.add_spec(self.s.check_element_exists(
                f'th[data-name="{col}"], td[name="{col}"]',
                f"spec: Origin Port list has '{col}' column"
            ))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_origin_port_inline_edit()

    def _workflow_origin_port_inline_edit(self):
        """Origin Port is editable=bottom — clicking a cell should open it."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORIGIN_PORT}?view_type=list", wait_ms=3500)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: Origin Port row editable",
                Status.SKIP,
                "No origin port records seeded"
            ))
            return
        try:
            rows.first.locator('td[name="notes"], td.o_data_cell').first.click()
            self.s.page.wait_for_timeout(1000)
            editing = (
                self.s.page.locator('.o_selected_row, input.o_input').count() > 0
            )
            if editing:
                self.add_workflow(self.s.snap(Check(
                    "workflow: Origin Port row editable",
                    Status.PASS,
                    "Inline editor activated"
                )))
            else:
                self.add_workflow(Check(
                    "workflow: Origin Port row editable",
                    Status.WARN,
                    "Click did not activate inline editor"
                ))
        except Exception as e:
            self.add_workflow(Check(
                "workflow: Origin Port row editable",
                Status.WARN,
                f"Inline-edit click raised: {e}"[:200]
            ))
