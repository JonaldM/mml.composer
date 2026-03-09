"""
Remote installer: installs mml_base into MML_EDI_Compat on 10.0.0.35.
Run with: python scripts/install_mml_base_remote.py
"""

import paramiko
import time
import sys

SSH_HOST = "10.0.0.35"
SSH_USER = "jono"
SSH_PASS = "Lockitdown456"
SUDO_CMD = "echo 'Lockitdown456' | sudo -S"

ODOO_BIN = "/opt/odoo19/odoo-bin"
ODOO_CONF = "/etc/odoo/odoo19.conf"
TARGET_DB = "MML_EDI_Compat"
REPO_URL = "https://github.com/JonaldM/mml.composer.git"
REPO_DIR = "/tmp/mml_compat_repo"
ADDONS_DIR = "/tmp/mml_compat"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    c.get_transport().set_keepalive(30)
    return c


def run(client, cmd, timeout=120):
    transport = client.get_transport()
    if not transport or not transport.is_active():
        raise RuntimeError("SSH session dropped")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    err_clean = "\n".join(l for l in err.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Step 1: Check / clean up old SFTP-uploaded files
# ---------------------------------------------------------------------------
section("Step 1: Clean up old files in /tmp/mml_compat")
client = connect()

rc, out, err = run(client, "ls -la /tmp/mml_compat/ 2>&1 || echo 'DIR_MISSING'")
print("Existing /tmp/mml_compat:", out)

rc, out, err = run(client, "rm -rf /tmp/mml_compat/mml_base /tmp/mml_compat/mml_edi 2>&1")
print("Cleanup rc:", rc, "| out:", out or "(none)", "| err:", err or "(none)")

client.close()

# ---------------------------------------------------------------------------
# Step 2: Clone or pull the repo
# ---------------------------------------------------------------------------
section("Step 2: Clone / update repo")
client = connect()

rc, out, err = run(client, f"test -d {REPO_DIR}/.git && echo EXISTS || echo MISSING")
repo_state = out.strip()
print("Repo state:", repo_state)

if "EXISTS" in repo_state:
    print("Repo already cloned — pulling latest...")
    rc, out, err = run(client, f"cd {REPO_DIR} && git pull origin master 2>&1", timeout=120)
else:
    print("Cloning repo...")
    rc, out, err = run(
        client,
        f"git clone --depth 1 {REPO_URL} {REPO_DIR} 2>&1",
        timeout=180,
    )

print(f"git rc={rc}")
print("stdout:", out[-500:] if out else "(none)")
print("stderr:", err[-200:] if err else "(none)")

if rc != 0:
    print("ERROR: git clone/pull failed. Aborting.")
    client.close()
    sys.exit(1)

client.close()

# ---------------------------------------------------------------------------
# Step 3: Verify repo structure before symlinking
# ---------------------------------------------------------------------------
section("Step 3: Verify repo structure")
client = connect()

rc, out, err = run(client, f"ls {REPO_DIR}/")
print("Repo top-level dirs:", out)

# Check for mml_base and mml.edi (note: repo uses mml.edi, not mml_edi)
rc_mb, out_mb, _ = run(client, f"test -d {REPO_DIR}/mml_base && echo FOUND || echo MISSING")
rc_me, out_me, _ = run(client, f"ls {REPO_DIR}/ | grep -E '^mml.edi$|^mml_edi$' || echo MISSING")
print(f"mml_base: {out_mb.strip()}")
print(f"mml_edi dir in repo: {out_me.strip() or 'MISSING'}")

client.close()

# ---------------------------------------------------------------------------
# Step 4: Set up symlinks
# ---------------------------------------------------------------------------
section("Step 4: Set up symlinks in /tmp/mml_compat")
client = connect()

run(client, f"mkdir -p {ADDONS_DIR}")

rc1, o1, e1 = run(client, f"ln -sfn {REPO_DIR}/mml_base {ADDONS_DIR}/mml_base")
print(f"mml_base symlink rc={rc1}", "| err:", e1 or "(none)")

# Handle both mml.edi and mml_edi directory names in the repo
rc_check, out_check, _ = run(client, f"test -d {REPO_DIR}/mml.edi && echo DOT || test -d {REPO_DIR}/mml_edi && echo UNDER || echo NEITHER")
edi_dir_style = out_check.strip()
print(f"mml_edi dir style in repo: {edi_dir_style}")

if edi_dir_style == "DOT":
    src_edi = f"{REPO_DIR}/mml.edi"
elif edi_dir_style == "UNDER":
    src_edi = f"{REPO_DIR}/mml_edi"
else:
    print("WARNING: mml_edi directory not found in repo — skipping mml_edi symlink")
    src_edi = None

if src_edi:
    rc2, o2, e2 = run(client, f"ln -sfn {src_edi} {ADDONS_DIR}/mml_edi")
    print(f"mml_edi symlink rc={rc2}", "| err:", e2 or "(none)")
else:
    rc2 = 0

print(f"symlinks rc={rc1},{rc2}")

rc, out, _ = run(client, f"ls -la {ADDONS_DIR}/")
print(out)

client.close()

# ---------------------------------------------------------------------------
# Step 5: Check / update addons_path
# ---------------------------------------------------------------------------
section("Step 5: Check addons_path in odoo19.conf")
client = connect()

rc, out, err = run(client, f"grep addons_path {ODOO_CONF}")
print("Current addons_path:", out)

if ADDONS_DIR not in out:
    print(f"{ADDONS_DIR} not in addons_path — adding it...")
    rc, out, err = run(
        client,
        f"echo 'Lockitdown456' | sudo -S sed -i '/^addons_path/s|$|,{ADDONS_DIR}|' {ODOO_CONF} 2>&1",
    )
    print(f"sed rc={rc}", "| out:", out or "(none)", "| err:", err or "(none)")

    rc, out, _ = run(client, f"grep addons_path {ODOO_CONF}")
    print("Updated addons_path:", out)
else:
    print(f"{ADDONS_DIR} already in addons_path — no change needed.")

client.close()

# ---------------------------------------------------------------------------
# Step 6: Stop odoo19 service
# ---------------------------------------------------------------------------
section("Step 6: Stop odoo19.service")
client = connect()

rc, out, err = run(client, f"{SUDO_CMD} systemctl stop odoo19.service 2>&1")
print(f"stop rc={rc}", "| out:", out or "(none)", "| err:", err or "(none)")

time.sleep(3)

rc, out, _ = run(client, f"{SUDO_CMD} systemctl is-active odoo19.service 2>&1")
status = out.strip()
print(f"service status: {status}")

if status not in ("inactive", "failed", "activating"):
    print(f"WARNING: service may still be running (status='{status}') — continuing anyway")

client.close()

# ---------------------------------------------------------------------------
# Step 7: Run install (up to 5 minutes)
# ---------------------------------------------------------------------------
section("Step 7: Install mml_base into MML_EDI_Compat")
print("This may take 2-5 minutes...")

client = connect()

cmd = (
    f"echo 'Lockitdown456' | sudo -S {ODOO_BIN} "
    f"-c {ODOO_CONF} -i mml_base -d {TARGET_DB} --stop-after-init 2>&1"
)

rc_install, out_install, err_install = run(client, cmd, timeout=400)
print(f"install rc={rc_install}")

combined = out_install + ("\n" + err_install if err_install else "")
print("\n--- INSTALL OUTPUT (last 6000 chars) ---")
print(combined[-6000:])
print("--- END INSTALL OUTPUT ---")

client.close()

# ---------------------------------------------------------------------------
# Step 8: Restart odoo19 service
# ---------------------------------------------------------------------------
section("Step 8: Restart odoo19.service")
client = connect()

rc, out, err = run(client, f"{SUDO_CMD} systemctl start odoo19.service 2>&1")
print(f"start rc={rc}", "| out:", out or "(none)", "| err:", err or "(none)")

time.sleep(5)

rc, out, _ = run(client, f"{SUDO_CMD} systemctl is-active odoo19.service 2>&1")
service_status = out.strip()
print(f"service status after restart: {service_status}")

client.close()

# ---------------------------------------------------------------------------
# Step 9: Analyse and report
# ---------------------------------------------------------------------------
section("Step 9: Result Analysis")

SUCCESS_MARKERS = ["Modules loaded.", "modules loaded"]
FAILURE_MARKERS = [
    "ValueError", "TypeError", "ImportError", "AttributeError",
    "ERROR odoo", "Traceback (most recent call last)", "odoo.exceptions",
]

install_success = any(m.lower() in combined.lower() for m in SUCCESS_MARKERS)
errors_found = [m for m in FAILURE_MARKERS if m in combined]

if install_success and not errors_found:
    print("RESULT: PASS")
    print("  mml_base installed successfully into MML_EDI_Compat.")
elif install_success and errors_found:
    print("RESULT: PASS WITH WARNINGS")
    print(f"  Modules loaded, but error markers found: {errors_found}")
else:
    print("RESULT: FAIL")
    print(f"  Error markers found: {errors_found}")

    # Find first error / traceback in output
    lines = combined.splitlines()
    for i, line in enumerate(lines):
        if any(m in line for m in FAILURE_MARKERS):
            start = max(0, i - 3)
            end = min(len(lines), i + 40)
            print("\n--- First error context ---")
            print("\n".join(lines[start:end]))
            print("--- End error context ---")
            break

print(f"\nOdoo service status: {service_status}")
if service_status == "active":
    print("Service is UP.")
else:
    print(f"WARNING: Service status is '{service_status}' — may need manual intervention.")

print()
print("Done.")
