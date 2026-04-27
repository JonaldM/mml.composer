"""
Additive helpers shared across module test files.

This module is purely additive. It must not redefine any existing
function or class from the parent harness. Helpers here are utilities
the platform / freight / data agents may reuse.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import paramiko

from mml_test_sprint.config import (
    DATABASE,
    DB_CONTAINER,
    DB_USER,
    SSH_HOST,
    SSH_KEY,
    SSH_USER,
)
from mml_test_sprint.checks import Check, Status


def ssh_psql(query: str, *, timeout: int = 30) -> str:
    """
    Run a psql query on the dev DB via SSH and return stdout.

    Same shape as the private helper in mml_test_sprint.modules.mml_base_platform
    but exposed as a public utility so other modules can reuse it without
    importing private functions.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY, timeout=15)
    try:
        cmd = (
            f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d {DATABASE} '
            f'-t -A -c "{query}"'
        )
        _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
        return stdout.read().decode().strip()
    finally:
        ssh.close()


def ssh_psql_count(query: str) -> int:
    """Run a SELECT COUNT(*) query and return the integer result, or 0 on error."""
    raw = ssh_psql(query)
    if not raw:
        return 0
    try:
        return int(raw.split()[-1])
    except (ValueError, IndexError):
        return 0


def module_installed(module_name: str) -> bool:
    """Return True if the given Odoo module is in state='installed'."""
    q = (
        f"SELECT COUNT(*) FROM ir_module_module "
        f"WHERE name = '{module_name}' AND state = 'installed'"
    )
    try:
        return ssh_psql_count(q) >= 1
    except Exception:
        return False


def model_exists(model_name: str) -> bool:
    """Return True if the given Odoo model is registered in ir_model."""
    q = f"SELECT COUNT(*) FROM ir_model WHERE model = '{model_name}'"
    try:
        return ssh_psql_count(q) >= 1
    except Exception:
        return False


def group_exists(xml_id_or_name: str) -> bool:
    """
    Return True if a res.groups record exists. Accepts either an xmlid
    (module.name) or a literal name string.
    """
    if "." in xml_id_or_name:
        module, name = xml_id_or_name.split(".", 1)
        q = (
            f"SELECT COUNT(*) FROM ir_model_data "
            f"WHERE module = '{module}' AND name = '{name}' "
            f"AND model = 'res.groups'"
        )
    else:
        q = f"SELECT COUNT(*) FROM res_groups WHERE name ILIKE '%{xml_id_or_name}%'"
    try:
        return ssh_psql_count(q) >= 1
    except Exception:
        return False


def make_check(name: str, condition: bool, pass_detail: str = "", fail_detail: str = "") -> Check:
    """Convenience: build a Check from a boolean condition."""
    if condition:
        return Check(name, Status.PASS, pass_detail)
    return Check(name, Status.FAIL, fail_detail or "condition failed")


def env_override(key: str, default: str) -> str:
    """
    Return os.environ[key] if set (and non-empty), else the default.

    Used for letting the user override the default Hetzner test target
    via env vars without modifying config.py:
        MML_TEST_BASE_URL, MML_TEST_DATABASE, MML_TEST_LOGIN, MML_TEST_PASSWORD
    """
    val = os.environ.get(key, "").strip()
    return val if val else default
