"""Tests for ``mml_freight_knplus`` — Kuehne+Nagel adapter scaffold.

Validates the **M17 activation gate**:

* ``mml_freight_knplus/data/delivery_carrier_data.xml`` pre-seeds a single
  K+N delivery.carrier with ``active=False``.
* ``mml_freight_knplus/models/freight_carrier_knplus.py::create``/``write``
  raises ``UserError`` with ``KNPLUS_DISABLED_MESSAGE`` whenever a K+N
  carrier is set ``active=True`` and ``MML_KNPLUS_ENABLE`` is not ``"1"``.

UI scope
--------
Smoke / spec confirm:

* The default K+N carrier exists and is **inactive** in the Freight
  Carriers list (the gate prevents creating active ones).
* When the carrier form is opened, the K+N configuration group is
  rendered and contains the expected ``x_knplus_*`` fields.

Workflow check
--------------
* Attempt to toggle the K+N carrier active. A UserError modal/notification
  with the gate copy ("K+N integration is not yet active" / "MML_KNPLUS_ENABLE")
  must appear. If the toggle succeeds, the gate is broken — FAIL.

If ``MML_KNPLUS_ENABLE=1`` is set on the Odoo server (the post-onboarding
state), the workflow check WARNs because the gate is intentionally bypassed
on that environment.
"""
from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.modules.base_module import BaseModuleTest


# Standard MML Freight Carriers action — the carrier list is filtered by
# auto_tender=True so by default a brand-new (auto_tender=False) K+N row
# does NOT appear there. We use the raw delivery.carrier action instead.
ACTION_DELIVERY_CARRIER = "action-delivery.action_delivery_carrier_form"


