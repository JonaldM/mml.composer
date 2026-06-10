"""Skip the live-box test-sprint suite when its target env is not configured.

mml_test_sprint drives a LIVE Odoo instance over HTTP/SSH (see config.py). Its
test modules import config at the top level, and config fails closed when the
MML_TEST_* environment variables are unset — by design for the runner scripts,
but without this guard that import error breaks pytest COLLECTION for the
entire monorepo (`pytest -m "not odoo_integration"` from the repo root).
When the env is absent, ignore everything in this directory instead.
"""
import os

if not os.environ.get("MML_TEST_BASE_URL"):
    collect_ignore_glob = ["*"]
