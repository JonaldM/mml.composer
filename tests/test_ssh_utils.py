"""Unit tests for ssh_utils.connect() — auth path, host-key policy, and migration.

All tests mock paramiko so no real SSH connection is attempted.
"""
import os
import sys
import importlib
from unittest import mock

import pytest


# Ensure repo root is on sys.path so `import ssh_utils` works regardless of
# the directory pytest was invoked from.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every MML_SSH_* env var so each test starts from a known state."""
    for key in list(os.environ):
        if key.startswith("MML_SSH_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def ssh_utils_module():
    """Import ssh_utils fresh for each test (avoids cached module state)."""
    if "ssh_utils" in sys.modules:
        del sys.modules["ssh_utils"]
    import ssh_utils  # noqa: WPS433  — intentional late import after sys.path setup
    return ssh_utils


def _make_mock_client():
    """Return a mock SSHClient instance with a working transport."""
    client = mock.MagicMock()
    transport = mock.MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    return client


# ---------------------------------------------------------------------------
# Host-key policy
# ---------------------------------------------------------------------------


def test_connect_uses_reject_policy_by_default(clean_env, ssh_utils_module, tmp_path):
    """Default behavior must reject unknown host keys."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("dummy")
    clean_env.setenv("MML_SSH_PRIVATE_KEY_PATH", str(key_file))

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client), \
         mock.patch.object(
             ssh_utils_module.paramiko.Ed25519Key,
             "from_private_key_file",
             return_value=mock.MagicMock(),
         ):
        ssh_utils_module.connect()

    # Last call to set_missing_host_key_policy must use a RejectPolicy instance
    args, _ = mock_client.set_missing_host_key_policy.call_args
    assert isinstance(args[0], ssh_utils_module.paramiko.RejectPolicy), (
        "Default host-key policy must be RejectPolicy"
    )


def test_connect_uses_auto_add_policy_when_opt_in(clean_env, ssh_utils_module, tmp_path):
    """Setting MML_SSH_AUTO_ACCEPT_HOST=1 must switch to AutoAddPolicy."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    clean_env.setenv("MML_SSH_AUTO_ACCEPT_HOST", "1")
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("dummy")
    clean_env.setenv("MML_SSH_PRIVATE_KEY_PATH", str(key_file))

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client), \
         mock.patch.object(
             ssh_utils_module.paramiko.Ed25519Key,
             "from_private_key_file",
             return_value=mock.MagicMock(),
         ):
        ssh_utils_module.connect()

    args, _ = mock_client.set_missing_host_key_policy.call_args
    assert isinstance(args[0], ssh_utils_module.paramiko.AutoAddPolicy), (
        "Opt-in MML_SSH_AUTO_ACCEPT_HOST=1 must use AutoAddPolicy"
    )


def test_connect_loads_system_host_keys(clean_env, ssh_utils_module, tmp_path):
    """Host fingerprint validation requires loading ~/.ssh/known_hosts."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("dummy")
    clean_env.setenv("MML_SSH_PRIVATE_KEY_PATH", str(key_file))

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client), \
         mock.patch.object(
             ssh_utils_module.paramiko.Ed25519Key,
             "from_private_key_file",
             return_value=mock.MagicMock(),
         ):
        ssh_utils_module.connect()

    mock_client.load_system_host_keys.assert_called_once()


# ---------------------------------------------------------------------------
# Key-based auth (preferred path)
# ---------------------------------------------------------------------------


def test_connect_uses_explicit_private_key_path(clean_env, ssh_utils_module, tmp_path):
    """When MML_SSH_PRIVATE_KEY_PATH is set, that key must be used."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    key_file = tmp_path / "explicit_key"
    key_file.write_text("dummy")
    clean_env.setenv("MML_SSH_PRIVATE_KEY_PATH", str(key_file))

    mock_client = _make_mock_client()
    fake_pkey = mock.MagicMock(name="Ed25519Key")
    with mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client), \
         mock.patch.object(
             ssh_utils_module.paramiko.Ed25519Key,
             "from_private_key_file",
             return_value=fake_pkey,
         ) as mock_load_key:
        ssh_utils_module.connect()

    mock_load_key.assert_called_once_with(str(key_file))
    _, kwargs = mock_client.connect.call_args
    assert kwargs["pkey"] is fake_pkey
    assert kwargs["username"] == "deploy"
    assert kwargs.get("password") in (None, "")  # No password should leak in


