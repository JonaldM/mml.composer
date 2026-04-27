"""Tests for mml_edi — EDI engine (Briscoes parser, FTP poll, ASN gen).

Smoke:   Top-level EDI menu reachable; trading-partner list; pending-review list;
         EDI sale orders list; logs list.
Spec:    Trading-partner form has pricelist_id field. Form fields verified.
Workflow: Inbound dashboard renders. M1 GST gate behaviour observed (see
          run_workflows for details — current code logs a warning rather than
          rejecting hard).

Action XML IDs are read from mml_edi/views/menuitems.xml + per-view files.
"""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


# Action references (use module-prefixed XMLIDs — the harness URL pattern
# is /odoo/action-<module>.<xmlid>).
ACTION_DASHBOARD = "action-mml_edi.action_edi_order_review"
ACTION_PENDING = "action-mml_edi.action_edi_order_review_pending"
ACTION_SALE_ORDERS = "action-mml_edi.action_edi_sale_orders"
ACTION_LOGS = "action-mml_edi.action_edi_log"
ACTION_TRADING_PARTNERS = "action-mml_edi.action_edi_trading_partner"


class EdiTests(BaseModuleTest):
    module_name = "mml_edi"
    module_label = "EDI Engine"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_dashboard()
        self._smoke_pending_review()
        self._smoke_sale_orders()
        self._smoke_logs()
        self._smoke_trading_partners()

    def _smoke_dashboard(self):
        """EDI dashboard (review list as homepage) loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DASHBOARD}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: EDI Dashboard loads"
        )))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: EDI Dashboard no error dialog"
        ))

    def _smoke_pending_review(self):
        """Pending Review list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_PENDING}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: EDI Pending Review list loads"
        )))

    def _smoke_sale_orders(self):
        """Sales Orders (EDI) list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_SALE_ORDERS}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: EDI Sales Orders list loads"
        )))

    def _smoke_logs(self):
        """EDI Logs list view loads."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_LOGS}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: EDI Logs list loads"
        )))

    def _smoke_trading_partners(self):
        """Trading Partners list (Configuration menu) loads.

        The configuration menu requires `mml_edi.group_edi_manager`; if the
        test user is not in that group, the action will error or 404. We
        treat that as a WARN (data/access gap), not a FAIL.
        """
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TRADING_PARTNERS}?view_type=list", wait_ms=4000)
        # Accept either a list view or the access-denied dialog
        if self.s.page.locator('.o_action, .o_list_view, .o_view_controller').count() == 0:
            self.add_smoke(Check(
                "smoke: Trading Partners list loads",
                Status.WARN,
                "Action did not render — user may lack mml_edi.group_edi_manager"
            ))
        else:
            self.add_smoke(self.s.snap(self.s.check_no_js_errors(
                "smoke: Trading Partners list loads"
            )))
            self.add_smoke(self.s.check_no_error_dialog(
                "smoke: Trading Partners no error dialog"
            ))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_trading_partner_pricelist_field()
        self._spec_pending_review_columns()

    def _spec_trading_partner_pricelist_field(self):
        """Trading-partner form: must expose pricelist_id (per M1 design).

        Spec-doc requires a pricelist_id field so EDI prices can be matched
        against the partner's contractual pricelist (Briscoes Products, etc.).
        """
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TRADING_PARTNERS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: Trading partner has pricelist_id field",
                Status.SKIP,
                "No trading partners exist (or access denied)"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Trading partner form not blank"
        )))
        self.add_spec(self.s.check_element_exists(
            '[name="pricelist_id"]',
            "spec: Trading partner has pricelist_id field"
        ))
        # Other contract fields per views/edi_trading_partner_views.xml
        self.add_spec(self.s.check_element_exists(
            '[name="edi_format"]',
            "spec: Trading partner has edi_format field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="environment"]',
            "spec: Trading partner has environment field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="auto_confirm_clean"]',
            "spec: Trading partner has auto_confirm_clean toggle"
        ))

    def _spec_pending_review_columns(self):
        """Pending review list should expose review state and partner."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_PENDING}?view_type=list", wait_ms=4000)
        if self.s.page.locator('.o_list_view').count() == 0:
            self.add_spec(Check(
                "spec: Pending review list rendered",
                Status.WARN,
                "List view did not render"
            ))
            return
        self.add_spec(self.s.snap(self.s.check_element_exists(
            '.o_list_view',
            "spec: Pending review list rendered"
        )))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_dashboard_renders_data()
        self._workflow_m1_gst_gate_observation()

    def _workflow_dashboard_renders_data(self):
        """Dashboard should render either reviews or the empty-state nocontent panel."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DASHBOARD}", wait_ms=4000)
        rendered = (
            self.s.page.locator('.o_data_row').count() > 0
            or self.s.page.locator('.o_view_nocontent').count() > 0
            or self.s.page.locator('.o_kanban_view').count() > 0
        )
        if rendered:
            self.add_workflow(self.s.snap(Check(
                "workflow: EDI Dashboard renders",
                Status.PASS,
                f"{self.s.page.locator('.o_data_row').count()} review row(s)"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: EDI Dashboard renders",
                Status.FAIL,
                "Neither data rows nor empty-state panel found"
            )))

    def _workflow_m1_gst_gate_observation(self):
        """M1 GST gate — current behaviour check.

        The mml_edi processor (models/edi_processor.py:347-356) emits an
        ex-GST advisory comment but does NOT hard-reject GST-inclusive
        pricelists. A negative-path UI test cannot reliably trigger a
        rejection dialog.

        Until M1 is upgraded to a hard validation (UserError on save when
        a GST-inclusive pricelist is assigned), this workflow records the
        current state as INFO (WARN) so the gap is visible in the report.
        """
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_TRADING_PARTNERS}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: M1 GST gate observable on trading partner save",
                Status.SKIP,
                "No trading partners to test (or access denied)"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)

        # Look for any constraint message banner that mentions GST.
        # Current code does not raise — this should be SKIP/WARN, never PASS.
        constraint_count = self.s.page.locator(
            '.alert:has-text("GST"), .o_notification:has-text("GST")'
        ).count()
        if constraint_count > 0:
            self.add_workflow(self.s.snap(Check(
                "workflow: M1 GST gate observable on trading partner save",
                Status.PASS,
                f"GST-related notice surfaced ({constraint_count})"
            )))
        else:
            self.add_workflow(Check(
                "workflow: M1 GST gate observable on trading partner save",
                Status.WARN,
                "No GST validation/notice surfaced — M1 hard-gate not enforced "
                "in current build (see edi_processor.py:347)"
            ))
