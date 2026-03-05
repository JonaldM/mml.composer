# MML Odoo Apps — Pre-Production Deployment Runbook

**Last updated:** 2026-03-05
**Target:** Odoo 19, self-hosted (MML Odoo instance at 10.0.0.35)

---

## Pre-Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs: `paramiko` (SFTP for 3PL and EDI transports), `numpy` and `scipy` (ROQ demand forecasting).

---

## Module Install Order

Install in this exact sequence. Odoo respects `depends[]` but explicit ordering prevents partial upgrades causing install failures.

1. `mml_base`
2. `mml_forecast_core`
3. `mml_barcode_registry`
4. `mml_forecast_financial`
5. `mml_freight` → then `mml_freight_dsv`, `mml_freight_knplus`, `mml_freight_mainfreight`
6. `stock_3pl_core` → then `stock_3pl_mainfreight`
7. `mml_freight_3pl` (bridge — `auto_install=True`, verify it activates)
8. `mml_roq_forecast` → then `mml_roq_freight` bridge (auto_install)
9. `mml_edi` (directory must be named `mml_edi` in the Odoo addons path — currently named `briscoes.edi` in the repo; symlink or rename before installing)

**Do NOT install:** `mml_freight_demo` (`installable=False`)

---

## Required `ir.config_parameter` Values

Set in **Settings → Technical → System Parameters** before go-live:

| Key | Example Value | Description |
|-----|--------------|-------------|
| `mml.cron_alert_email` | `ops@mml.co.nz` | Cron failure email destination |
| `mml_edi.sender_id` | `MMLEDI` | MML EDIS VAN sender ID |
| `mml_edi.asn_enabled` | `0` | Keep `0` until .NET service retired |
| `stock_3pl_mainfreight.webhook_secret` | `<secret>` | Mainfreight webhook HMAC secret |
| `mml_freight.mf_webhook_secret` | `<secret>` | Same as above if separate |
| `mml_freight_dsv.api_url` | `https://api.dsv.com` | DSV API base URL |
| `mml_registry.service.edi` | _(auto-set on install)_ | Set by mml_edi post_init_hook |
| `mml_registry.service.roq` | _(auto-set on install)_ | Set by mml_roq_forecast post_init_hook |

---

## SFTP Host Key Configuration (Briscoes EDIS VAN)

The new mml_edi SFTP connection **requires** a pinned host key. Without it, SFTP connections are refused (fail-safe).

1. Run from a trusted network: `ssh-keyscan -t rsa post.edis.co.nz | awk '{print $3}'`
2. Copy the base64 output
3. In Odoo: **EDI → Trading Partners → Briscoes → SFTP Host Key** — paste the base64 value
4. Save (requires System Administrator role)

---

## Briscoes Store GLN Configuration

For each Briscoes delivery location in Odoo (**Inventory → Configuration → Locations**):

1. Open the location (e.g. "Briscoes Whangarei")
2. Set **EDI Store GLN** to the GLN from the Briscoes PO `LOC+7` or `NAD+UD` segment
   - Store 1005 → Briscoes Whangarei
   - Store 1007 → Briscoes Albany
   - (add others as POs arrive)
3. Save

Store GLNs must be configured before ASN generation is enabled, or ASN lines for un-configured stores will be skipped with a warning.

---

## Sandbox Testing Checklist

Run through this on **ODOOTEST** database before touching production.

### EDI (mml_edi)
- [ ] Install mml_edi on ODOOTEST
- [ ] Configure Briscoes trading partner with **test** EDIS VAN credentials (`/Test/FromEDIS`, `/Test/ToEDIS`)
- [ ] Set SFTP host key for `post.edis.co.nz`
- [ ] Set store GLNs for at least 2 Briscoes locations
- [ ] Trigger manual poll: **EDI → Trading Partners → Briscoes → Poll Now**
- [ ] Confirm Briscoes PO appears in **EDI → Order Review Queue**
- [ ] Approve order → confirm SO created with correct lines
- [ ] Generate ORDRSP → confirm file appears in `/Test/ToEDIS/`
- [ ] Verify ORDRSP contains valid EAN-13 segments

### ASN (when ready to activate)
- [ ] Set `mml_edi.asn_enabled = 1`
- [ ] Validate a stock.picking (mark as done)
- [ ] Confirm `DESADV_*.edi` appears in `/Test/ToEDIS/`
- [ ] Check `ir.attachment` on the picking for the DESADV file
- [ ] Check picking chatter for "ASN sent to Briscoes" message
- [ ] Check **EDI → Audit Log** for upload entry
- [ ] Revert `mml_edi.asn_enabled = 0` after test

### ROQ Forecast
- [ ] Install mml_roq_forecast
- [ ] Run a forecast via **Forecasting → Forecast Runs → New → Run Now**
- [ ] Confirm no `AccessError` in server log
- [ ] Raise draft POs via wizard — confirm duplicate guard fires on second attempt
- [ ] Confirm POs are assigned to `purchase.group_purchase_user` — non-purchase users should get UserError

### 3PL (stock_3pl)
- [ ] Configure Mainfreight webhook secret in ir.config_parameter
- [ ] Send test payload to `/web/stock_3pl/mainfreight/webhook` with correct HMAC
- [ ] Confirm picking updated (not rejected)
- [ ] Confirm cron alert email fires when an error is injected

### Barcode Registry
- [ ] Install mml_barcode_registry
- [ ] Allocate a GTIN to a test product
- [ ] Confirm GTIN appears on product form smart button
- [ ] Import XLSX with test barcodes — confirm check digit validation rejects invalid rows

---

## Cron Alert Configuration

After install, set `mml.cron_alert_email` in System Parameters. All three modules (mml_edi, mml_roq_forecast, stock_3pl) will email this address when a scheduled action fails.

Test by temporarily breaking a cron (e.g. set an invalid FTP host) and running the cron manually: **Settings → Technical → Automation → Scheduled Actions**.

---

## Go-Live: EDI ASN Cutover

When ready to retire the legacy .NET `BriscoesEditOrder` service:

1. Confirm all Briscoes store GLNs are configured in Odoo
2. Stop (or pause) the `.NET BriscoesEditOrder` Windows service
3. Set `mml_edi.asn_enabled = 1` in ir.config_parameter
4. Process a live despatch and confirm `DESADV_*.edi` appears in `/ToEDIS/`
5. Monitor `EDI → Audit Log` for any upload failures
6. Keep the .NET service available for 1 week rollback window

---

## Rollback Procedure

If critical issues found post-install:

1. Set `mml_edi.asn_enabled = 0` immediately
2. Restart the legacy .NET service if it was stopped
3. **Do NOT uninstall modules with live data** — instead set `installable = False` and restart Odoo
4. For code-level rollback: `git revert <sha>` in the affected module repo, restart Odoo
5. Escalation contact: check CLAUDE.md for project contacts

---

## Known Deployment Notes

- `briscoes.edi/` must be on the Odoo addons path **as `mml_edi`** (the technical module name in the manifest). Either symlink it or add the parent directory to addons_path with the directory renamed.
- `roq.model/`, `fowarder.intergration/`, `mainfreight.3pl.intergration/`, `mml.forecasting/` are separate git repos nested inside the workspace — each has its own `.git/`. Deploy scripts must handle each separately.
- `mml_forecast_demand` has been deleted — do not attempt to install it.
- `mml_freight_demo` has `installable=False` — it will not appear as installable on the home screen.
