"""
Shared SSH connection helper for MML deployment scripts.

Reads connection details from environment variables.
Copy .env.example to .env and fill in values before running any script.
Never commit .env to git.
"""
import os
import paramiko


def connect() -> paramiko.SSHClient:
    host = os.environ["MML_SSH_HOST"]
    user = os.environ["MML_SSH_USER"]
    password = os.environ["MML_SSH_PASSWORD"]

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.WarningPolicy())
    c.connect(host, username=user, password=password, timeout=30)
    c.get_transport().set_keepalive(30)
    return c


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120):
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
    """
    Run a command under sudo, piping the password via stdin.
    Safer than echo-piping: password never appears in remote process list,
    and no shell escaping issues with special characters in the password.
    """
    password = os.environ["MML_SSH_PASSWORD"]
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd} 2>&1", timeout=timeout)
    stdin.write(password + "\n")
    stdin.flush()
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def write_remote(client: paramiko.SSHClient, path: str, content: str) -> None:
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(content.encode("utf-8") if isinstance(content, str) else content)
    sftp.close()
