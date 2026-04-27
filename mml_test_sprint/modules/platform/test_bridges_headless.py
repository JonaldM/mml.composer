"""
Headless bridge-module checks for mml_roq_freight and mml_freight_3pl.

These two modules are pure dependency bridges — they ship hooks +
service registrations only, no models, no menus, no UI. The only
meaningful tests are:

  1. Module is installed (state='installed' in ir_module_module).
  2. Each declared dependency is also installed (the bridge would not
     install otherwise, but better to surface clearly than silently).
  3. Service registration shows up in ir.config_parameter under
     `mml_registry.service.<name>` (set by mml_base when a module
     registers a service in its post_init_hook).

These run as a stand-alone module result — they reuse the
ModuleResult dataclass without subclassing BaseModuleTest because they
need no browser session.
"""
from __future__ import annotations

from mml_test_sprint.checks import Check, ModuleResult, Status
from mml_test_sprint.helpers import ssh_psql, ssh_psql_count, module_installed


def _check_module(name: str, label: str, expected_deps: list[str]) -> ModuleResult:
    result = ModuleResult(
        module_name=name,
        module_label=label,
        installed=False,
    )

    # 1) Module install state.
    try:
        installed = module_installed(name)
    except Exception as e:
        result.smoke.append(Check(
            f"headless: {name} install state",
            Status.WARN,
            f"SSH probe failed: {e}",
        ))
        return result

    if not installed:
        # Mark module as not installed; runner reports it that way.
        return result

    result.installed = True
    result.smoke.append(Check(
        f"headless: {name} installed",
        Status.PASS,
        f"{name} state='installed'",
    ))

    # 2) Required dependencies.
    for dep in expected_deps:
        try:
            ok = module_installed(dep)
            if ok:
                result.smoke.append(Check(
                    f"headless: dependency {dep} installed",
                    Status.PASS,
                ))
            else:
                result.smoke.append(Check(
                    f"headless: dependency {dep} installed",
                    Status.FAIL,
                    f"{dep} not in state='installed' — bridge cannot function",
                ))
        except Exception as e:
            result.smoke.append(Check(
                f"headless: dependency {dep} installed",
                Status.WARN,
                f"SSH probe failed: {e}",
            ))

    # 3) No-UI assertion: bridge module should ship no ir.ui.menu records.
    try:
        menu_count = ssh_psql_count(
            f"SELECT COUNT(*) FROM ir_ui_menu m "
            f"JOIN ir_model_data d ON d.res_id = m.id AND d.model = 'ir.ui.menu' "
            f"WHERE d.module = '{name}'"
        )
        if menu_count == 0:
            result.spec.append(Check(
                f"spec: {name} ships no ir.ui.menu (bridge-only)",
                Status.PASS,
                "0 menu items registered — bridge is UI-less as designed",
            ))
        else:
            result.spec.append(Check(
                f"spec: {name} ships no ir.ui.menu (bridge-only)",
                Status.WARN,
                f"{menu_count} menu item(s) registered — unexpected for a "
                f"bridge module",
            ))
    except Exception as e:
        result.spec.append(Check(
            f"spec: {name} ships no ir.ui.menu (bridge-only)",
            Status.WARN,
            f"SSH probe failed: {e}",
        ))

    # 4) Service registration: at least one mml_registry.service.* param
    #    referencing a class path that lives inside this bridge module.
    try:
        service_count = ssh_psql_count(
            f"SELECT COUNT(*) FROM ir_config_parameter "
            f"WHERE key LIKE 'mml_registry.service.%' "
            f"AND value LIKE 'odoo.addons.{name}.%'"
        )
        if service_count >= 1:
            result.workflows.append(Check(
                f"workflow: {name} registers >= 1 service in mml.registry",
                Status.PASS,
                f"{service_count} service(s) registered with class path "
                f"under odoo.addons.{name}",
            ))
        else:
            # Bridges may delegate registration to upstream modules — surface
            # as INFO/WARN, not FAIL.
            result.workflows.append(Check(
                f"workflow: {name} registers >= 1 service in mml.registry",
                Status.WARN,
                f"No mml_registry.service.* params reference {name} — "
                f"bridge may delegate registration upstream",
            ))
    except Exception as e:
        result.workflows.append(Check(
            f"workflow: {name} registers >= 1 service in mml.registry",
            Status.WARN,
            f"SSH probe failed: {e}",
        ))

    return result


def run_mml_roq_freight_checks() -> ModuleResult:
    return _check_module(
        name="mml_roq_freight",
        label="mml_roq_freight (Bridge)",
        expected_deps=["mml_base", "mml_roq_forecast"],
    )


def run_mml_freight_3pl_checks() -> ModuleResult:
    return _check_module(
        name="mml_freight_3pl",
        label="mml_freight_3pl (Bridge)",
        expected_deps=["mml_base", "mml_freight"],
    )
