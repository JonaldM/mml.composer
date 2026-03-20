# MML Odoo Ops Runbook

## Server Access (Tailscale required)

All servers are accessible only via Tailscale VPN. Connect to Tailscale before any SSH or DB access.

| Server | Tailscale IP | Role |
|--------|-------------|------|
| Prem (bare-metal) | 10.0.0.35 | Odoo 15 prod (MML_Production) + Odoo 19 dev (port 8073, MML_EDI_Compat) |
| Hetzner | TBD | PG 15 standby + Odoo 19 DR (planned failover Q2 2026) |

SSH access: `ssh <user>@<tailscale-ip>` (key-based auth)

## Credential Rotation Procedure

1. Generate new SSH key pair: `ssh-keygen -t ed25519 -f ~/.ssh/mml_ops`
2. Add public key to `~/.ssh/authorized_keys` on target server **while current session is active**
3. Test new key in a second terminal before closing the existing session
4. Remove the old key from `authorized_keys`
5. Update `MML_SSH_PASSWORD` env var in any deployment environment
6. Run `python restart_and_verify.py` to confirm deployment scripts work

## EDI Circuit Breaker

The EDI FTP poller has a circuit breaker on `edi.trading.partner`. If polling stops:

**Check circuit state (Odoo shell or psql):**
```sql
SELECT code, circuit_failure_count, circuit_open_since, circuit_failure_threshold
FROM edi_trading_partner
WHERE circuit_failure_count >= circuit_failure_threshold;
```

**Diagnose:**
1. Test FTP connectivity: `telnet post.edis.co.nz 21`
2. Check FTP credentials: Odoo > Settings > EDI > Trading Partners
3. Review recent `edi.log` records for the partner

**Reset circuit after FTP is restored:**
```sql
UPDATE edi_trading_partner
SET circuit_failure_count = 0, circuit_open_since = NULL;
```

## Alert Email Configuration

EDI cron failures send email alerts. Configure via Odoo system parameters:
```sql
UPDATE ir_config_parameter SET value = 'ops@mml.co.nz'
WHERE key = 'mml.cron_alert_email';
```

## PG Replication Status

From any machine with Tailscale:
```bash
# From the mml.hiav/ directory (relative to repo):
bash ../mml.hiav/check-replication.sh
```

Expected: replication lag < 60 seconds.

## Odoo Service Management (Prem)

```bash
# Check status
sudo systemctl status odoo19.service

# Restart
sudo systemctl restart odoo19.service

# View logs (last 100 lines)
sudo journalctl -u odoo19.service -n 100 --no-pager
```

## Module Upgrade Procedure

```bash
# Upgrade a single module
python odoo-bin -d MML_EDI_Compat -u <module_name> --stop-after-init

# Upgrade multiple modules
python odoo-bin -d MML_EDI_Compat -u mml_edi,mml_base --stop-after-init
```

## Current Migration Status (as of 2026-03-21)

| Component | Status | Target |
|-----------|--------|--------|
| Odoo 15 → 19 | In progress (dev on port 8073) | Q2 2026 cutover |
| Hetzner HA failover | Phase 1 complete (standby synced) | May–Jun 2026 |
| Legacy .NET EDI → mml_edi | In progress (ASN disabled pending .NET retirement) | Q2 2026 |
| ROQ legacy → mml.forecasting | In progress (see forecasting-migration.md) | H2 2026 |

Full failover plan: `mml.hiav/odoo-ha-migration-plan.md`
