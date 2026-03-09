# mml_edi Odoo 19 Compatibility Test Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install `mml_base` and `mml_edi` on a throwaway copy of the test database to verify Odoo 19 compatibility, then clean up completely without affecting Harold's work on `MML_Test_Odoo19_02102026`.

**Architecture:** Create a temporary PostgreSQL database (`MML_EDI_Compat`) cloned from the test DB, upload both modules to a temp directory on the server, install via `odoo-bin --stop-after-init`, capture all output, then drop the DB and remove the files. Harold's DB is never touched.

**Tech Stack:** Python + paramiko (SSH/SFTP), PostgreSQL 15, Odoo 19 (`/opt/odoo19/odoo-bin`), server at `10.0.0.35` (credentials in `ssh.txt`).

---

## Critical rules

- **NEVER touch `MML_Production`** — it is off-limits entirely.
- **NEVER modify `MML_Test_Odoo19_02102026`** — Harold is actively working there.
- All work targets `MML_EDI_Compat` only. Drop it at the end.
- If any step fails unexpectedly, stop and report before continuing.

---

## Context

### Server layout
- Odoo 19 binary: `/opt/odoo19/odoo-bin`
- Odoo 19 config: `/etc/odoo/odoo19.conf`
- Existing addons path: `/opt/odoo19/odoo/addons,/mnt/odoo-addons/enabling19,/mnt/odoo-addons/repos19/purchase-workflow`
- Temp addons dir we will create: `/tmp/mml_compat/`
- PostgreSQL 15, socket auth for `odoo` user, sudo -u postgres for admin ops

### Module dependency order
1. `mml_base` — depends on `mail`, `base` only (both installed)
2. `mml_edi` — depends on `mml_base`, `sale`, `account`, `stock`, `mail` (all installed)

### Local module paths
- `mml_base`: `mml_base/` at repo root (technical name = `mml_base`, dir name = `mml_base`)
- `mml_edi`: `mml.edi/` at repo root (technical name = `mml_edi`, dir name on server must be `mml_edi`)

### SSH notes
- `jono` has full sudo (`(ALL : ALL) ALL`) with password `Lockitdown456`. Use `echo 'Lockitdown456' | sudo -S <cmd>` for any privileged command.
- **The SSH connection can drop intermittently** (remote host closes socket mid-session). Always wrap multi-step scripts with reconnect logic: check `ssh.get_transport().is_active()` before each command; if not active, reconnect and retry. Set `keepalive` on the transport: `ssh.get_transport().set_keepalive(30)`.

### SSH helper (use throughout)
```python
import paramiko, sys

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('10.0.0.35', username='jono', password='Lockitdown456', timeout=15)
    c.get_transport().set_keepalive(30)
    return c

def run(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    out_clean = '\n'.join(l for l in out.splitlines() if not l.startswith('[sudo]'))
    return out_clean, err
```

---

## Task 1: Pre-flight checks

**Goal:** Confirm the server is in the expected state before doing anything.

**Files:** None — read-only checks.

**Step 1: Verify test DB exists and Harold's DB is untouched**
```python
client = ssh()
out, _ = run(client, "echo 'Lockitdown456' | sudo -S -u postgres psql -l 2>&1")
print(out)
client.close()
```
Expected: `MML_Test_Odoo19_02102026` listed. `MML_Production` listed. No `MML_EDI_Compat` yet.

**Step 2: Check disk space**
```python
client = ssh()
out, _ = run(client, "df -h /")
print(out)
client.close()
```
Expected: At least 10 GB free (DB clone ~5 GB + module files ~50 MB).
If less than 10 GB free, STOP and report.

**Step 3: Check Odoo 19 service is running**
```python
client = ssh()
out, _ = run(client, "echo 'Lockitdown456' | sudo -S systemctl is-active odoo19 2>&1")
print(out)
client.close()
```
Expected: `active`. If not active, report before continuing.

**Step 4: Confirm Harold's active connections (so we don't interrupt)**
```python
client = ssh()
out, _ = run(client, "echo 'Lockitdown456' | sudo -S -u postgres psql -c \"SELECT count(*) FROM pg_stat_activity WHERE datname='MML_Test_Odoo19_02102026';\" 2>&1")
print(out)
client.close()
```
Note the connection count. If > 15 active, flag it but continue (Harold may be running something).

---