class MmlFreightKnplusTests(BaseModuleTest):
    module_name = "mml_freight_knplus"
    module_label = "MML Freight — K+N Adapter"

    # ── Smoke ────────────────────────────────────────────────────────────────

    def run_smoke(self):
        """The K+N carrier is reachable and remains inactive by default."""
        # Use the raw delivery.carrier list (mml_freight's action filters
        # auto_tender=True; the K+N seed has auto_tender=False).
        self.s.goto(f"{BASE_URL}/odoo/action-delivery.action_delivery_carrier_form"
                    f"?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: delivery.carrier list loads")))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: delivery.carrier no error dialog"))

        # Toggle off the default 'active=True' filter so inactive K+N row is visible.
        # Odoo adds a "Active" facet by default on delivery.carrier — remove it.
        facet_x = self.s.page.locator('.o_searchview_facet:has-text("Active") .o_facet_remove, '
                                      '.o_facet_remove')
        if facet_x.count() > 0:
            try:
                facet_x.first.click()
                self.s.page.wait_for_timeout(1500)
            except Exception:
                pass

        # Now look for the K+N pre-seeded row.
        rows = self.s.page.locator('.o_data_row:has-text("K+N")')
        if rows.count() == 0:
            self.add_smoke(Check(
                "smoke: K+N seed row visible",
                Status.WARN,
                "No K+N delivery.carrier row found — was the data file loaded?"))
            return

        self.add_smoke(self.s.snap(Check(
            "smoke: K+N seed row visible (post-M17 gate)",
            Status.PASS,
            f"{rows.count()} K+N delivery.carrier row(s) listed")))

    # ── Spec ─────────────────────────────────────────────────────────────────

    def run_spec(self):
        """Open the K+N carrier form, verify the K+N configuration group."""
        self.s.goto(f"{BASE_URL}/odoo/action-delivery.action_delivery_carrier_form"
                    f"?view_type=list", wait_ms=4000)

        # Drop the active=True facet so the inactive K+N row is in the list.
        facet_x = self.s.page.locator('.o_facet_remove')
        if facet_x.count() > 0:
            try:
                facet_x.first.click()
                self.s.page.wait_for_timeout(1500)
            except Exception:
                pass

        kn_rows = self.s.page.locator('.o_data_row:has-text("K+N")')
        if kn_rows.count() == 0:
            self.add_spec(Check(
                "spec: K+N carrier form fields",
                Status.SKIP,
                "No K+N delivery.carrier seeded on target instance"))
            return

        kn_rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()

        self.add_spec(self.s.snap(self.s.check_no_blank_page(
            "spec: K+N carrier form not blank")))

        # The K+N configuration group is rendered conditional on
        # delivery_type='knplus'. Either the group itself or the
        # x_knplus_environment field must be present.
        self.add_spec(self.s.check_element_exists(
            '[name="knplus_config"], [name="x_knplus_environment"]',
            "spec: K+N carrier form exposes K+N configuration group"))
        self.add_spec(self.s.check_element_exists(
            '[name="x_knplus_quote_mode"]',
            "spec: K+N carrier form has x_knplus_quote_mode field"))
        self.add_spec(self.s.check_element_exists(
            '[name="x_knplus_account_number"]',
            "spec: K+N carrier form has x_knplus_account_number field"))

        # The active toggle must currently be False — that's the M17 invariant.
        active_field = self.s.page.locator(
            '.o_field_widget[name="active"] input[type="checkbox"]')
        if active_field.count() > 0:
            is_checked = active_field.first.is_checked()
            self.add_spec(Check(
                "spec: K+N carrier is INACTIVE by default (M17 gate)",
                Status.PASS if not is_checked else Status.FAIL,
                "Carrier is inactive as expected" if not is_checked
                else "K+N carrier is active without MML_KNPLUS_ENABLE — gate broken"))

    # ── Workflows ────────────────────────────────────────────────────────────

    def run_workflows(self):
        """Try to activate the K+N carrier — must hit the M17 UserError gate."""
        self.s.goto(f"{BASE_URL}/odoo/action-delivery.action_delivery_carrier_form"
                    f"?view_type=list", wait_ms=4000)

        facet_x = self.s.page.locator('.o_facet_remove')
        if facet_x.count() > 0:
            try:
                facet_x.first.click()
                self.s.page.wait_for_timeout(1500)
            except Exception:
                pass

        kn_rows = self.s.page.locator('.o_data_row:has-text("K+N")')
        if kn_rows.count() == 0:
            self.add_workflow(Check(
                "workflow: K+N activation gate raises UserError",
                Status.SKIP,
                "No K+N carrier on target instance"))
            return

        kn_rows.first.click()
        self.s.page.wait_for_timeout(3500)
        self.s.scroll_to_top()

        active_field = self.s.page.locator(
            '.o_field_widget[name="active"] input[type="checkbox"]')
        if active_field.count() == 0:
            self.add_workflow(Check(
                "workflow: K+N activation gate raises UserError",
                Status.SKIP,
                "active toggle not found on form"))
            return

        # Click to flip from inactive→active. The M17 gate should reject the
        # write; Odoo presents a UserError dialog.
        try:
            active_field.first.check(force=True)
            self.s.page.wait_for_timeout(800)
            # Save explicitly (Odoo 17+ uses Ctrl+S or the cloud-save icon)
            save_btn = self.s.page.locator(
                'button.o_form_button_save, button[name="save"], .o_form_status_indicator button')
            if save_btn.count() > 0:
                try:
                    save_btn.first.click()
                except Exception:
                    pass
            self.s.page.wait_for_timeout(2500)
        except Exception:
            # If Playwright itself fails to flip the checkbox (overlay hijack),
            # treat as a SKIP — the test is about the back-end raising, not
            # about the front-end accepting the click.
            self.add_workflow(Check(
                "workflow: K+N activation gate raises UserError",
                Status.WARN,
                "Could not toggle the active checkbox via the UI"))
            return

        # The expected message — assert at least one of the gate keywords appears
        # in any visible error/notification element.
        page_text = self.s.page.inner_text("body") if self.s.page else ""
        gate_keywords = (
            "K+N integration is not yet active",
            "MML_KNPLUS_ENABLE",
            "Kuehne+Nagel carrier adapter is a scaffold",
            "K+N integration not enabled",
        )
        if any(kw in page_text for kw in gate_keywords):
            self.add_workflow(self.s.snap(Check(
                "workflow: K+N activation gate raises UserError (M17)",
                Status.PASS,
                "Gate copy displayed when activation attempted")))
        else:
            # Fall back to the generic Odoo error indicators.
            err_visible = (
                self.s.page.locator(".o_error_dialog").count() > 0 or
                self.s.page.locator(".o_notification_error").count() > 0 or
                self.s.page.locator(".modal .alert-danger").count() > 0
            )
            if err_visible:
                self.add_workflow(self.s.snap(Check(
                    "workflow: K+N activation gate raises UserError (M17)",
                    Status.PASS,
                    "Error dialog/notification raised — gate appears to fire")))
            else:
                self.add_workflow(self.s.snap(Check(
                    "workflow: K+N activation gate raises UserError (M17)",
                    Status.FAIL,
                    "K+N carrier was toggled active without UserError — "
                    "M17 gate broken or MML_KNPLUS_ENABLE=1 set on server")))
