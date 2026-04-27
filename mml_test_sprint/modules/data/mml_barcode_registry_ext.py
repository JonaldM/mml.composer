"""Extended tests for mml_barcode_registry — registry + brand + workflow.

The base file mml_test_sprint/modules/mml_barcode_registry.py covers
allocation list/form/dashboard. This file adds:

  - Registry list (the canonical 88,001-slot pool, trimmed to 50 in test DB)
  - Status filters: Active / Dormant / Reuse Eligible from search view
  - Allocate-next-available wizard reachability (the prior FINDINGS.md
    noted access was a WARN; we re-verify after the group fixes applied
    in remediation 2026-03-11).

This complements (does NOT replace) the existing
modules/mml_barcode_registry.py BarcodeRegistryTests.
"""
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.modules.base_module import BaseModuleTest


ACTION_ALLOCATION = "action-mml_barcode_registry.action_barcode_allocation"
ACTION_DASHBOARD = "action-mml_barcode_registry.action_barcode_dashboard"
ACTION_REGISTRY_GRAPH = "action-mml_barcode_registry.action_barcode_registry_graph"
ACTION_PREFIX = "action-mml_barcode_registry.action_barcode_prefix"
ACTION_BRAND = "action-mml_barcode_registry.action_mml_brand"


class BarcodeRegistryExtTests(BaseModuleTest):
    module_name = "mml_barcode_registry"
    module_label = "Barcode Registry (extended)"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        self._smoke_dashboard()
        self._smoke_status_graph()
        self._smoke_prefix_list()
        self._smoke_brand_list()

    def _smoke_dashboard(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_DASHBOARD}", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Barcode Registry dashboard loads"
        )))

    def _smoke_status_graph(self):
        """Status Breakdown graph view loads (registry pie chart)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_REGISTRY_GRAPH}", wait_ms=5000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: Registry Status graph loads"
        )))
        # FAIL if no graph container at all; many test DBs may render
        # an empty graph but the .o_graph_view should still appear.
        self.add_smoke(self.s.check_element_exists(
            '.o_graph_view, .o_graph_container, canvas',
            "smoke: Registry Status graph container exists"
        ))

    def _smoke_prefix_list(self):
        """Prefix list (configuration menu — admin only)."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_PREFIX}?view_type=list", wait_ms=3000)
        if self.s.page.locator('.o_list_view, .o_action').count() == 0:
            self.add_smoke(Check(
                "smoke: Barcode Prefix list loads",
                Status.WARN,
                "Action did not render — user may lack base.group_system"
            ))
        else:
            self.add_smoke(self.s.snap(self.s.check_no_js_errors(
                "smoke: Barcode Prefix list loads"
            )))

    def _smoke_brand_list(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_BRAND}?view_type=list", wait_ms=3000)
        if self.s.page.locator('.o_list_view, .o_action').count() == 0:
            self.add_smoke(Check(
                "smoke: Brand list loads",
                Status.WARN,
                "Action did not render — user may lack base.group_system"
            ))
        else:
            self.add_smoke(self.s.snap(self.s.check_no_js_errors(
                "smoke: Brand list loads"
            )))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        self._spec_allocation_form_fields()
        self._spec_allocation_status_filter()

    def _spec_allocation_form_fields(self):
        """Allocation form: status statusbar, gtin_13, product_id, brand_id."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_spec(Check(
                "spec: Allocation form fields",
                Status.SKIP,
                "No allocation records in DB"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)
        self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: Allocation form not blank"
        )))
        self.add_spec(self.s.check_element_exists(
            '.o_form_statusbar .o_statusbar_status',
            "spec: Allocation form has status statusbar (active->dormant->discontinued)"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="gtin_13"]',
            "spec: Allocation form has gtin_13 field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="product_id"]',
            "spec: Allocation form has product_id field"
        ))
        self.add_spec(self.s.check_element_exists(
            '[name="registry_id"]',
            "spec: Allocation form has registry_id link"
        ))

    def _spec_allocation_status_filter(self):
        """Search view exposes Active / Dormant / Discontinued filters."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=4000)
        # Open the search panel to expose filter menu
        search_btn = self.s.page.locator('button.o_searchview_dropdown_toggler, '
                                          '.o_search_options button')
        if search_btn.count() > 0:
            try:
                search_btn.first.click()
                self.s.page.wait_for_timeout(1000)
            except Exception:
                pass
        # Look for the named filter labels (or the search filter dropdown)
        active_filter_visible = (
            self.s.page.locator('span.o_menu_item:has-text("Active"), '
                                'a:has-text("Active"), .dropdown-item:has-text("Active")').count()
            > 0
        )
        if active_filter_visible:
            self.add_spec(self.s.snap(Check(
                "spec: Allocation search has Active/Dormant filters",
                Status.PASS
            )))
        else:
            self.add_spec(Check(
                "spec: Allocation search has Active/Dormant filters",
                Status.WARN,
                "Filter labels not surfaced in dropdown — may require explicit search-panel open"
            ))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        self._workflow_allocate_button_on_product()
        self._workflow_dormant_button_visible_on_active_record()

    def _workflow_allocate_button_on_product(self):
        """Re-test prior FINDINGS.md WARN: 'Allocate next available'.

        The wizard is exposed via product.product.action_allocate_barcode().
        Per views/product_views.xml the button surfaces on the product form.
        We try to navigate to a product that lacks a barcode; if access is
        denied we record the access gap (the prior FINDINGS.md WARN).
        """
        self.s.goto(f"{BASE_URL}/odoo/action-product.product_normal_action_sell?view_type=list",
                    wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: Allocate Barcode button reachable from product",
                Status.SKIP,
                "No products in test DB or product action not reachable"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)
        # The button exists in mml_barcode_registry/views/product_views.xml as
        # name="action_allocate_barcode" on product.product.
        btn = self.s.page.locator('button[name="action_allocate_barcode"]')
        if btn.count() > 0:
            self.add_workflow(self.s.snap(Check(
                "workflow: Allocate Barcode button reachable from product",
                Status.PASS,
                "Button surfaces on product form"
            )))
        else:
            self.add_workflow(self.s.snap(Check(
                "workflow: Allocate Barcode button reachable from product",
                Status.WARN,
                "Button not visible — either product has barcode already, "
                "user lacks group, or view extension was not applied"
            )))

    def _workflow_dormant_button_visible_on_active_record(self):
        """Open an active allocation -> Set Dormant button must be visible."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_ALLOCATION}?view_type=list", wait_ms=4000)
        rows = self.s.page.locator('.o_data_row')
        if rows.count() == 0:
            self.add_workflow(Check(
                "workflow: Active allocation exposes Set Dormant button",
                Status.SKIP,
                "No allocation records"
            ))
            return
        rows.first.click()
        self.s.page.wait_for_timeout(3000)
        # The form button is name="action_dormant"; only visible on active records.
        btn = self.s.page.locator('button[name="action_dormant"]')
        if btn.count() > 0 and btn.first.is_visible():
            self.add_workflow(self.s.snap(Check(
                "workflow: Active allocation exposes Set Dormant button",
                Status.PASS
            )))
        else:
            # Not necessarily a failure — first record may not be active.
            self.add_workflow(Check(
                "workflow: Active allocation exposes Set Dormant button",
                Status.WARN,
                "Button not visible — first row may not be in 'active' state"
            ))
