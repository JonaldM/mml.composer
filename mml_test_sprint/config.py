"""Central configuration for MML test sprint.

SECURITY: this harness used to ship hardcoded defaults for the target box —
its IP/URL, the login email, the login password ("test"), and the SSH host/user.
Those have been removed. Every value below is now read from an environment
variable and there is NO in-file default for any secret or target-identifying
value: if a required variable is unset the harness fails closed with a clear
message rather than silently pointing at the old mml_dev box.

Set these before running (e.g. export / a local .env you do not commit, or the
CLI flags wired into ``runner.main`` which populate the same env vars):

    MML_TEST_BASE_URL        e.g. http://<host>:8090
    MML_TEST_LOGIN_EMAIL     e.g. you@example.com
    MML_TEST_LOGIN_PASSWORD  the Odoo login password (secret)
    MML_TEST_DATABASE        e.g. mml_dev
    MML_TEST_SSH_HOST        host used for DB queries over SSH
    MML_TEST_SSH_USER        SSH user
    MML_TEST_SSH_KEY         path to the SSH private key (default: ~/.ssh/id_ed25519)
    MML_TEST_DB_CONTAINER    docker container name of the DB
    MML_TEST_DB_USER         postgres role

NOTE: this directory has NO __manifest__.py and is NOT an Odoo addon. It must be
kept OUT of any Odoo ``addons_path`` — it is a standalone test runner only.
"""
import os
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when a required configuration environment variable is unset."""


def _require_env(name: str) -> str:
    """Return os.environ[name] or raise a clear, actionable error if unset/empty.

    No defaults: a missing target/credential must fail closed rather than fall
    back to a baked-in value.
    """
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Required environment variable {name!r} is not set. "
            f"The MML test-sprint harness no longer ships hardcoded host/credential "
            f"defaults — set {name} (and the other MML_TEST_* vars) before running. "
            f"See the module docstring in mml_test_sprint/config.py for the full list."
        )
    return value


BASE_URL = _require_env("MML_TEST_BASE_URL")
LOGIN_EMAIL = _require_env("MML_TEST_LOGIN_EMAIL")
LOGIN_PASSWORD = _require_env("MML_TEST_LOGIN_PASSWORD")
DATABASE = _require_env("MML_TEST_DATABASE")

# SSH for DB queries
SSH_HOST = _require_env("MML_TEST_SSH_HOST")
SSH_USER = _require_env("MML_TEST_SSH_USER")
# The key *path* is not itself a secret; a conventional default location is fine.
SSH_KEY = os.path.expanduser(
    os.environ.get("MML_TEST_SSH_KEY", "~/.ssh/id_ed25519"))

# Docker container names on server
DB_CONTAINER = _require_env("MML_TEST_DB_CONTAINER")
DB_USER = _require_env("MML_TEST_DB_USER")

# Output
RESULTS_DIR = Path(__file__).parent / "test_results"

# Browser
VIEWPORT_W = 1440
VIEWPORT_H = 900
HEADLESS = os.environ.get("MML_TEST_HEADLESS", "1") not in ("0", "false", "False")

# Timeouts (ms)
NAV_TIMEOUT = int(os.environ.get("MML_TEST_NAV_TIMEOUT", "10000"))   # page navigation
WAIT_TIMEOUT = int(os.environ.get("MML_TEST_WAIT_TIMEOUT", "5000"))  # element wait