## Task 2: Create the compat test database

**Goal:** pg_dump `MML_Test_Odoo19_02102026` and restore it as `MML_EDI_Compat`. This is the DB we will install modules into. Harold's DB is never touched after this point.

> **Note on timing:** The pg_dump takes ~2–5 minutes on a 4.8 GB DB. It runs against a live DB and does not lock it, so Harold can keep working. Just don't run this during peak business hours if possible.

**Step 1: Create the new empty database**
```python
client = ssh()
out, err = run(client, "echo 'Lockitdown456' | sudo -S -u postgres createdb -O odoo -E UTF8 MML_EDI_Compat 2>&1")
print(out, err)
client.close()
```
Expected: No error output. The DB is created.

**Step 2: Dump and restore (takes 2–5 min)**
```python
client = ssh()
# Dump to file first, then restore — more reliable than piping on a live DB
out, err = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres pg_dump MML_Test_Odoo19_02102026 -Fc -f /tmp/mml_compat_dump.pgc 2>&1",
    timeout=600
)
print("DUMP:", out[:500], err[:500])
client.close()
```
Expected: No errors. `/tmp/mml_compat_dump.pgc` exists on the server.

**Step 3: Restore into MML_EDI_Compat**
```python
client = ssh()
out, err = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres pg_restore -d MML_EDI_Compat /tmp/mml_compat_dump.pgc 2>&1",
    timeout=600
)
print("RESTORE:", out[:1000], err[:1000])
client.close()
```
Expected: Some warnings about `odoo` role ownership are normal. Fatal errors are not. If there are fatal errors, STOP.

**Step 4: Verify the restore**
```python
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat -c \"SELECT count(*) FROM ir_module_module WHERE state='installed';\" 2>&1"
)
print(out)
client.close()
```
Expected: A row count matching what the source DB has (~200+ installed modules). If 0, the restore failed.

**Step 5: Clean up the dump file**
```python
client = ssh()
run(client, "rm /tmp/mml_compat_dump.pgc")
client.close()
```

---

## Task 3: Clone repo on server

**Goal:** Clone `mml.composer` from GitHub directly on the server into `/tmp/mml_compat_repo/`. This avoids SFTP over the spotty connection. The repo is at `https://github.com/JonaldM/mml.composer.git`.

> **Why git clone instead of SFTP:** The SSH connection drops intermittently. Cloning from GitHub on the server itself is more reliable — GitHub has a stable connection from the server and git handles any resumption internally.

**Step 1: Clone (or pull if already cloned)**
```python
client = ssh()
# Check if already cloned
out, _ = run(client, "test -d /tmp/mml_compat_repo/.git && echo exists || echo missing")
if 'exists' in out:
    out, err = run(client, "cd /tmp/mml_compat_repo && git pull origin master 2>&1", timeout=120)
else:
    out, err = run(client,
        "git clone --depth 1 https://github.com/JonaldM/mml.composer.git /tmp/mml_compat_repo 2>&1",
        timeout=120
    )
print(out, err)
client.close()
```
Expected: `Cloning into '/tmp/mml_compat_repo'...` then `done.`

