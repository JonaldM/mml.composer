"""Central configuration for MML test sprint."""
import os
from pathlib import Path

BASE_URL = "http://46.62.148.99:8090"
LOGIN_EMAIL = "jono@mml.co.nz"
LOGIN_PASSWORD = "test"
DATABASE = "mml_dev"

# SSH for DB queries
SSH_HOST = "46.62.148.99"
SSH_USER = "root"
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")

# Docker container names on server
DB_CONTAINER = "mml-dev-db"
DB_USER = "odoo"

# Output
RESULTS_DIR = Path(__file__).parent / "test_results"

# Browser
VIEWPORT_W = 1440
VIEWPORT_H = 900
HEADLESS = True

# Timeouts (ms)
NAV_TIMEOUT = 10_000   # page navigation
WAIT_TIMEOUT = 5_000   # element wait
