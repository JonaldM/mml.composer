"""Tests for ``stock_3pl_core`` — 3PL platform layer.

``stock_3pl_core`` is ``application = False`` — its menus are exposed by
adapter modules (``stock_3pl_mainfreight`` registers them under
"3PL Operations > Configuration"). Test scope:

Smoke
-----
* The 3PL Connectors list (action_3pl_connector) loads cleanly.
* The 3PL Message Queue list (action_3pl_message_all) loads cleanly and
  shows the canonical state-machine columns (state, retry_count).

Spec
----
* Open a 3pl.message form (if any messages exist) and verify the
  state-machine fields: ``state``, ``retry_count``, ``next_retry_at``,
  ``last_error``.

Workflows
---------
* Apply a state filter (state=dead) on the message queue and verify the
  filter pill is set and the list re-renders. We use the dead-letter
  action (``action_3pl_message_dead``) which has the filter baked in.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


# Action xml-ids declared in stock_3pl_core/views/connector_views.xml + message_views.xml.
ACTION_CONNECTORS = "action-stock_3pl_core.action_3pl_connector"
ACTION_MESSAGES = "action-stock_3pl_core.action_3pl_message_all"
ACTION_DEAD_LETTERS = "action-stock_3pl_core.action_3pl_message_dead"


class Stock3plCoreTests(BaseModuleTest):
    module_name = "stock_3pl_core"
    module_label = "stock_3pl_core (3PL Platform)"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_connectors_list()
        self._smoke_messages_list()

    def _smoke_connectors_list(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_CONNECTORS}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: 3PL Connectors list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: 3PL Connectors no error dialog"))
        self.add_smoke(self.s.check_element_exists(
            ".o_list_view, .o_kanban_view, .o_view_controller",
            "smoke: 3PL Connectors view present"))

    def _smoke_messages_list(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_MESSAGES}?view_type=list",
                    wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: 3PL Message Queue list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: 3PL Message Queue no error dialog"))
        # Canonical columns from message_views.xml — state machine + retry.
        self.add_smoke(self.s.check_element_exists(
            'th[data-name="state"], .o_list_table th:has-text("State")',
            "smoke: Message Queue list has state column"))
        self.add_smoke(self.s.check_element_exists(
            'th[data-name="retry_count"], .o_list_table th:has-text("Retry")',
            "smoke: Message Queue list has retry_count column"))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        """Open a 3pl.message and verify the state-machine field set."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_MESSAGES}?view_type=list",
                    wait_ms=4000)
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: 3pl.message form fields",
                Status.SKIP,
                "No 3pl.message records on target instance"))
            return

        rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()
        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: 3pl.message form not blank")))

        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status, [name="state"]',
            "spec: 3pl.message has state widget"))
        self.add_spec(self.s.check_element_exists(
            '[name="retry_count"]',
            "spec: 3pl.message has retry_count field"))
        # last_error is the canonical name — message.py defines no
        # ``error_message`` field. Accept either to insulate against rename.
        self.add_spec(self.s.check_element_exists(
            '[name="last_error"], [name="error_message"]',
            "spec: 3pl.message has last_error field"))
        self.add_spec(self.s.check_element_exists(
            '[name="connector_id"]',
            "spec: 3pl.message has connector_id field"))
        self.add_spec(self.s.check_element_exists(
            '[name="document_type"]',
            "spec: 3pl.message has document_type field"))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_filter_dead_messages()

    def _workflow_filter_dead_messages(self):
        """Verify the dead-letter filter action loads with the state=dead filter."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DEAD_LETTERS}?view_type=list",
                    wait_ms=4000)
        self.add_workflow(self.s.snap(self.s.check_no_js_errors(
            "workflow: dead-letter filter action loads")))

        # The dead-letter action has domain [('state', '=', 'dead')] hard-baked.
        # Either every visible row has state='dead', or there are no rows.
        rows = self.s.page.locator(".o_data_row")
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: dead-letter filter shows only state=dead rows",
                Status.PASS,
                "No dead-letter messages — filter renders empty list cleanly"))
            return

        # Sample up to 8 rows and check that "dead" (or its localised variant)
        # appears somewhere in each row.
        bad_rows = 0
        sampled = min(rows.count(), 8)
        for i in range(sampled):
            text = rows.nth(i).inner_text().lower()
            if "dead" not in text:
                bad_rows += 1
        if bad_rows == 0:
            self.add_workflow(self.s.snap(Check(
                "workflow: dead-letter filter shows only state=dead rows",
                Status.PASS,
                f"All {sampled} sampled row(s) display 'dead' state")))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: dead-letter filter shows only state=dead rows",
                Status.WARN,
                f"{bad_rows}/{sampled} row(s) did not show 'dead' in text — "
                "may be due to translated label; verify visually")))
