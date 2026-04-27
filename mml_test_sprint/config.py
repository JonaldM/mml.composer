"""Central configuration for MML test sprint.

Defaults are the historical mml_dev box. Every value below honours an
environment-variable override so the harness can be retargeted (e.g. at
the Hetzner pre-prod replica ``MML_19_prod_test`` over Tailscale) without
editing this file. CLI flags wired into ``runner.main`` populate the
same env vars.
"""
import os
from pathlib import Path

BASE_URL = os.environ.get("MML_TEST_BASE_URL", "http://46.62.148.99:8090")
LOGIN_EMAIL = os.environ.get("MML_TEST_LOGIN_EMAIL", "jono@mml.co.nz")
LOGIN_PASSWORD = os.environ.get("MML_TEST_LOGIN_PASSWORD", "test")
DATABASE = os.environ.get("MML_TEST_DATABASE", "mml_dev")

# SSH for DB queries
SSH_HOST = os.environ.get("MML_TEST_SSH_HOST", "46.62.148.99")
SSH_USER = os.environ.get("MML_TEST_SSH_USER", "root")
SSH_KEY = os.path.expanduser(
    os.environ.get("MML_TEST_SSH_KEY", "~/.ssh/id_ed25519"))

# Docker container names on server
DB_CONTAINER = os.environ.get("MML_TEST_DB_CONTAINER", "mml-dev-db")
DB_USER = os.environ.get("MML_TEST_DB_USER", "odoo")

# Output
RESULTS_DIR = Path(__file__).parent / "test_results"

# Browser
VIEWPORT_W = 1440
VIEWPORT_H = 900
HEADLESS = os.environ.get("MML_TEST_HEADLESS", "1") not in ("0", "false", "False")

# Timeouts (ms)
NAV_TIMEOUT = int(os.environ.get("MML_TEST_NAV_TIMEOUT", "10000"))   # page navigation
WAIT_TIMEOUT = int(os.environ.get("MML_TEST_WAIT_TIMEOUT", "5000"))  # element wait
