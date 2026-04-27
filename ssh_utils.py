"""
Shared SSH connection helper for MML deployment scripts.

Reads connection details from environment variables.
Copy ``.env.example`` to ``.env`` and fill in values before running any script.
Never commit ``.env`` to git.

Required env vars
-----------------
``MML_SSH_HOST``
    Hostname or IP address of the target server.
``MML_SSH_USER``
    Login username.

Authentication (one of, in priority order)
------------------------------------------
1. ``MML_SSH_PRIVATE_KEY_PATH=/path/to/key`` — preferred, Ed25519 key.
2. ``~/.ssh/id_ed25519`` — auto-detected if the env var is unset.
3. ``MML_SSH_USE_PASSWORD=1`` + ``MML_SSH_PASSWORD=...`` — legacy password
   fallback. Both vars MUST be set; ``MML_SSH_PASSWORD`` alone is ignored.

Host-key policy
---------------
By default, unknown SSH host keys are **rejected** (paramiko ``RejectPolicy``)
and host fingerprints are validated against ``~/.ssh/known_hosts``.

For first-bootstrap scenarios where the host is not yet in ``known_hosts``,
set ``MML_SSH_AUTO_ACCEPT_HOST=1`` to opt in to ``AutoAddPolicy`` for that
session only. Do not leave this set in production environments.

Migration note
--------------
If you previously used password auth with only ``MML_SSH_PASSWORD`` set, you
must now also export ``MML_SSH_USE_PASSWORD=1`` to keep the same behavior.
The recommended migration is to switch to key-based auth.
"""
import os
from pathlib import Path

import paramiko


def connect() -> paramiko.SSHClient:
    """Open a hardened SSH connection to the configured MML host.

    Returns
    -------
    paramiko.SSHClient
        A connected client with TCP keepalive enabled.

    Raises
    ------
    KeyError
        If ``MML_SSH_HOST`` or ``MML_SSH_USER`` is not set.
    RuntimeError
        If no authentication path is configured (no key found and password
        fallback not explicitly enabled).
    paramiko.SSHException
        Subclasses raised by paramiko, including
        ``paramiko.ssh_exception.SSHException`` when a host key is not in
        ``known_hosts`` and ``MML_SSH_AUTO_ACCEPT_HOST`` is not set.
    """
    host = os.environ["MML_SSH_HOST"]
    user = os.environ["MML_SSH_USER"]

    client = paramiko.SSHClient()
    client.load_system_host_keys()

    if os.environ.get("MML_SSH_AUTO_ACCEPT_HOST") == "1":
        # First-bootstrap only: accept and persist any host key on first sight.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        # Production default: refuse unknown hosts. The fingerprint must
        # already be present in ~/.ssh/known_hosts (loaded above).
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    key_path = os.environ.get("MML_SSH_PRIVATE_KEY_PATH")
    if not key_path:
        default_key = Path.home() / ".ssh" / "id_ed25519"
        if default_key.exists():
            key_path = str(default_key)

    if key_path:
        pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
        client.connect(host, username=user, pkey=pkey, timeout=30)
    elif os.environ.get("MML_SSH_USE_PASSWORD") == "1":
        password = os.environ["MML_SSH_PASSWORD"]
        client.connect(
            host,
            username=user,
            password=password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )
    else:
        raise RuntimeError(
            "No SSH auth configured. Set MML_SSH_PRIVATE_KEY_PATH (or place a "
            "key at ~/.ssh/id_ed25519), or set MML_SSH_USE_PASSWORD=1 + "
            "MML_SSH_PASSWORD for legacy password auth."
        )

    client.get_transport().set_keepalive(30)
    return client


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120):
    """Execute a non-sudo command and return ``(rc, stdout, stderr)``."""
    if not client.get_transport() or not client.get_transport().is_active():
        raise RuntimeError("SSH session dropped")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    err_clean = "\n".join(l for l in err.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def sudo_run(client: paramiko.SSHClient, cmd: str, timeout: int = 120):
    """Run a command under sudo, piping the password via stdin.

    Safer than echo-piping: the password never appears in the remote process
    list, and there are no shell-escaping issues with special characters.

    Requires ``MML_SSH_PASSWORD`` to be set (independent of the
    ``MML_SSH_USE_PASSWORD`` opt-in used for SSH auth — sudo always needs the
    password regardless of how the SSH connection itself is authenticated).
    """
    password = os.environ["MML_SSH_PASSWORD"]
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd} 2>&1", timeout=timeout)
    stdin.write(password + "\n")
    stdin.flush()
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    err_clean = "\n".join(l for l in err.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def write_remote(client: paramiko.SSHClient, path: str, content: str) -> None:
    """Upload ``content`` to ``path`` over SFTP. Creates or overwrites the file."""
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(content.encode("utf-8") if isinstance(content, str) else content)
    sftp.close()
