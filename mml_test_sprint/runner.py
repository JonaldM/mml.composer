"""
MML Module Test Sprint — Main Entry Point

Usage:
    cd E:/ClaudeCode/projects/mml.odoo
    python -m mml_test_sprint.runner

Output:
    test_results/YYYY-MM-DD/report.html
"""
import sys
from datetime import datetime
from pathlib import Path

import paramiko

from mml_test_sprint.browser import BrowserSession
from mml_test_sprint.checks import ModuleResult, Status
from mml_test_sprint.config import (
    BASE_URL, DATABASE, RESULTS_DIR,
    SSH_HOST, SSH_USER, SSH_KEY, DB_CONTAINER, DB_USER
)
from mml_test_sprint.report import generate_html
from mml_test_sprint.modules.mml_roq_forecast import RoqForecastTests
from mml_test_sprint.modules.mml_barcode_registry import BarcodeRegistryTests
from mml_test_sprint.modules.mml_base_platform import run_mml_base_checks
# PW-C: data / forecasting / barcode module extensions
from mml_test_sprint.modules.data.mml_edi import EdiTests
from mml_test_sprint.modules.data.mml_barcode_registry_ext import BarcodeRegistryExtTests
from mml_test_sprint.modules.data.mml_forecast_core import ForecastCoreTests
from mml_test_sprint.modules.data.mml_forecast_financial import ForecastFinancialTests
from mml_test_sprint.modules.data.mml_roq_forecast_ext import RoqForecastExtTests


def get_installed_modules() -> set:
    """Query mml_dev DB via SSH to find which MML modules are installed."""
    mml_modules = [
        "mml_base", "mml_roq_forecast", "mml_roq_freight", "mml_freight_3pl",
        "mml_barcode_registry", "mml_freight", "mml_freight_dsv",
        "mml_edi", "mml_forecast_core", "mml_forecast_financial",
        "stock_3pl_core", "stock_3pl_mainfreight",
    ]
    names_sql = "', '".join(mml_modules)
    query = f"SELECT name FROM ir_module_module WHERE name IN ('{names_sql}') AND state = 'installed'"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY, timeout=15)
        cmd = f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d {DATABASE} -t -c "{query}"'
        _, stdout, _ = ssh.exec_command(cmd, timeout=30)
        rows = stdout.read().decode().strip().splitlines()
        ssh.close()
        installed = {r.strip() for r in rows if r.strip()}
        print(f"Installed MML modules: {sorted(installed)}")
        return installed
    except Exception as e:
        print(f"WARNING: Could not query installed modules ({e}). Assuming all.")
        return set(mml_modules)


def not_installed_result(name: str, label: str) -> ModuleResult:
    r = ModuleResult(module_name=name, module_label=label, installed=False)
    return r


def main():
    print("\n" + "=" * 70)
    print("  MML Module Test Sprint")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Server: {BASE_URL}  |  DB: {DATABASE}")
    print("=" * 70)

    installed = get_installed_modules()
    results = []

    # ── mml_base headless checks (no browser needed) ────────────────────────
    print("\n[mml_base] Running headless DB checks...")
    if "mml_base" in installed:
        results.append(run_mml_base_checks())
    else:
        results.append(not_installed_result("mml_base", "mml_base (Platform Layer)"))

    # ── Browser-based module tests ───────────────────────────────────────────
    session = BrowserSession()
    try:
        session.start()
        session.login()
        print("  Browser: logged in")

        browser_modules = [
            ("mml_roq_forecast", "ROQ Forecast", RoqForecastTests),
            ("mml_barcode_registry", "Barcode Registry", BarcodeRegistryTests),
            # PW-C additions (data / forecasting / barcode extensions).
            # Each maps to an installed Odoo module on the test target;
            # gated by the same `installed` set as the existing modules.
            ("mml_edi", "EDI Engine", EdiTests),
            ("mml_barcode_registry", "Barcode Registry (extended)", BarcodeRegistryExtTests),
            ("mml_forecast_core", "Forecast Core", ForecastCoreTests),
            ("mml_forecast_financial", "Forecast Financial", ForecastFinancialTests),
            ("mml_roq_forecast", "ROQ Forecast (extended)", RoqForecastExtTests),
        ]

        for module_name, label, TestClass in browser_modules:
            if module_name in installed:
                test = TestClass(session)
                results.append(test.run())
            else:
                results.append(not_installed_result(module_name, label))

    finally:
        session.stop()

    # ── Report ───────────────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = RESULTS_DIR / date_str / "report.html"
    generate_html(results, output_path, BASE_URL, DATABASE)

    # Print summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for r in results:
        if r.installed:
            print(f"  {r.module_label:<30} {r.overall_status.value.upper():<8} "
                  f"smoke={r.smoke_score} spec={r.spec_score} wf={r.workflow_score}")
        else:
            print(f"  {r.module_label:<30} NOT INSTALLED")
    print(f"\n  Report: {output_path}")
    print("=" * 70 + "\n")

    # Exit 1 if any failures
    has_failures = any(
        r.installed and r.overall_status == Status.FAIL
        for r in results
    )
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
