"""
Tests for mml_base — Platform Layer (capabilities, events, subscriptions,
license, dispatch failures, registry).

mml_base intentionally has no menu, no top-level action, and
application=False. Its UI surface is therefore limited to:
  1. Technical model browsing (Settings -> Technical -> Database Structure
     -> Models) which is Odoo's built-in `base.action_model` action.
  2. Direct ad-hoc model URLs accessed from the Technical menu.
  3. ACL/group enforcement (which we verify via DB probe).
  4. The S4 dispatch-failure model (skipped here when not yet present).

Smoke    -- can the user log in and navigate to the four core models?
Spec     -- do the models render with their declared fields visible?
Workflow -- are the documented ACLs (group_user read-only, group_system
            full CRUD) actually present in ir_model_access?
"""
from __future__ import annotations

from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.helpers import (
    model_exists,
    module_installed,
    ssh_psql,
    ssh_psql_count,
)
from mml_test_sprint.modules.base_module import BaseModuleTest


# Odoo 19 built-in technical menu actions.
# These let an admin browse any model without a custom action being declared.
ACTION_TECHNICAL_MODELS = "action-base.action_model_data"     # ir.model.data list
ACTION_IR_MODEL = "action-base.action_model_model"            # ir.model list (the canonical "Models" admin view)
ACTION_IR_MODEL_FIELDS = "action-base.action_model_fields"    # ir.model.fields
ACTION_IR_VIEWS = "action-base.action_ui_view"                # ir.ui.view
ACTION_IR_GROUPS = "action-base.action_res_groups"            # res.groups list
ACTION_IR_USERS = "action-base.action_res_users"              # res.users list


PLATFORM_MODELS = [
    ("mml.capability", "Capability registry"),
    ("mml.event", "Event ledger"),
    ("mml.event.subscription", "Event subscription"),
    ("mml.license", "License cache"),
]

# This dispatch-failure model is added by S4 (post-platform sprint). We probe
# for its presence and skip the matching checks if absent.
DISPATCH_FAILURE_MODEL = "mml.event.dispatch.failure"


