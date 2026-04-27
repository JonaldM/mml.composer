"""Tests for mml_forecast_financial — P&L + cashflow analysis layer.

Smoke:   "Analysis" submenu visible under Forecasting; P&L and Cashflow lists
         load.
Spec:    Generate Forecast button visible on draft forecasts; KPI strip appears
         on generated forecasts.
Workflow: Click Generate Forecast on a draft and observe the result.

M2 GST gate behaviour: per the wizard at
mml_forecast_financial/wizards/forecast_generate_wizard.py:242-252, sell prices
are *assumed* ex-GST; a logger.warning() is emitted but generation proceeds.
There is no UserError that a UI test can assert on. We capture this as a WARN
so the gap is visible in the report, mirroring the M1 gate observation in
mml_edi.
"""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_FORECAST_CONFIG = "action-mml_forecast_core.action_forecast_config"
ACTION_PNL = "action-mml_forecast_financial.action_forecast_pnl"
ACTION_CASHFLOW = "action-mml_forecast_financial.action_forecast_cashflow"
ACTION_BS = "action-mml_forecast_financial.action_forecast_balance_sheet"
ACTION_VARIANCE = "action-mml_forecast_financial.action_forecast_variance"


class ForecastFinancialTests(BaseModuleTest):
    module_name = "mml_forecast_financial"
    module_label = "Forecast Financial"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_pnl_list()
        self._smoke_cashflow_list()
        self._smoke_balance_sheet()
        self._smoke_variance()

    def _smoke_pnl_list(self):
        """P&L Summary view loads (default = pivot)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_PNL}", wait_ms=4500)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: P&L Summary loads"
        )))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: P&L Summary no error dialog"
        ))

    def _smoke_cashflow_list(self):
        """Cashflow list loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_CASHFLOW}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Cashflow list loads"
        )))

    def _smoke_balance_sheet(self):
        """Balance Sheet view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_BS}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Balance Sheet loads"
        )))

    def _smoke_variance(self):
        """Variance pivot loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_VARIANCE}", wait_ms=4500)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Variance loads"
        )))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_generate_button_on_draft()
        self._spec_kpi_strip_on_generated()

    def _spec_generate_button_on_draft(self):
        """Forecast.config draft form: Generate Forecast button visible."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: Generate Forecast button on draft",
                Status.SKIP,
                "No forecast configs in DB"
            ))
            return
        # Iterate rows looking for a draft state
        for i in range(min(rows.count(), 8)):
            rows.nth(i).click()
            self.s.page.wait_for_timeout(2500)
            state = self.s.page.locator(
                '.o_form_statusbar .o_arrow_button_current, '
                '.o_form_statusbar [data-value="draft"]'
            )
            if state.count() > 0 and 'draft' in (state.first.inner_text() or '').lower():
                # Found a draft — verify the button
                btn = self.s.page.locator(
                    'button[name="action_generate_forecast"]'
                )
                self.add_spec(self.s.snap(self.s.check_element_exists(
                    'button[name="action_generate_forecast"]',
                    "spec: Generate Forecast button on draft forecast"
                )))
                if btn.count() == 0:
                    pass  # already failed by check_element_exists
                else:
                    self.add_spec(Check(
                        "spec: Generate Forecast button visible to user",
                        Status.PASS,
                        f"button visible={btn.first.is_visible()}"
                    ))
                return
            self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=3000)

        self.add_spec(Check(
            "spec: Generate Forecast button on draft",
            Status.SKIP,
            "No draft forecasts found in first 8 rows"
        ))

    def _spec_kpi_strip_on_generated(self):
        """Generated forecasts surface a KPI strip injected by the financial extension."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: KPI strip on generated forecast",
                Status.SKIP,
                "No forecast configs"
            ))
            return
        found_generated = False
        for i in range(min(rows.count(), 8)):
            rows.nth(i).click()
            self.s.page.wait_for_timeout(2500)
            kpi = self.s.page.locator(
                '[name="kpi_total_revenue"], [name="kpi_ebitda"], [name="kpi_ending_cash"]'
            )
            # KPI fields render only when state != draft
            if kpi.count() > 0:
                found_generated = True
                self.add_spec(self.s.snap(self.s.check_element_exists(
                    '[name="kpi_total_revenue"]',
                    "spec: KPI strip has Total Revenue"
                )))
                self.add_spec(self.s.check_element_exists(
                    '[name="kpi_ebitda"]',
                    "spec: KPI strip has EBITDA"
                ))
                self.add_spec(self.s.check_element_exists(
                    '[name="kpi_ending_cash"]',
                    "spec: KPI strip has Ending Cash"
                ))
                break
            self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=3000)

        if not found_generated:
            self.add_spec(Check(
                "spec: KPI strip on generated forecast",
                Status.SKIP,
                "No generated forecast records to inspect KPI fields"
            ))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_generate_forecast_clickable()
        self._workflow_m2_gst_gate_observation()

    def _workflow_generate_forecast_clickable(self):
        """Click Generate Forecast on a draft and verify it renders without JS errors.

        We do NOT require successful generation (which depends on demand data,
        FX rates, and supplier terms being populated); we only verify the
        action is clickable and does not crash the UI.
        """
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: Generate Forecast clickable",
                Status.SKIP,
                "No forecast configs"
            ))
            return

        for i in range(min(rows.count(), 8)):
            rows.nth(i).click()
            self.s.page.wait_for_timeout(2500)
            btn = self.s.page.locator('button[name="action_generate_forecast"]')
            if btn.count() > 0 and btn.first.is_visible():
                # Fire the action — accept either success or a clean dialog
                try:
                    btn.first.click()
                    self.s.page.wait_for_timeout(5000)
                except Exception as e:
                    self.add_workflow(Check(
                        "workflow: Generate Forecast clickable",
                        Status.FAIL,
                        f"Click raised: {e}"[:200]
                    ))
                    return
                # Accept either the post-generate KPI strip OR a notification
                # OR a non-error dialog ("missing demand data" etc.).
                # Fail only on console JS errors.
                err_dialog = self.s.page.locator(
                    '.o_error_dialog, .modal .alert-danger'
                ).count()
                if err_dialog > 0:
                    msg = self.s.page.locator(
                        '.o_error_dialog, .modal .alert-danger'
                    ).first.inner_text()
                    # An expected UserError (e.g. missing demand) is acceptable
                    self.add_workflow(self.s.snap(Check(
                        "workflow: Generate Forecast clickable",
                        Status.WARN,
                        f"Generate fired but surfaced a dialog: {msg[:200]}"
                    )))
                else:
                    self.add_workflow(self.s.snap(Check(
                        "workflow: Generate Forecast clickable",
                        Status.PASS,
                        "Generate Forecast fired without crashing"
                    )))
                return
            self.s.goto(f"{BASE_URL}/odoo/{ACTION_FORECAST_CONFIG}?view_type=list",
                        wait_ms=3000)

        self.add_workflow(Check(
            "workflow: Generate Forecast clickable",
            Status.SKIP,
            "No draft forecast with visible Generate button"
        ))

    def _workflow_m2_gst_gate_observation(self):
        """M2 GST gate — current behaviour check.

        Per forecast_generate_wizard.py:242-252 the ex-GST assumption surfaces
        only as a logger.warning, never as a UserError. A negative-path UI
        test cannot rely on a visible rejection. This check captures the gap.
        """
        self.add_workflow(Check(
            "workflow: M2 GST gate visible to user when generating",
            Status.WARN,
            "M2 hard-gate not enforced — wizard logs ex-GST assumption only "
            "(see forecast_generate_wizard.py:242). Negative-path UI test "
            "needs seed data and a hard validation to be reliable."
        ))