def test_connect_falls_back_to_default_key_path(clean_env, ssh_utils_module, tmp_path):
    """When no env var set, ~/.ssh/id_ed25519 should be used if it exists."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")

    fake_home = tmp_path / "home"
    (fake_home / ".ssh").mkdir(parents=True)
    default_key = fake_home / ".ssh" / "id_ed25519"
    default_key.write_text("dummy")

    mock_client = _make_mock_client()
    fake_pkey = mock.MagicMock(name="Ed25519Key")
    with mock.patch.object(ssh_utils_module.Path, "home", return_value=fake_home), \
         mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client), \
         mock.patch.object(
             ssh_utils_module.paramiko.Ed25519Key,
             "from_private_key_file",
             return_value=fake_pkey,
         ) as mock_load_key:
        ssh_utils_module.connect()

    mock_load_key.assert_called_once_with(str(default_key))


# ---------------------------------------------------------------------------
# Password fallback (must be opt-in)
# ---------------------------------------------------------------------------


def test_connect_uses_password_when_explicitly_enabled(clean_env, ssh_utils_module, tmp_path):
    """MML_SSH_USE_PASSWORD=1 + MML_SSH_PASSWORD must enable password auth."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    clean_env.setenv("MML_SSH_USE_PASSWORD", "1")
    clean_env.setenv("MML_SSH_PASSWORD", "s3cret")

    # Force the default key path lookup to return a non-existent file
    fake_home = tmp_path / "no-keys"
    fake_home.mkdir()

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.Path, "home", return_value=fake_home), \
         mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client):
        ssh_utils_module.connect()

    _, kwargs = mock_client.connect.call_args
    assert kwargs["password"] == "s3cret"
    assert kwargs.get("pkey") is None
    assert kwargs.get("look_for_keys") is False
    assert kwargs.get("allow_agent") is False


def test_connect_raises_without_password_opt_in(clean_env, ssh_utils_module, tmp_path):
    """MML_SSH_PASSWORD alone must NOT trigger password auth — opt-in required."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")
    clean_env.setenv("MML_SSH_PASSWORD", "s3cret")
    # Note: MML_SSH_USE_PASSWORD intentionally NOT set

    fake_home = tmp_path / "no-keys"
    fake_home.mkdir()

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.Path, "home", return_value=fake_home), \
         mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="No SSH auth configured"):
            ssh_utils_module.connect()


def test_connect_raises_when_no_auth_at_all(clean_env, ssh_utils_module, tmp_path):
    """No key, no password opt-in → clear error message."""
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    clean_env.setenv("MML_SSH_USER", "deploy")

    fake_home = tmp_path / "empty"
    fake_home.mkdir()

    mock_client = _make_mock_client()
    with mock.patch.object(ssh_utils_module.Path, "home", return_value=fake_home), \
         mock.patch.object(ssh_utils_module.paramiko, "SSHClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="No SSH auth configured"):
            ssh_utils_module.connect()


# ---------------------------------------------------------------------------
# Required env vars
# ---------------------------------------------------------------------------


def test_connect_raises_when_host_missing(clean_env, ssh_utils_module):
    clean_env.setenv("MML_SSH_USER", "deploy")
    with pytest.raises(KeyError):
        ssh_utils_module.connect()


def test_connect_raises_when_user_missing(clean_env, ssh_utils_module):
    clean_env.setenv("MML_SSH_HOST", "host.example.com")
    with pytest.raises(KeyError):
        ssh_utils_module.connect()