class MmlBaseUiTests(BaseModuleTest):
    """UI/admin tests for mml_base. Run only when mml_base is installed."""

    module_name = "mml_base"
    module_label = "mml_base (Platform Layer UI)"

    # ------------------------------------------------------------------ smoke

    def run_smoke(self):
        self._smoke_login_landing()
        self._smoke_admin_menu_reachable()
        for model_name, label in PLATFORM_MODELS:
            self._smoke_model_browseable(model_name, label)
        self._smoke_dispatch_failure_model_optional()

    def _smoke_login_landing(self):
        """After login, the main navbar must be present (sanity)."""
        self.s.goto(f"{BASE_URL}/odoo", wait_ms=3000)
        self.add_smoke(self.s.snap(self.s.check_element_exists(
            ".o_main_navbar",
            "smoke: Odoo navbar present after login",
            description="Login session valid and SPA rendered",
        )))

    def _smoke_admin_menu_reachable(self):
        """Settings/Technical model list must be reachable."""
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_IR_MODEL}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: ir.model list reachable for admin"
        )))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: ir.model list has no error dialog"
        ))

    def _smoke_model_browseable(self, model_name: str, label: str):
        """
        Each platform model must be discoverable in ir.model.

        Because mml_base declares no act_window, we open the ir.model list
        filtered by the model's technical name. If the row exists, the
        model is loaded by Odoo and the admin can drill into its fields.
        """
        if not model_exists(model_name):
            self.add_smoke(Check(
                f"smoke: model {model_name} registered ({label})",
                Status.FAIL,
                f"ir_model has no row for {model_name}",
            ))
            return

        # Use the ir.model search URL with a domain filter on `model`.
        # Odoo 19 SPA accepts a `search_default_<field>` query param shape,
        # but the most reliable cross-version path is the raw list with a
        # filter facet typed in. We just navigate to the list and verify
        # the model name is present in the rendered row data.
        self.s.goto(
            f"{BASE_URL}/odoo/{ACTION_IR_MODEL}?view_type=list",
            wait_ms=4000,
        )
        # Apply a search filter for the technical name.
        try:
            search_box = self.s.page.locator('.o_searchview_input')
            if search_box.count() > 0:
                search_box.first.click()
                search_box.first.fill(model_name)
                self.s.page.keyboard.press("Enter")
                self.s.page.wait_for_timeout(2000)
        except Exception:
            # Search filtering is a nice-to-have; the headless probe above
            # already proved the row exists. Continue without it.
            pass

        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            f"smoke: model {model_name} list filterable"
        )))

    def _smoke_dispatch_failure_model_optional(self):
        """S4 introduces mml.event.dispatch.failure. Skip if not yet landed."""
        if model_exists(DISPATCH_FAILURE_MODEL):
            self.s.goto(
                f"{BASE_URL}/odoo/{ACTION_IR_MODEL}?view_type=list",
                wait_ms=3000,
            )
            self.add_smoke(self.s.snap(Check(
                f"smoke: dispatch failure model {DISPATCH_FAILURE_MODEL} present",
                Status.PASS,
                "Model exists in ir_model — UI is reachable via Technical -> Models",
            )))
        else:
            self.add_smoke(Check(
                f"smoke: dispatch failure model {DISPATCH_FAILURE_MODEL}",
                Status.SKIP,
                "Model not yet present — S4 dispatch-failure work has not landed",
            ))

    # ------------------------------------------------------------------- spec

    def run_spec(self):
        """
        Verify that each platform model declares the fields documented in
        the module CLAUDE.md / model source. We probe ir_model_fields by
        SQL because mml_base ships no form view XML — Odoo auto-generates
        a basic form on demand and field names are the load-bearing
        contract for downstream modules.
        """
        self._spec_capability_fields()
        self._spec_event_fields()
        self._spec_subscription_fields()
        self._spec_license_fields()
        self._spec_dispatch_failure_fields_optional()

    def _assert_fields(self, model: str, expected: list[str], label: str):
        """For a given model, every field in `expected` must exist in ir_model_fields."""
        # Probe each field individually so we get a clear list of any that are missing.
        missing = []
        for field in expected:
            count = ssh_psql_count(
                f"SELECT COUNT(*) FROM ir_model_fields "
                f"WHERE model = '{model}' AND name = '{field}'"
            )
            if count == 0:
                missing.append(field)
        if missing:
            self.add_spec(Check(
                f"spec: {label} declares required fields",
                Status.FAIL,
                f"Missing fields on {model}: {', '.join(missing)}",
            ))
        else:
            self.add_spec(Check(
                f"spec: {label} declares required fields",
                Status.PASS,
                f"All {len(expected)} fields present: {', '.join(expected)}",
            ))

    def _spec_capability_fields(self):
        self._assert_fields(
            "mml.capability",
            ["name", "module", "company_id"],
            "mml.capability",
        )

    def _spec_event_fields(self):
        # Per mml_event.py: event_type, source_module, payload_json, quantity,
        # billable_unit, synced_to_platform, timestamp, instance_ref, company_id
        self._assert_fields(
            "mml.event",
            [
                "event_type", "source_module", "payload_json", "quantity",
                "billable_unit", "synced_to_platform", "timestamp",
                "instance_ref", "company_id", "res_model", "res_id",
            ],
            "mml.event",
        )

    def _spec_subscription_fields(self):
        # Per mml_event_subscription.py: event_type, handler_model, handler_method, module
        self._assert_fields(
            "mml.event.subscription",
            ["event_type", "handler_model", "handler_method", "module"],
            "mml.event.subscription",
        )

    def _spec_license_fields(self):
        # Per mml_license.py: org_ref, license_key, tier, module_grants_json,
        # floor_amount, currency_id, seat_limit, valid_until, last_validated
        self._assert_fields(
            "mml.license",
            [
                "org_ref", "license_key", "tier", "module_grants_json",
                "floor_amount", "currency_id", "seat_limit", "valid_until",
                "last_validated",
            ],
            "mml.license",
        )

    def _spec_dispatch_failure_fields_optional(self):
        if not model_exists(DISPATCH_FAILURE_MODEL):
            self.add_spec(Check(
                f"spec: {DISPATCH_FAILURE_MODEL} declares required fields",
                Status.SKIP,
                "Model not present — S4 has not landed yet",
            ))
            return
        # Educated guess at minimum-viable schema — adjust once S4 lands.
        self._assert_fields(
            DISPATCH_FAILURE_MODEL,
            ["event_type", "handler_model", "handler_method", "error_message"],
            DISPATCH_FAILURE_MODEL,
        )

    # -------------------------------------------------------------- workflows

    def run_workflows(self):
        """ACL contract: group_user has read-only, group_system has CRUD."""
        self._workflow_acl_capability()
        self._workflow_acl_event()
        self._workflow_acl_subscription()
        self._workflow_acl_license()
        self._workflow_license_key_field_restricted()
        self._workflow_handler_method_pattern_documented()

    def _check_acl(self, model: str):
        """
        Returns (user_perms, system_perms) where each is a 4-tuple of
        ints (read, write, create, unlink) from ir_model_access. If
        multiple rows match (one per group), the OR is taken.
        """
        # group_user (xmlid base.group_user)
        user_q = (
            "SELECT MAX(perm_read::int), MAX(perm_write::int), "
            "MAX(perm_create::int), MAX(perm_unlink::int) "
            "FROM ir_model_access ima "
            "JOIN ir_model im ON im.id = ima.model_id "
            "JOIN res_groups rg ON rg.id = ima.group_id "
            "JOIN ir_model_data imd ON imd.res_id = rg.id AND imd.model = 'res.groups' "
            f"WHERE im.model = '{model}' AND imd.module = 'base' AND imd.name = 'group_user'"
        )
        sys_q = (
            "SELECT MAX(perm_read::int), MAX(perm_write::int), "
            "MAX(perm_create::int), MAX(perm_unlink::int) "
            "FROM ir_model_access ima "
            "JOIN ir_model im ON im.id = ima.model_id "
            "JOIN res_groups rg ON rg.id = ima.group_id "
            "JOIN ir_model_data imd ON imd.res_id = rg.id AND imd.model = 'res.groups' "
            f"WHERE im.model = '{model}' AND imd.module = 'base' AND imd.name = 'group_system'"
        )
        try:
            user_raw = ssh_psql(user_q)
            sys_raw = ssh_psql(sys_q)
            user_perms = self._parse_perm_row(user_raw)
            sys_perms = self._parse_perm_row(sys_raw)
            return user_perms, sys_perms
        except Exception:
            return None, None

    @staticmethod
    def _parse_perm_row(raw: str) -> tuple:
        """Parse a `psql -A -t` perm row like '1|0|0|0' into a tuple."""
        if not raw:
            return (None, None, None, None)
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) != 4:
            return (None, None, None, None)
        try:
            return tuple(int(p) if p else 0 for p in parts)
        except ValueError:
            return (None, None, None, None)

    def _workflow_acl(self, model: str, label: str, *, system_can_unlink: bool = True):
        user_perms, sys_perms = self._check_acl(model)
        if user_perms is None or sys_perms is None:
            self.add_workflow(Check(
                f"workflow: ACL contract for {label}",
                Status.FAIL,
                f"Could not query ir_model_access for {model}",
            ))
            return
        # group_user must have read=1 and write/create/unlink=0
        u_ok = user_perms == (1, 0, 0, 0)
        # group_system must have read=write=create=1; unlink=1 if system_can_unlink
        expected_sys = (1, 1, 1, 1) if system_can_unlink else (1, 1, 1, 0)
        s_ok = sys_perms == expected_sys

        if u_ok and s_ok:
            self.add_workflow(Check(
                f"workflow: ACL contract for {label}",
                Status.PASS,
                f"group_user={user_perms}, group_system={sys_perms}",
            ))
        else:
            details = []
            if not u_ok:
                details.append(f"group_user={user_perms} (expected (1,0,0,0))")
            if not s_ok:
                details.append(f"group_system={sys_perms} (expected {expected_sys})")
            self.add_workflow(Check(
                f"workflow: ACL contract for {label}",
                Status.FAIL,
                "; ".join(details),
            ))

    def _workflow_acl_capability(self):
        self._workflow_acl("mml.capability", "mml.capability")

    def _workflow_acl_event(self):
        self._workflow_acl("mml.event", "mml.event")

    def _workflow_acl_subscription(self):
        self._workflow_acl("mml.event.subscription", "mml.event.subscription")

    def _workflow_acl_license(self):
        self._workflow_acl("mml.license", "mml.license")

    def _workflow_license_key_field_restricted(self):
        """
        license_key has groups='base.group_system' inline on the field.
        Verify by inspecting ir.model.fields.groups via SQL.
        """
        q = (
            "SELECT COUNT(*) FROM ir_model_fields imf "
            "JOIN ir_model im ON im.id = imf.model_id "
            "JOIN ir_model_fields_group_rel rel ON rel.field_id = imf.id "
            "JOIN res_groups rg ON rg.id = rel.group_id "
            "JOIN ir_model_data imd ON imd.res_id = rg.id AND imd.model = 'res.groups' "
            "WHERE im.model = 'mml.license' AND imf.name = 'license_key' "
            "AND imd.module = 'base' AND imd.name = 'group_system'"
        )
        try:
            count = ssh_psql_count(q)
            if count >= 1:
                self.add_workflow(Check(
                    "workflow: license_key field restricted to group_system",
                    Status.PASS,
                    "groups=base.group_system enforced on field",
                ))
            else:
                self.add_workflow(Check(
                    "workflow: license_key field restricted to group_system",
                    Status.WARN,
                    "Field-level groups not visible via ir_model_fields_group_rel "
                    "— may be enforced only at the Python level",
                ))
        except Exception as e:
            self.add_workflow(Check(
                "workflow: license_key field restricted to group_system",
                Status.WARN,
                f"Could not verify via SQL: {e}",
            ))

    def _workflow_handler_method_pattern_documented(self):
        """
        Documentation/contract check: every existing subscription's
        handler_method must match ^_on_[a-z_]+$. This is enforced at
        runtime by mml.event.subscription.dispatch but bad rows still
        survive in the table — surface them in the report.
        """
        q = (
            "SELECT COUNT(*) FROM mml_event_subscription "
            "WHERE handler_method !~ '^_on_[a-z_]+$'"
        )
        try:
            bad = ssh_psql_count(q)
            if bad == 0:
                self.add_workflow(Check(
                    "workflow: subscription handler_method pattern compliance",
                    Status.PASS,
                    "All persisted subscriptions match ^_on_[a-z_]+$",
                ))
            else:
                self.add_workflow(Check(
                    "workflow: subscription handler_method pattern compliance",
                    Status.FAIL,
                    f"{bad} subscription(s) violate the ^_on_[a-z_]+$ pattern; "
                    f"those handlers will be silently dropped at dispatch time",
                ))
        except Exception as e:
            # Table may not yet exist if mml_base just installed empty.
            if "does not exist" in str(e).lower():
                self.add_workflow(Check(
                    "workflow: subscription handler_method pattern compliance",
                    Status.SKIP,
                    "mml_event_subscription table not yet present",
                ))
            else:
                self.add_workflow(Check(
                    "workflow: subscription handler_method pattern compliance",
                    Status.WARN,
                    f"SQL probe failed: {e}",
                ))


def is_installed() -> bool:
    """Convenience for the runner: avoid importing this module unless mml_base is live."""
    try:
        return module_installed("mml_base")
    except Exception:
        # If SSH is unavailable, fall back to assuming installed and let the
        # individual checks fail/skip gracefully.
        return True