**Step 2: Symlink module directories into /tmp/mml_compat/**

`mml_base` is at the repo root. `mml_edi` is inside `mml.edi/` (directory name has a dot — symlink it with the correct technical name).

```python
client = ssh()
run(client, "mkdir -p /tmp/mml_compat")
# mml_base — dir name matches technical name
run(client, "ln -sfn /tmp/mml_compat_repo/mml_base /tmp/mml_compat/mml_base")
# mml_edi — source dir is mml.edi/, symlink as mml_edi (technical name)
run(client, "ln -sfn /tmp/mml_compat_repo/mml.edi /tmp/mml_compat/mml_edi")
client.close()
```

**Step 3: Verify**
```python
client = ssh()
out, _ = run(client, "ls -la /tmp/mml_compat/ && echo '---' && ls /tmp/mml_compat/mml_base/ | head -5 && echo '---' && ls /tmp/mml_compat/mml_edi/ | head -5")
print(out)
client.close()
```
Expected: Both `mml_base/` and `mml_edi/` listed. Each shows `__manifest__.py`, `models/`, etc.

**Step 4: Make files readable by the odoo user**
```python
client = ssh()
run(client, "echo 'Lockitdown456' | sudo -S chmod -R a+rX /tmp/mml_compat/")
client.close()
```

---

## Task 4: Install mml_base

**Goal:** Install `mml_base` into `MML_EDI_Compat` and confirm it installs cleanly.

The Odoo 19 binary needs to run as the `odoo` OS user (it accesses the DB via peer/socket auth as the `odoo` pg role). We use `sudo -u odoo`.

The addons path extends the configured path with our temp dir.

**Step 1: Stop the Odoo 19 service**

> This is required because Odoo uses advisory locks on the DB; a running instance will block --stop-after-init installs.
> Harold's Odoo 15 instance (odoo-server.conf) is on a different port and DB — it is NOT affected.

```python
client = ssh()
out, err = run(client, "echo 'Lockitdown456' | sudo -S systemctl stop odoo19 2>&1")
print(out, err)
# Verify it stopped
out2, _ = run(client, "echo 'Lockitdown456' | sudo -S systemctl is-active odoo19 2>&1")
print("Status:", out2)
client.close()
```
Expected: Status = `inactive` or `failed` (stopped). If it won't stop, STOP the plan and investigate.

**Step 2: Run mml_base install**

```python
ADDONS_PATH = (
    '/opt/odoo19/odoo/addons'
    ',/mnt/odoo-addons/enabling19'
    ',/mnt/odoo-addons/repos19/purchase-workflow'
    ',/tmp/mml_compat'
)

cmd = (
    f"echo 'Lockitdown456' | sudo -S -u odoo "
    f"/opt/odoo19/venv/bin/python3 /opt/odoo19/odoo-bin "
    f"-c /etc/odoo/odoo19.conf "
    f"--addons-path={ADDONS_PATH} "
    f"-i mml_base "
    f"-d MML_EDI_Compat "
    f"--stop-after-init "
    f"--no-http "
    f"2>&1"
)

client = ssh()
out, err = run(client, cmd, timeout=300)
print(out[-3000:])  # last 3000 chars — the interesting part
if err:
    print("STDERR:", err[-1000:])
client.close()
```

**Step 3: Check result**

Scan output for these keywords:
```python
output_lower = out.lower()
errors   = [l for l in out.splitlines() if 'error' in l.lower() and 'WARNING' not in l]
warnings = [l for l in out.splitlines() if 'warning' in l.lower()]
print(f"Errors ({len(errors)}):")
for l in errors[:20]: print(" ", l)
print(f"Warnings ({len(warnings)}):")
for l in warnings[:10]: print(" ", l)
```

Expected outcome:
- No `ERROR` lines referencing `mml_base`
- The line `Module mml_base loaded` or similar confirmation
- Some warnings are normal (deprecated API notices etc.)

**Step 4: Verify install in DB**
```python
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat "
    "-c \"SELECT name, state, latest_version FROM ir_module_module WHERE name='mml_base';\" 2>&1"
)
print(out)
client.close()
```
Expected: `state = installed`, `latest_version = 19.0.1.0.0`.

**Step 5: Record any issues**

Write down any errors or deprecation warnings here before proceeding. These are compatibility findings.

---

## Task 5: Install mml_edi

**Goal:** Install `mml_edi` into `MML_EDI_Compat` (mml_base already installed) and check compatibility.

**Step 1: Run mml_edi install**
```python
ADDONS_PATH = (
    '/opt/odoo19/odoo/addons'
    ',/mnt/odoo-addons/enabling19'
    ',/mnt/odoo-addons/repos19/purchase-workflow'
    ',/tmp/mml_compat'
)

cmd = (
    f"echo 'Lockitdown456' | sudo -S -u odoo "
    f"/opt/odoo19/venv/bin/python3 /opt/odoo19/odoo-bin "
    f"-c /etc/odoo/odoo19.conf "
    f"--addons-path={ADDONS_PATH} "
    f"-i mml_edi "
    f"-d MML_EDI_Compat "
    f"--stop-after-init "
    f"--no-http "
    f"2>&1"
)

client = ssh()
out, err = run(client, cmd, timeout=300)
print(out[-5000:])
client.close()
```

**Step 2: Capture all errors and warnings**
```python
errors       = [l for l in out.splitlines() if ' ERROR ' in l]
critical     = [l for l in out.splitlines() if 'CRITICAL' in l]
deprecations = [l for l in out.splitlines() if 'deprecated' in l.lower() or 'DeprecationWarning' in l]

print(f"CRITICAL ({len(critical)}):")
for l in critical: print(" ", l)
print(f"ERRORs ({len(errors)}):")
for l in errors[:30]: print(" ", l)
print(f"Deprecations ({len(deprecations)}):")
for l in deprecations[:20]: print(" ", l)
```

**Step 3: Verify install in DB**
```python
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat "
    "-c \"SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('mml_base','mml_edi') ORDER BY name;\" 2>&1"
)
print(out)
client.close()
```
Expected: Both rows show `state = installed`.

**Step 4: Check that EDI data loaded**
```python
client = ssh()
queries = [
    # Trading partner seeded from edi_trading_partner_briscoes.xml
    "SELECT count(*) FROM mml_edi_trading_partner;",
    # IR sequence from ir_sequence.xml
    "SELECT name, prefix, number_next FROM ir_sequence WHERE name LIKE '%EDI%';",
    # Cron job from ir_cron.xml
    "SELECT cron_name, active FROM ir_cron WHERE cron_name LIKE '%EDI%' OR cron_name LIKE '%FTP%';",
    # Menu items exist
    "SELECT count(*) FROM ir_ui_menu WHERE complete_name LIKE '%EDI%';",
]
for q in queries:
    o, _ = run(client, f"echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat -c \"{q}\" 2>&1")
    print(q)
    print(o)
client.close()
```

**Step 5: Run Odoo integration tests for mml_edi**
```python
cmd = (
    f"echo 'Lockitdown456' | sudo -S -u odoo "
    f"/opt/odoo19/venv/bin/python3 /opt/odoo19/odoo-bin "
    f"-c /etc/odoo/odoo19.conf "
    f"--addons-path={ADDONS_PATH} "
    f"--test-enable "
    f"-u mml_edi "
    f"-d MML_EDI_Compat "
    f"--stop-after-init "
    f"--no-http "
    f"--test-tags /mml_edi "
    f"2>&1"
)

client = ssh()
out, err = run(client, cmd, timeout=600)
# Count test results
passed  = out.count('ok')
failed  = out.count('FAIL')
errors_ = out.count('ERROR')
print(f"Tests — passed: {passed}, failed: {failed}, errors: {errors_}")
print(out[-5000:])
client.close()
```

**Step 6: Check the Odoo 19 server log for any post-install errors**
```python
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S tail -100 /var/log/odoo19/odoo.log 2>&1 | grep -E 'ERROR|CRITICAL'"
)
print(out if out else "No errors in log tail")
client.close()
```

---

## Task 6: Capture and record findings

**Goal:** Before cleanup, record everything found so we have a complete compatibility report.

**Step 1: Check Python version compatibility**
```python
client = ssh()
out, _ = run(client,
    "/opt/odoo19/venv/bin/python3 --version && "
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat "
    "-c \"SELECT latest_version FROM ir_module_module WHERE name='mml_edi';\" 2>&1"
)
print(out)
client.close()
```

**Step 2: Check for any failed cron jobs post-install**
```python
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat "
    "-c \"SELECT cron_name, failure_count, first_failure_date FROM ir_cron WHERE (name LIKE '%EDI%' OR cron_name LIKE '%EDI%' OR cron_name LIKE '%FTP%') AND failure_count > 0;\" 2>&1"
)
print(out if out else "No cron failures")
client.close()
```

**Step 3: Write a compatibility summary**

After running the above, produce a report with:
- Install status: mml_base (pass/fail) + mml_edi (pass/fail)
- List of all ERRORs encountered
- List of deprecation warnings
- Test results (pass/fail counts)
- Any data loading issues (missing sequences, menus, etc.)
- Verdict: Ready / Needs fixes / Blocked

---

## Task 7: Cleanup

**Goal:** Remove all traces. Drop `MML_EDI_Compat`, delete `/tmp/mml_compat/`. Restart Odoo 19. Harold's environment is fully restored.

**Step 1: Drop the compat database**
```python
client = ssh()
# Must disconnect all sessions first
run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql "
    "-c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='MML_EDI_Compat';\" 2>&1"
)
out, err = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres dropdb MML_EDI_Compat 2>&1"
)
print(out, err)
client.close()
```
Expected: No error. DB dropped.

**Step 2: Remove temp module files**
```python
client = ssh()
out, err = run(client, "echo 'Lockitdown456' | sudo -S rm -rf /tmp/mml_compat/ 2>&1")
print(out, err)
client.close()
```

**Step 3: Restart Odoo 19**
```python
client = ssh()
out, err = run(client, "echo 'Lockitdown456' | sudo -S systemctl start odoo19 2>&1")
import time; time.sleep(5)
out2, _ = run(client, "echo 'Lockitdown456' | sudo -S systemctl is-active odoo19 2>&1")
print("Odoo 19 status:", out2)
client.close()
```
Expected: `active`.

**Step 4: Final verification — confirm Harold's DB is unchanged**
```python
client = ssh()
# Confirm MML_Test_Odoo19_02102026 still exists and is healthy
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -l 2>&1"
)
has_test_db = 'MML_Test_Odoo19_02102026' in out
has_compat  = 'MML_EDI_Compat' in out
print(f"Harold's DB still present: {has_test_db}")
print(f"Compat DB cleaned up: {not has_compat}")
client.close()
```
Expected: `True` and `True`.

**Step 5: Check Odoo 19 log for clean startup**
```python
import time; time.sleep(10)
client = ssh()
out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S tail -30 /var/log/odoo19/odoo.log 2>&1 | grep -E 'ERROR|CRITICAL|odoo.service'"
)
print(out if out else "Clean startup — no errors")
client.close()
```

---

## Task 8: Install stock_3pl_core + stock_3pl_mainfreight

**Goal:** Install both 3PL modules into `MML_EDI_Compat` (mml_base already installed). Dependency order: `stock_3pl_core` first, then `stock_3pl_mainfreight`.

**Repo:** `https://github.com/JonaldM/mml.3pl.odoo.git` (make public before running — same as mml.composer)

**Known pre-fixes applied locally (already committed and pushed):**
- Removed `numbercall` from 4 cron records (stock_3pl_core/data/cron.xml ×2, tracking_cron.xml, inbound_cron.xml)
- Removed `password=True` from 6 field definitions (connector.py ×2, connector_mf.py ×4)
- Fixed `%(xmlid)d` button name syntax in connector_views.xml and exception_views.xml

**Extra Python dependency:** `cryptography` must be present in the Odoo venv for Fernet credential encryption. Check and install if missing (see Step 1).

---

### Step 1: Check and install `cryptography` in Odoo venv
```python
client = connect()
rc, out, _ = run(client, "/opt/odoo19/venv/bin/pip show cryptography 2>&1")
print("cryptography:", out[:200] if rc == 0 else "NOT INSTALLED")
if rc != 0:
    rc2, out2, err2 = run(client,
        "echo 'Lockitdown456' | sudo -S /opt/odoo19/venv/bin/pip install cryptography 2>&1",
        timeout=120
    )
    print("install rc:", rc2, out2[-300:])
client.close()
```

### Step 2: Clone the 3PL repo on the server
```python
client = connect()
rc, out, _ = run(client, "test -d /tmp/mml_3pl_repo/.git && echo EXISTS || echo MISSING")
if 'EXISTS' in out:
    rc, out, err = run(client, "cd /tmp/mml_3pl_repo && git pull origin master 2>&1", timeout=120)
else:
    rc, out, err = run(client,
        "git clone --depth 1 https://github.com/JonaldM/mml.3pl.odoo.git /tmp/mml_3pl_repo 2>&1",
        timeout=180)
print(f"rc={rc}", out[-300:])
client.close()
```

### Step 3: Symlink 3PL addons into /tmp/mml_compat/
```python
client = connect()
# stock_3pl_core
run(client, "ln -sfn /tmp/mml_3pl_repo/addons/stock_3pl_core /tmp/mml_compat/stock_3pl_core")
# stock_3pl_mainfreight
run(client, "ln -sfn /tmp/mml_3pl_repo/addons/stock_3pl_mainfreight /tmp/mml_compat/stock_3pl_mainfreight")
rc, out, _ = run(client, "ls -la /tmp/mml_compat/")
print(out)
client.close()
```

### Step 4: Stop odoo19, install stock_3pl_core
```python
client = connect()
run(client, "echo 'Lockitdown456' | sudo -S systemctl stop odoo19.service 2>&1")

cmd = (
    "echo 'Lockitdown456' | sudo -S -u odoo "
    "/opt/odoo19/venv/bin/python3 /opt/odoo19/odoo-bin "
    "-c /tmp/odoo19_edi_compat.conf "
    "-i stock_3pl_core "
    "-d MML_EDI_Compat "
    "--stop-after-init 2>&1"
)
rc, out, err = run(client, cmd, timeout=400)
print(f"stock_3pl_core install rc={rc}")
print((out + err)[-6000:])
client.close()
```
Expected: `Modules loaded.` with no ERRORs from stock_3pl_core.

### Step 5: Install stock_3pl_mainfreight
```python
client = connect()
cmd = (
    "echo 'Lockitdown456' | sudo -S -u odoo "
    "/opt/odoo19/venv/bin/python3 /opt/odoo19/odoo-bin "
    "-c /tmp/odoo19_edi_compat.conf "
    "-i stock_3pl_mainfreight "
    "-d MML_EDI_Compat "
    "--stop-after-init 2>&1"
)
rc, out, err = run(client, cmd, timeout=400)
print(f"stock_3pl_mainfreight install rc={rc}")
print((out + err)[-6000:])
client.close()
```

### Step 6: Restart odoo19 and verify
```python
client = connect()
run(client, "echo 'Lockitdown456' | sudo -S systemctl start odoo19.service 2>&1")
time.sleep(5)
rc, out, _ = run(client, "echo 'Lockitdown456' | sudo -S systemctl is-active odoo19.service 2>&1")
print("service:", out)

rc, out, _ = run(client,
    "echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat "
    "-c \"SELECT name, state FROM ir_module_module "
    "WHERE name IN ('mml_base','mml_edi','stock_3pl_core','stock_3pl_mainfreight') ORDER BY name;\" 2>&1"
)
print(out)
client.close()
```
Expected: all 4 modules in state `installed`.

### Step 7: Spot-check key DB objects
```python
client = connect()
checks = [
    # Connector model exists
    "SELECT count(*) FROM ir_model WHERE model='3pl.connector';",
    # Message queue model exists
    "SELECT count(*) FROM ir_model WHERE model='3pl.message';",
    # MF crons registered (inactive by default)
    "SELECT cron_name, active FROM ir_cron WHERE cron_name LIKE '%MF%' OR cron_name LIKE '%3PL%';",
    # KPI dashboard model
    "SELECT count(*) FROM ir_model WHERE model='mf.kpi.dashboard';",
]
for q in checks:
    rc, out, _ = run(client,
        f"echo 'Lockitdown456' | sudo -S -u postgres psql -d MML_EDI_Compat -c \"{q}\" 2>&1"
    )
    print(q[:60], "->", out.strip())
client.close()
```

### Report
- PASS / FAIL per module
- Any errors or tracebacks (first occurrence with surrounding context)
- Remaining warnings
- DB spot-check results

---

## Success criteria

- [ ] `mml_base` installs with state=`installed` and no ERRORs
- [ ] `mml_edi` installs with state=`installed` and no ERRORs
- [ ] `stock_3pl_core` installs with state=`installed` and no ERRORs
- [ ] `stock_3pl_mainfreight` installs with state=`installed` and no ERRORs
- [ ] All XML data files load (sequences, trading partner, cron, menus)
- [ ] Odoo integration tests pass (or failures are documented and understood)
- [ ] `MML_EDI_Compat` kept for ongoing module testing
- [ ] `/tmp/mml_compat/` and `/tmp/mml_3pl_repo/` cleaned up only after all modules tested
- [ ] Odoo 19 service restarted and active
- [ ] `MML_Test_Odoo19_02102026` untouched throughout

## If install fails

Common failures and what they mean:

| Error | Likely cause | Action |
|---|---|---|
| `Field ... not found` | Model field renamed in Odoo 19 | Note field name, fix in module |
| `AttributeError: ... has no attribute` | API removed/renamed | Note the API, check Odoo 19 migration docs |
| `XML validation failed` | View XML uses removed attributes | Fix the XML |
| `Cannot install module` / missing dep | Dependency not installed | Check `depends` in manifest |
| `ir.cron` column error | Cron field name changed (it did — `name` → `cron_name`) | Already handled in mml_base; check mml_edi crons |
| Python import error | Third-party package missing on server | Check `requirements.txt`, install via pip in venv |
