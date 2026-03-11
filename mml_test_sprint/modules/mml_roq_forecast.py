"""Tests for mml_roq_forecast — ROQ Forecast module."""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


# Action IDs on mml_dev (verified in session)
ACTION_RUNS = "action-mml_roq_forecast.action_roq_forecast_run"
ACTION_SHIPMENT_GROUPS = "2020"
ACTION_CALENDAR = "2023"
ACTION_ORDER_DASHBOARD = "action-mml_roq_forecast.action_roq_order_dashboard"
ACTION_PORTS = "action-mml_roq_forecast.action_roq_port"


class RoqForecastTests(BaseModuleTest):
    module_name = "mml_roq_forecast"
    module_label = "ROQ Forecast"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_app_menu()
        self._smoke_order_dashboard()
        self._smoke_roq_runs_list()
        self._smoke_shipment_groups_list()
        self._smoke_shipment_calendar()
        self._smoke_freight_ports()

    def _smoke_app_menu(self):
        """ROQ Forecast top-level app menu is reachable."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_RUNS}")
        check = self.s.check_no_js_errors("menu: ROQ Forecast app loads")
        # Verify app menu bar is present
        if self.s.page.locator('.o_main_navbar').count() == 0:
            check = Check("menu: ROQ Forecast app loads", Status.FAIL, "No navbar found")
        self.add_smoke(self.s.snap(check))

    def _smoke_order_dashboard(self):
        """Order Dashboard loads without errors."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORDER_DASHBOARD}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Order Dashboard loads")))
        self.add_smoke(self.s.check_no_error_dialog("smoke: Order Dashboard no error dialog"))

    def _smoke_roq_runs_list(self):
        """ROQ Runs list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_RUNS}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: ROQ Runs list loads")))
        self.add_smoke(self.s.check_no_blank_page("smoke: ROQ Runs list not blank"))

    def _smoke_shipment_groups_list(self):
        """Shipment Groups list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Shipment Groups list loads")))

    def _smoke_shipment_calendar(self):
        """Shipment Calendar view loads."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_CALENDAR}", wait_ms=5000)
        check = self.s.check_element_exists(".o_calendar_view", "smoke: Calendar view renders",
                                             "FullCalendar container must be present")
        self.add_smoke(self.s.snap(check))
        self.add_smoke(self.s.check_no_js_errors("smoke: Calendar no JS errors"))

    def _smoke_freight_ports(self):
        """Configuration > Freight Ports loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_PORTS}?view_type=list", wait_ms=3000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors("smoke: Freight Ports loads")))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_dashboard_tabs()
        self._spec_roq_run_form()
        self._spec_shipment_group_form()
        self._spec_suppliers_tab()
        self._spec_calendar_filters()
        self._spec_kanban_groups()

    def _spec_dashboard_tabs(self):
        """Order Dashboard: spec says 'Urgency' and 'Order by Supplier' tabs."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORDER_DASHBOARD}", wait_ms=4000)
        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("Urgency"), '
            '.o_notebook .nav-link:has-text("urgency"), '
            'a:has-text("Urgency")',
            "spec: Order Dashboard has Urgency tab"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("Supplier"), '
            'a:has-text("Order by Supplier"), '
            'a:has-text("By Supplier")',
            "spec: Order Dashboard has Order by Supplier tab"
        ))

    def _spec_roq_run_form(self):
        """ROQ Run form: spec says run has pipeline output — forecast lines, shipment groups."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_RUNS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check("spec: ROQ Run form fields", Status.SKIP, "No runs in list"))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)
        self.s.scroll_to_top()
        self.add_spec(self.s.snap(self.s.check_no_blank_page("spec: ROQ Run form not blank")))
        self.add_spec(self.s.check_element_exists(
            'input[id*="name"], .o_field_char input',
            "spec: ROQ Run has name/reference field"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_statusbar_status',
            "spec: ROQ Run has state statusbar"
        ))

    def _spec_shipment_group_form(self):
        """Shipment Group form: spec says CBM, fill%, container type, state statusbar, Suppliers tab."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check("spec: SG form fields", Status.SKIP, "No shipment groups"))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(4000)
        self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page("spec: SG form not blank (chatter bug check)")))

        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status',
            "spec: SG form has state statusbar (draft->confirmed->tendered->booked->delivered)"
        ))

        # action_confirm button — visible only on draft records.
        # Iterate the list to find a draft record before checking the button.
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        draft_found = False
        list_rows = self.s.page.locator('.o_data_row')
        for i in range(min(list_rows.count(), 10)):
            badge = list_rows.nth(i).locator('[name="state"], .badge')
            if badge.count() > 0 and 'draft' in badge.first.inner_text().lower():
                list_rows.nth(i).click()
                self.s.page.wait_for_timeout(3000)
                draft_found = True
                break
        if draft_found:
            self.add_spec(self.s.check_element_exists(
                'button[name="action_confirm"]',
                "spec: SG form has Confirm & Create Tender button (on draft record)"
            ))
        else:
            self.add_spec(Check(
                "spec: SG form has Confirm & Create Tender button",
                Status.SKIP,
                "No draft shipment groups exist to test button visibility"
            ))

        self.add_spec(self.s.check_element_exists(
            '[name="total_cbm"]',
            "spec: SG form has Total CBM field"
        ))

        self.add_spec(self.s.check_element_exists(
            '[name="fill_percentage"]',
            "spec: SG form has Fill % field"
        ))

        self.add_spec(self.s.check_element_exists(
            '[name="container_type"]',
            "spec: SG form has Container Type field"
        ))

        self.add_spec(self.s.check_element_exists(
            '.o_notebook .nav-link:has-text("Suppliers")',
            "spec: SG form has Suppliers tab"
        ))

    def _spec_suppliers_tab(self):
        """Suppliers tab: spec says supplier, CBM, SKU count, OOS risk, View SKUs button."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check("spec: Suppliers tab", Status.SKIP, "No shipment groups"))
            return

        clicked_with_lines = False
        for i in range(min(rows.count(), 5)):
            rows.nth(i).click()
            self.s.page.wait_for_timeout(3000)
            suppliers_tab = self.s.page.locator('.o_notebook .nav-link:has-text("Suppliers")')
            if suppliers_tab.count() > 0:
                suppliers_tab.click()
                self.s.page.wait_for_timeout(1500)
                if self.s.page.locator('.o_field_one2many .o_data_row').count() > 0:
                    clicked_with_lines = True
                    break
            self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=3000)

        if not clicked_with_lines:
            self.add_spec(Check("spec: Suppliers tab has lines", Status.WARN,
                                "No shipment group with supplier lines found"))
            return

        self.add_spec(self.s.snap(self.s.check_row_count(
            '.o_field_one2many .o_data_row', 1, "spec: Suppliers tab has at least 1 line"
        )))

        self.add_spec(self.s.check_element_exists(
            'button[name="action_view_forecast_lines"]',
            "spec: Suppliers tab has View SKUs button"
        ))

        self.add_spec(self.s.check_element_exists(
            '[name="oos_risk_flag"]',
            "spec: Suppliers tab has OOS Risk column"
        ))

        self.add_spec(self.s.check_element_exists(
            '[name="push_pull_days"]',
            "spec: Suppliers tab has Push/Pull Days column"
        ))

    def _spec_calendar_filters(self):
        """Calendar: spec says state-based filters (Draft, Confirmed, In Transit, Active)."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_CALENDAR}", wait_ms=5000)
        self.add_spec(self.s.check_element_exists(
            '.o_calendar_view .fc',
            "spec: Calendar has FullCalendar grid"
        ))
        self.add_spec(self.s.check_element_exists(
            '.o_calendar_mini, .o_calendar_sidebar',
            "spec: Calendar has date picker sidebar"
        ))

    def _spec_kanban_groups(self):
        """Kanban: spec says grouped by state with mode badge (reactive/proactive)."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}", wait_ms=5000)
        self.add_spec(self.s.snap(self.s.check_element_exists(
            '.o_kanban_view',
            "spec: Shipment Groups has kanban view"
        )))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_order_dashboard_by_supplier()
        self._workflow_sg_form_renders_correctly()
        self._workflow_view_skus_button()
        self._workflow_calendar_shows_events()
        self._workflow_roq_run_has_lines()

    def _workflow_order_dashboard_by_supplier(self):
        """Order Dashboard: By Supplier tab should have data (not empty) when runs exist."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ORDER_DASHBOARD}", wait_ms=4000)
        tab = self.s.page.locator(
            '.o_notebook .nav-link:has-text("Supplier"), '
            'a:has-text("Order by Supplier"), '
            'a:has-text("By Supplier")'
        )
        if tab.count() == 0:
            self.add_workflow(Check("workflow: By Supplier tab has data", Status.SKIP,
                                   "By Supplier tab not found"))
            return
        tab.first.click()
        self.s.page.wait_for_timeout(2000)
        self.add_workflow(self.s.snap(self.s.check_row_count(
            '.o_data_row, .o_kanban_record',
            1,
            "workflow: Order Dashboard By Supplier tab has at least 1 row"
        )))

    def _workflow_sg_form_renders_correctly(self):
        """Navigate to a SG record. Verify main sheet renders."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check("workflow: SG form renders", Status.SKIP, "No records"))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(4000)
        self.s.scroll_to_top()

        w = self.s.page.evaluate(
            'document.querySelector(".o_form_sheet_bg")?.getBoundingClientRect().width || 0'
        )
        if w < 100:
            self.add_workflow(self.s.snap(Check(
                "workflow: SG form sheet full width",
                Status.FAIL,
                f"Sheet collapsed to {w:.0f}px — chatter/widget rendering bug"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: SG form sheet full width",
                Status.PASS,
                f"Sheet width = {w:.0f}px"
            )))

    def _workflow_view_skus_button(self):
        """Click 'View SKUs' on first supplier line -> verify SKU list opens."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check("workflow: View SKUs opens list", Status.SKIP, "No records"))
            return

        for i in range(min(rows.count(), 5)):
            rows.nth(i).click()
            self.s.page.wait_for_timeout(3000)
            suppliers_tab = self.s.page.locator('.o_notebook .nav-link:has-text("Suppliers")')
            if suppliers_tab.count() > 0:
                suppliers_tab.click()
                self.s.page.wait_for_timeout(1500)
                view_btns = self.s.page.locator('button[name="action_view_forecast_lines"]')
                if view_btns.count() > 0:
                    view_btns.first.click()
                    self.s.page.wait_for_timeout(3000)
                    check = self.s.check_element_exists(
                        '.o_list_view, .o_data_row',
                        "workflow: View SKUs opens forecast line list"
                    )
                    self.add_workflow(self.s.snap(check))
                    return
            self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_SHIPMENT_GROUPS}?view_type=list", wait_ms=3000)

        self.add_workflow(Check("workflow: View SKUs opens list", Status.WARN,
                                "No group with View SKUs button found"))

    def _workflow_calendar_shows_events(self):
        """Calendar: navigate forward month-by-month until events appear (up to 6 months)."""
        self.s.goto(f"{BASE_URL}/odoo/action-{ACTION_CALENDAR}", wait_ms=5000)

        # Remove default 'Active' filter so draft records are visible
        close_btns = self.s.page.locator('.o_facet_remove')
        if close_btns.count() > 0:
            close_btns.first.click()
            self.s.page.wait_for_timeout(1500)

        next_btn = self.s.page.locator('button.o_next')
        event_count = 0
        found_month = None
        for month_offset in range(1, 7):  # check Apr through Sep 2026
            if next_btn.count() > 0:
                next_btn.click()
                self.s.page.wait_for_timeout(1500)
            event_count = self.s.page.locator('.fc-event').count()
            if event_count > 0:
                found_month = month_offset
                break

        if found_month is not None:
            self.add_workflow(self.s.snap(Check(
                "workflow: Calendar shows shipment events",
                Status.PASS,
                f"{event_count} event(s) visible at +{found_month} month(s) from current"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: Calendar shows shipment events",
                Status.WARN,
                "No events found in next 6 months — check target_ship_date values in DB"
            )))

    def _workflow_roq_run_has_lines(self):
        """Open latest ROQ run -> By Supplier tab should have supplier data."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_RUNS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check("workflow: ROQ run has supplier lines", Status.SKIP, "No runs"))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)
        # ROQ Run form has "Results" tab (forecast lines) and "Run Log" tab.
        # The "By Supplier" grouping is on the Order Dashboard, not here.
        tab = self.s.page.locator('.o_notebook .nav-link:has-text("Results")')
        if tab.count() > 0:
            tab.first.click()
            self.s.page.wait_for_timeout(2000)
            self.add_workflow(self.s.snap(self.s.check_row_count(
                '.o_data_row', 1, "workflow: ROQ run Results tab has forecast lines"
            )))
        else:
            self.add_workflow(Check("workflow: ROQ run has forecast lines", Status.WARN,
                                   "No 'Results' tab found on ROQ Run form"))
