import paramiko
import time
import sys
import io

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('10.0.0.35', username='jono', password='***REMOVED***', timeout=30)
    c.get_transport().set_keepalive(30)
    return c

def run(client, cmd, timeout=120):
    if not client.get_transport() or not client.get_transport().is_active():
        raise RuntimeError("SSH session dropped")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    out_clean = '\n'.join(l for l in out.splitlines() if not l.startswith('[sudo]'))
    err_clean = '\n'.join(l for l in err.splitlines() if not l.startswith('[sudo]'))
    return rc, out_clean, err_clean

print("=== STEP 9: Restart odoo19 service ===")
client = connect()
rc, out, err = run(client, "echo '***REMOVED***' | sudo -S systemctl start odoo19.service 2>&1")
time.sleep(5)
rc, out, _ = run(client, "echo '***REMOVED***' | sudo -S systemctl is-active odoo19.service 2>&1")
print("is-active:", repr(out))

# Fallback: check if port 8069 is listening
rc2, out2, _ = run(client, "ss -tlnp | grep 8069 || echo 'port 8069 not yet open'")
print("port check:", out2)

client.close()
print()

print("=== STEP 10: Verify module states and spot checks ===")
client = connect()

rc, out, _ = run(client,
    "echo '***REMOVED***' | sudo -S -u postgres psql -d MML_EDI_Compat -c "
    "\"SELECT name, state FROM ir_module_module WHERE name IN "
    "('mml_base','mml_edi','stock_3pl_core','stock_3pl_mainfreight',"
    "'mml_forecast_core','mml_forecast_financial','mml_roq_forecast') ORDER BY name;\" 2>&1")
print("=== All module states ===")
print(out)

checks = [
    ("forecast.config model",
     "SELECT count(*) FROM ir_model WHERE model='forecast.config';"),
    ("forecast.origin.port model",
     "SELECT count(*) FROM ir_model WHERE model='forecast.origin.port';"),
    ("forecast.opex.line model",
     "SELECT count(*) FROM ir_model WHERE model='forecast.opex.line';"),
    ("roq.forecast.run model",
     "SELECT count(*) FROM ir_model WHERE model='roq.forecast.run';"),
    ("roq.shipment.group model",
     "SELECT count(*) FROM ir_model WHERE model='roq.shipment.group';"),
    ("ROQ crons",
     "SELECT cron_name, active FROM ir_cron WHERE cron_name LIKE '%ROQ%' OR cron_name LIKE '%roq%';"),
]
for label, q in checks:
    rc, out, _ = run(client,
        f"echo '***REMOVED***' | sudo -S -u postgres psql -d MML_EDI_Compat -c \"{q}\" 2>&1")
    print(f"\n{label}: {out.strip()}")

client.close()
