"""Headless checks for mml_base — platform layer (no UI)."""
import paramiko

from mml_test_sprint.config import SSH_HOST, SSH_USER, SSH_KEY, DB_CONTAINER, DB_USER, DATABASE
from mml_test_sprint.checks import Check, Status, ModuleResult


def _ssh_psql(query: str) -> str:
    """Run a psql query on dev DB via SSH. Returns stdout."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY, timeout=15)
    cmd = f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d {DATABASE} -t -c "{query}"'
    _, stdout, _ = ssh.exec_command(cmd, timeout=30)
    result = stdout.read().decode().strip()
    ssh.close()
    return result


def run_mml_base_checks() -> ModuleResult:
    """Run all mml_base headless checks and return a ModuleResult."""
    result = ModuleResult(
        module_name="mml_base",
        module_label="mml_base (Platform Layer)",
    )

    checks = [
        # Platform model existence
        ("mml.capability model exists",
         "SELECT COUNT(*) FROM ir_model WHERE model = 'mml.capability'", 1),
        ("mml.registry model exists",
         "SELECT COUNT(*) FROM ir_model WHERE model = 'mml.registry'", 1),
        ("mml.event model exists",
         "SELECT COUNT(*) FROM ir_model WHERE model = 'mml.event'", 1),
        # All 14 ROQ config params
        ("ROQ lead time param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.default_lead_time_days'", 1),
        ("ROQ service level param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.default_service_level'", 1),
        ("ROQ lookback weeks param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.lookback_weeks'", 1),
        ("ROQ review interval param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.default_review_interval_days'", 1),
        ("ROQ SMA window param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.sma_window_weeks'", 1),
        ("ROQ min N value param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.min_n_value'", 1),
        ("ROQ ABC dampener param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.abc_dampener_weeks'", 1),
        ("ROQ ABC trailing revenue param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.abc_trailing_revenue_weeks'", 1),
        ("ROQ LCL threshold param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.container_lcl_threshold_pct'", 1),
        ("ROQ max padding weeks param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.max_padding_weeks_cover'", 1),
        ("ROQ max pull days param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.max_pull_days'", 1),
        ("ROQ MOQ enforcement param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.enable_moq_enforcement'", 1),
        ("ROQ calendar consolidation window param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.calendar.consolidation_window_days'", 1),
        ("ROQ reschedule threshold param",
         "SELECT COUNT(*) FROM ir_config_parameter WHERE key = 'roq.calendar.reschedule_threshold_days'", 1),
        # Sequences
        ("SG sequence exists",
         "SELECT COUNT(*) FROM ir_sequence WHERE code = 'roq.shipment.group'", 1),
        ("ROQ run sequence exists",
         "SELECT COUNT(*) FROM ir_sequence WHERE code = 'roq.forecast.run'", 1),
    ]

    for name, query, expected in checks:
        try:
            value = _ssh_psql(query).strip()
            # psql -t output may have leading whitespace
            count = int(value.split()[-1]) if value else 0
            if count >= expected:
                result.smoke.append(Check(f"headless: {name}", Status.PASS, f"count={count}"))
            else:
                result.smoke.append(Check(f"headless: {name}", Status.FAIL,
                                          f"Expected {expected}, got {count}"))
        except Exception as e:
            result.smoke.append(Check(f"headless: {name}", Status.FAIL, str(e)))

    return result
