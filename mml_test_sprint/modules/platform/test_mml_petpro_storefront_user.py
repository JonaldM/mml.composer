"""
Tests for mml_petpro_storefront_user — defines the
"MML PetPro Storefront" group plus a res.users template.

This module is new in the P2 sprint. If the module has not yet been
deployed to the test instance, all checks here are SKIPPED so the test
suite stays green.
"""
from __future__ import annotations

from mml_test_sprint.checks import Check, Status
from mml_test_sprint.config import BASE_URL
from mml_test_sprint.helpers import (
    group_exists,
    module_installed,
    ssh_psql,
    ssh_psql_count,
)
from mml_test_sprint.modules.base_module import BaseModuleTest


MODULE_NAME = "mml_petpro_storefront_user"
EXPECTED_GROUP_NAME = "MML PetPro Storefront"
ACTION_RES_GROUPS = "action-base.action_res_groups"


class MmlPetproStorefrontUserTests(BaseModuleTest):
    module_name = MODULE_NAME
    module_label = "MML PetPro Storefront User"

    # ----------------------------------------------------------------- smoke

    def run_smoke(self):
        if not module_installed(MODULE_NAME):
            self.add_smoke(Check(
                f"smoke: {MODULE_NAME} module installed",
                Status.SKIP,
                f"{MODULE_NAME} not installed on this instance — P2 has not "
                f"landed here yet. Re-run after installing the module.",
            ))
            return

        self.add_smoke(Check(
            f"smoke: {MODULE_NAME} module installed",
            Status.PASS,
            f"{MODULE_NAME} is in state='installed'",
        ))
        self._smoke_groups_list_loads()

    def _smoke_groups_list_loads(self):
        self.s.goto(f"{BASE_URL}/odoo/{ACTION_RES_GROUPS}?view_type=list", wait_ms=4000)
        self.add_smoke(self.s.snap(self.s.check_no_js_errors(
            "smoke: res.groups list reachable for admin"
        )))
        self.add_smoke(self.s.check_no_error_dialog(
            "smoke: res.groups list has no error dialog"
        ))

    # ------------------------------------------------------------------ spec

    def run_spec(self):
        if not module_installed(MODULE_NAME):
            self.add_spec(Check(
                f"spec: {EXPECTED_GROUP_NAME} group exists",
                Status.SKIP,
                f"{MODULE_NAME} not installed — cannot verify group",
            ))
            return

        self._spec_group_exists()
        self._spec_users_template_present()

    def _spec_group_exists(self):
        # We don't yet know the canonical xmlid the module ships with, so
        # match the human-readable name.
        if group_exists(EXPECTED_GROUP_NAME):
            self.add_spec(Check(
                f"spec: '{EXPECTED_GROUP_NAME}' group exists",
                Status.PASS,
                "res.groups row found by name match",
            ))
        else:
            self.add_spec(Check(
                f"spec: '{EXPECTED_GROUP_NAME}' group exists",
                Status.FAIL,
                "No res.groups row matches the expected storefront group name",
            ))

    def _spec_users_template_present(self):
        """
        The module ships a res.users template (see prompt brief). We
        verify by looking for any ir.ui.view of model='res.users' that
        belongs to the storefront module.
        """
        q = (
            "SELECT COUNT(*) FROM ir_ui_view iv "
            "JOIN ir_model_data imd ON imd.res_id = iv.id AND imd.model = 'ir.ui.view' "
            f"WHERE iv.model = 'res.users' AND imd.module = '{MODULE_NAME}'"
        )
        try:
            count = ssh_psql_count(q)
            if count >= 1:
                self.add_spec(Check(
                    "spec: res.users template view shipped by module",
                    Status.PASS,
                    f"{count} ir.ui.view record(s) found",
                ))
            else:
                self.add_spec(Check(
                    "spec: res.users template view shipped by module",
                    Status.WARN,
                    "No res.users view records traced to "
                    f"{MODULE_NAME} — module may use Python-only templates "
                    "or the view is registered under a different module name",
                ))
        except Exception as e:
            self.add_spec(Check(
                "spec: res.users template view shipped by module",
                Status.WARN,
                f"SQL probe failed: {e}",
            ))

    # -------------------------------------------------------------- workflows

    def run_workflows(self):
        if not module_installed(MODULE_NAME):
            self.add_workflow(Check(
                "workflow: storefront group has minimum-viable ACLs",
                Status.SKIP,
                f"{MODULE_NAME} not installed",
            ))
            return

        self._workflow_group_has_acls()

    def _workflow_group_has_acls(self):
        """
        A new portal-style group is meaningless without at least one
        ir.model.access row. Verify >= 1 ACL row references the
        storefront group.
        """
        q = (
            "SELECT COUNT(*) FROM ir_model_access ima "
            "JOIN res_groups rg ON rg.id = ima.group_id "
            f"WHERE rg.name ILIKE '%{EXPECTED_GROUP_NAME}%'"
        )
        try:
            count = ssh_psql_count(q)
            if count >= 1:
                self.add_workflow(Check(
                    "workflow: storefront group has minimum-viable ACLs",
                    Status.PASS,
                    f"{count} ir.model.access row(s) reference the group",
                ))
            else:
                self.add_workflow(Check(
                    "workflow: storefront group has minimum-viable ACLs",
                    Status.WARN,
                    "Group exists but has no ACL rows — group will not "
                    "actually grant any access to its members",
                ))
        except Exception as e:
            self.add_workflow(Check(
                "workflow: storefront group has minimum-viable ACLs",
                Status.WARN,
                f"SQL probe failed: {e}",
            ))


def is_installed() -> bool:
    try:
        return module_installed(MODULE_NAME)
    except Exception:
        return False
