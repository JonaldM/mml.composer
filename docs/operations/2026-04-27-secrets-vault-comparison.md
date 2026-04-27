# Secrets Vault Comparison Runbook for MML

**Date:** 2026-04-27
**Author:** Sprint agent P4 (audit-fix)
**Status:** Decision pending (operator: Jonathan)
**Closes:** Parked item P4, 2026-04-27 sprint
**Related:** `mml.hiav/CLAUDE.md`, `mml.hiav/ssh.txt`, `mml.hiav/certificates/*.txt`

---

## 1. Current state

### What exists today

MML infrastructure secrets currently live in plaintext files inside the developer working tree at:

```
E:/ClaudeCode/projects/mml.odoo/mml.hiav/
  ssh.txt                       # SSH passwords + service-to-service credentials
  certificates/
    mml.co.nz.txt               # Cloudflare Origin Cert (cert + private key)
    mmlakl.co.nz.txt            # Cloudflare Origin Cert
    enkelshop.com.txt           # Cloudflare Origin Cert
    petpro.co.nz.txt            # Cloudflare Origin Cert
    volere.com.au.txt           # Cloudflare Origin Cert
```

Per `mml.hiav/CLAUDE.md` (not opened directly), these files contain:

| Category | Item | Used by |
|---|---|---|
| Operator-facing | Prem SSH password (`jono@10.0.0.35` / `100.110.92.80`) | Manual SSH, paramiko sessions from Claude Code |
| Operator-facing | Hetzner Read-Write API key | Hetzner console / Terraform / firewall changes |
| Operator-facing | Tailscale OAuth client secret | Tailnet provisioning, ACL pushes, key issuance |
| Service-to-service | PostgreSQL `replicator` password | Hetzner standby `primary_conninfo` over Tailscale |
| Service-to-service | Hetzner PostgreSQL admin password | Container init, restore tooling, dev provisioning |
| TLS material | Cloudflare Origin Cert + key (5 domains) | Nginx on prem and Hetzner; Cloudflare Full (Strict) |

Application secrets (Stripe keys, Odoo `admin_passwd`, Cloudflare API token, SMTP) live in `.env.local` files next to their services — out of scope here, but should follow into the same vault on a follow-up.

### What is **not** in source control

Verified, read-only:

- `mml.hiav/` is a planning directory with no `.git`. Secrets are not committed.
- `mml.odoo.apps`, `pet.pro.website`, `mml_test_sprint`, and other MML repos do not contain `ssh.txt` or `certificates/*.txt`. Spot-checked git history: no leak.

### Why the current state is CRITICAL

1. **Single device, no encryption boundary.** Files are plaintext on `E:/`. BitLocker (if enabled) protects against offline disk theft only; any process running as Jonathan's user reads them.
2. **Blast radius.** One laptop compromise yields direct SSH to prem (live `MML_Production` 6.7 GB DB), root SSH to Hetzner, PG replication credential, Tailscale OAuth (mint new tailnet keys, bypass the public firewall), Hetzner API key (provision/destroy servers, change billing), and 5 Cloudflare Origin Certs (Cloudflare-trusted MITM against five customer domains until revoked — Origin Certs default to ~15-year validity).
3. **No audit trail.** No record of when, by whom, or how any secret was last accessed. If the laptop is lost, every secret must be assumed leaked.
4. **Programmatic pattern is fragile.** `ssh_utils.py` parses `ssh.txt`. New contributors get a copy by hand, encouraging proliferation.

---

## 2. Requirements

The vault must satisfy these for a solo operator today, with headroom for a 3–5 person ops team in 12–18 months.

| # | Requirement | Why it matters for MML |
|---|---|---|
| R1 | Solo today, future small team | Jonathan is the only user. Adding 2–4 trusted users must not require re-architecting. |
| R2 | Cross-machine access | Laptop (Windows + Claude Code), prem (Ubuntu 20.04), Hetzner (Ubuntu 24.04), iOS for break-glass. All four read at least a subset. |
| R3 | Programmatic API for CI/CD | GitHub Actions does not yet exist for MML; Phase 3 (Jul–Aug 2026) anticipates CI runners needing the Hetzner API key, Cloudflare token, and PG creds. |
| R4 | Rotation + audit log | Every read should be logged with operator, machine, secret, timestamp. Rotation should be documented and ideally scriptable. |
| R5 | Offline / break-glass | If the vault is down during a Phase 2 cutover, MML cannot be locked out of its own infrastructure. |
| R6 | NZ-friendly billing | Direct NZD preferred; USD acceptable; EU/AU-only billing portals add friction. |
| R7 | Short-lived dynamic credentials (nice-to-have) | Vault's standout feature: 30-min SSH certs and per-session PG roles instead of static passwords. Useful for `replicator` and prem SSH. |
| R8 | File support | Cloudflare Origin Cert + key pairs are 4 KB multi-line PEMs. Files first-class beats env-var workarounds. |
| R9 | Lock-in risk | Open formats and exportable backups beat proprietary single-vendor binaries. Migration should take days, not weeks. |

---

## 3. Comparison table

Pricing checked April 2026; verify at signup. NZD figures use ~1.65 USD→NZD.

| Tool | Setup ease | Operator UX | Programmatic API | Cost (solo, NZD/mo) | Cost (5-user, NZD/mo) | File support | Audit log | Dynamic creds | NZ residency | Lock-in risk |
|---|---|---|---|---|---|---|---|---|---|---|
| **1Password Business** | High | Excellent (best GUI + CLI) | Good (Connect Server, op CLI, SCIM) | ~$13 (Teams Starter Pack $19.95 USD/mo flat ≤10 users) | ~$66 ($7.99 USD/user Business) | Yes (Documents up to 2 GB) | Yes (Business tier; Slack/Teams hooks) | No | US/EU/CA (no AU/NZ) | Medium (`.1pux` export) |
| **Bitwarden Secrets Manager** | Medium (separate from password mgr) | Good (`bws` CLI; less polished) | Excellent (REST, SDK, GitHub Actions, K8s operator) | $0 (free: 2 projects, 3 service accts) | ~$33 ($4 USD/user Teams + SM bundle) | Workaround (kv only; PEM as multiline string) | Yes (event log, exportable) | No | US Cloud; self-host on Hetzner | Low (open source AGPL/BSL) |
| **Doppler** | High | Good for env-vars, weaker elsewhere | Excellent (CLI, REST, native CI integrations) | $0 (Developer free tier) | ~$173 ($21 USD/seat Team — up from $5 in 2024) | **No native file support** (base64 workaround) | Yes (Team tier; SOC 2) | No | US only | Medium (proprietary; export rebuilds integrations) |
| **Vault Community Edition (self-host)** | Low (Raft cluster, seal/unseal, policy DSL) | Mixed (powerful CLI, basic UI) | Excellent (HTTP, gRPC, SDKs) | $0 (self-host) | $0 | Yes (KV v2, PKI engine) | Yes (audit device → file/syslog) | **Yes** (SSH CA, PG dynamic, AWS STS, PKI) | Self-host anywhere (NZ on prem; EU on Hetzner) | Low (open source) |
| **Infisical** | High | Good (clean React UI; CLI matches Doppler) | Good (REST, CLI, GitHub/GitLab/K8s) | $0 (Cloud free: 5 users) | $0–$33 ($8 USD/user Pro after free; self-host stays free) | Yes (file uploads first-class) | Yes (Pro retains longer) | Limited (dynamic PG in Pro; no SSH CA as of Apr 2026) | Self-host anywhere; Cloud US/EU | **Lowest** (MIT-licensed core) |
| **AWS Secrets Manager** | Medium (AWS account + IAM) | Poor for non-engineers (CLI/console only) | Excellent (SDKs, IAM-driven) | ~$8 (~$0.40 USD/secret + API calls; ~12 secrets) | Same | Yes (binary up to 64 KB) | Yes (CloudTrail) | Yes (RDS only natively; bring-your-own Lambda elsewhere) | ap-southeast-2 (Sydney; no NZ) | High (AWS-coupled) |

### Pricing notes

- **1Password** Teams Starter Pack ($19.95 USD/mo flat, ≤10 users) is cheaper for MML's shape than per-seat Business.
- **Bitwarden** SM is sold separately from the password manager; the Teams + SM bundle is what MML wants.
- **Doppler's** 2026 pricing has shifted upward (from $5 USD/seat in 2024 to $21 USD/seat Team). Most expensive per-user.
- **HashiCorp Vault HCP Secrets is being shut down** (end of sale 2025-06-30, EOL 2026-07-01). HCP Vault Dedicated starts at ~$13,800 USD/year. Self-hosted Community Edition is the only sensible HashiCorp option here.
- **Infisical** Cloud is free for ≤5 users with no secret cap; self-hosted is free regardless of seats. Pro ($8 USD/user) adds SAML, longer audit retention, dynamic secrets.
- **AWS SM** charges per secret (~$5–10 USD/mo for ~12 secrets). Hidden cost: no native non-CLI workflow, and non-RDS rotations need custom Lambdas.

---

## 4. Per-option migration plan

Each plan assumes the 18+ secrets are **rotated**, not just copied (section 7); destination cert paths on prem and Hetzner are unchanged (`/etc/ssl/cloudflare/<domain>.{pem,key}`); and `ssh_utils.py` is updated once per option.

### 4.1 1Password Business

1. Sign up; Business ($7.99 USD/user) or Teams Starter Pack ($19.95 USD/mo flat, ≤10 users).
2. Install `op` CLI on laptop, prem, Hetzner; authenticate each with a service account token.
3. Create vault "MML Infrastructure". Add SSH password, Hetzner API key, PG replication password, Tailscale OAuth as items; upload 5 Origin Cert + key pairs as 1Password Documents.
4. Wire `ssh_utils.py` to `op item get "MML Prem SSH" --fields password`.
5. On prem and Hetzner, render certs via `op document get` → `/etc/ssl/cloudflare/<domain>.{pem,key}` (root:root 0600), via systemd on boot.
6. Rotation: operator-driven (no auto-rotate); document per-secret.
7. Enable Business audit log; route to Slack for new-device access alerts.
8. Decommission `ssh.txt` and `certificates/` (section 7).

### 4.2 Bitwarden Secrets Manager

1. Sign up; Teams + Secrets Manager ($4 + $6 USD/user bundled — verify current).
2. Install `bws` CLI on each machine. Three project-scoped service accounts (laptop, prem, Hetzner).
3. Projects "infra" (SSH/PG/Tailscale/Hetzner) and "tls" (Cloudflare). Cert+key as adjacent secrets `mml.co.nz.cert` and `mml.co.nz.key` (multi-line values pass through verbatim).
4. Wire `ssh_utils.py` via `bws secret get <id>`; auth via `BWS_ACCESS_TOKEN` env.
5. systemd unit on each server pulls cert/key, writes `/etc/ssl/cloudflare/`, reloads Nginx if checksums changed.
6. Rotation: API-driven (`PUT /secrets/<id>`).
7. Teams tier audit log; weekly export to S3/R2.
8. Self-host fallback: same Bitwarden image runs on the existing Hetzner box if NZ residency or cost forces a move.
9. Decommission (section 7).

### 4.3 Doppler

1. Sign up; Developer free tier.
2. Project "mml-infra" with environments `prod`, `prem`, `hetzner`.
3. SSH passwords and API keys map naturally. **The 5 Cloudflare cert+key pairs do not** — Doppler treats them as opaque strings; consumers must base64-decode at runtime (real wart).
4. Wire `ssh_utils.py` via `doppler run -- python myscript.py`.
5. Entrypoint script per server runs `doppler secrets get CF_CERT_MML --plain | base64 -d > /etc/ssl/cloudflare/mml.co.nz.pem` for each of 10 file artifacts. Brittle; trailing newlines and IDs need careful handling.
6. UI- and API-driven rotation; solid history/diff for env values.
7. Audit log on Team tier ($21 USD/seat); not Developer.
8. Decommission (section 7).

### 4.4 HashiCorp Vault Community Edition (self-hosted)

1. Smallest footprint: single Vault server on the existing Hetzner box; HA later via 3-node Raft across prem + Hetzner + a Phase 3 mini PC. `apt install vault`; storage = raft; TLS via Cloudflare Origin Cert.
2. Initialize and seal: 5 unseal keys, 3 distributed to physically separate locations (printed + sealed envelopes). Auto-unseal via cloud KMS is cleaner long-term but adds vendor coupling.
3. Mount engines: `kv/` (KV v2) for static; `ssh/` SSH CA for **dynamic** SSH (replaces prem password — `ssh_utils.py` requests a 30-min cert); `database/postgresql/` for **dynamic** PG users (replaces static `replicator`); `pki/` for forward use.
4. Per-machine and per-role policies. Laptop reads everything; CI is read-only on a tight allowlist.
5. `vault agent template` writes `/etc/ssl/cloudflare/<domain>.{pem,key}` from `kv/` (certs are Cloudflare-issued, not Vault-PKI) and reloads Nginx on change.
6. Audit device → syslog → Loki/Grafana, or file with logrotate.
7. Decommission (section 7).

**Honest assessment:** correct technical answer if MML invests 1–2 weeks of operator time. For a solo operator with a day job, heavy lift. Reconsider during Phase 3.

### 4.5 Infisical

1. Cloud (free ≤5 users) or self-host on Hetzner (free, MIT, Docker Compose).
2. Project "mml-infra" with environments `prod`, `prem`, `hetzner`, `dev`.
3. kv pairs for SSH/API/Tailscale; **file uploads** for Cloudflare cert+key pairs (first-class).
4. Wire `ssh_utils.py` via `infisical run --env=prem -- python myscript.py` or the Python SDK with a service token.
5. Native CLI `secrets get --type=file` writes cert/key to disk. Cleaner than Doppler workaround.
6. Rotation: UI-driven; Pro ($8 USD/user) adds dynamic Postgres creds (narrower than Vault's `database/`).
7. Built-in event log; Pro extends retention.
8. Decommission (section 7).

### 4.6 AWS Secrets Manager

1. Region ap-southeast-2 (Sydney), ~25 ms from Auckland. AWS account + IAM root + MFA + billing alerts; non-root admin for day-to-day.
2. One secret per credential; cert+key as JSON `{"cert": "...", "key": "..."}`.
3. Wire `ssh_utils.py` via boto3 `client.get_secret_value(...)`; auth via IAM access key (Hetzner is not EC2 so no instance role).
4. systemd unit calls `aws secretsmanager get-secret-value` → file.
5. Rotation: built-in for RDS only; non-RDS needs custom Lambda. CloudTrail captures every API call.
6. Decommission (section 7).

**Honest assessment:** picks up AWS billing, IAM, and CloudTrail for one narrow use case. Only sensible if AWS is already in the stack — it is not.

---

## 5. Decision matrix

Scored 1–5 against MML's actual situation (solo operator, NZ, mostly self-hosted, ~12 secrets, possible 3–5 person team in 18 months). Higher = better fit.

| Requirement (weight) | 1Password | Bitwarden SM | Doppler | Vault OSS | Infisical | AWS SM |
|---|---|---|---|---|---|---|
| R1: Solo + small team (5) | 5 | 4 | 4 | 2 | 5 | 2 |
| R2: Cross-machine (5) | 5 | 5 | 4 | 4 | 5 | 3 |
| R3: Programmatic API (4) | 4 | 5 | 5 | 5 | 5 | 5 |
| R4: Rotation + audit (4) | 4 | 4 | 4 | 5 | 4 | 5 |
| R5: Offline / break-glass (5) | 5 | 4 | 3 | 3 | 4 | 2 |
| R6: NZ-friendly billing (3) | 4 | 4 | 3 | 5 | 5 | 3 |
| R7: Dynamic creds (3) | 1 | 1 | 1 | 5 | 3 | 3 |
| R8: File support (5) | 5 | 3 | 1 | 4 | 5 | 4 |
| R9: Lock-in risk (3) | 3 | 5 | 3 | 5 | 5 | 1 |
| **Weighted total / 185** | **142** | **140** | **109** | **150** | **156** | **111** |

Method: `score × weight`, summed. Weights reflect what bites a solo operator most: cross-machine consumption, file support, and break-glass beat dynamic creds in priority. With a real ops team and active CI, R3 and R7 would weigh higher and Vault would close the gap on Infisical.

---

## 6. Recommendation

**Pick: Infisical (self-hosted on Hetzner).**

### Why

1. **Highest score against MML's actual constraints.** File support handles the 5 Cloudflare cert/key pairs cleanly; free self-host means zero ongoing license cost; MIT license means lowest lock-in of any option; Doppler-like UX is friendly enough for the rare mobile break-glass moment.
2. **Self-hosting on the existing Hetzner box** keeps secrets on infrastructure MML already controls. No third-party residency question, no vendor billing exposure. The Hetzner box is already running Docker Compose; Infisical is one more compose file.
3. **Sound break-glass story.** JSON dumps that print and seal in an envelope; the same dump rehydrates a fresh instance in minutes. "Vault is down" becomes a recoverable Docker incident, not a vendor outage.
4. **Does not preclude later upgrades.** If secret count or team size grows enough that dynamic SSH/PG matters, Vault OSS sits alongside Infisical (Infisical for static, Vault for dynamic) — no rip-and-replace. Infisical's own dynamic secrets are also maturing on Pro.
5. **Simplest migration of the six.** File support is first-class, CLI matches what `ssh_utils.py` already wants, no vendor-specific quirk (Doppler's base64 dance, AWS's IAM, Vault's policy DSL).

### Tradeoffs

- **Self-host means MML owns Infisical's uptime.** If the Hetzner box dies, the vault dies with it. Mitigation: offline encrypted dump (printed + USB in a safe) plus documented rebuild path. No worse than today, where one laptop holds everything.
- **Younger than Vault, 1Password, Bitwarden.** Smaller community, faster-moving codebase. Pin Docker image tags; review release notes before upgrading. MIT license guarantees fork option if the project disappears.
- **Dynamic secrets are limited.** If MML wants short-lived SSH certs in the next 12 months, Vault is still the right answer.

### Runner-up: 1Password Business

If Jonathan wants zero-ops, polished mobile UX, and is willing to pay ~$13–66 NZD/mo, 1Password is the next-best fit. Loses to Infisical on lock-in and bill, wins on UX and the vault-down story (Cloud SLA + offline encrypted local cache).

### Avoid for MML's situation

- **Doppler:** file-support gap disqualifies it for the cert use case.
- **AWS Secrets Manager:** wrong shape for non-AWS workload; pulls in IAM and CloudTrail for one job.
- **Vault OSS:** correct technical answer, wrong operator-time answer for solo. Reconsider during Phase 3.
- **Bitwarden Secrets Manager:** solid but file support is a workaround; Infisical strictly dominates for MML's shape.

---

## 7. One-time cleanup checklist

Once the chosen vault is provisioned, every secret seeded, every consumer wired, and a successful smoke test passed, perform the following in order. **Do not skip rotation:** these credentials have been on a laptop in plaintext for an unknown duration and must all be treated as compromised.

### 7.1 Rotate every secret

| Secret | Rotation step | Update afterward |
|---|---|---|
| Prem SSH password (`jono@prem`) | `passwd jono` on prem (over Tailscale SSH; do not use the password being rotated) | Vault item `mml/prem/ssh` |
| Hetzner Read-Write API key | Hetzner console → Security → API Tokens → revoke old, generate new | Vault item `mml/hetzner/api-key` |
| Tailscale OAuth client secret | Tailscale admin console → Settings → OAuth Clients → revoke old, generate new | Vault item `mml/tailscale/oauth-secret` |
| PG `replicator` password | Prem: `ALTER ROLE replicator WITH PASSWORD '<new>'`; update `primary_conninfo` on Hetzner standby and reload | Vault item `mml/pg/replicator-password`; Hetzner `postgresql.auto.conf` |
| Hetzner PG admin password | Same `ALTER ROLE` pattern; update Docker Compose env | Vault item `mml/hetzner/pg-admin-password` |
| Cloudflare Origin Cert + key (×5: petpro.co.nz, mml.co.nz, mmlakl.co.nz, enkelshop.com, volere.com.au) | Cloudflare dashboard → SSL/TLS → Origin Server → revoke each old cert, generate fresh 15-year cert per domain. Install on **prem first, then Hetzner**, validate `curl https://<domain>` end-to-end before revoking previous certs | Vault items `mml/tls/<domain>.{cert,key}`; files at `/etc/ssl/cloudflare/<domain>.{pem,key}` on both servers |

Rotation order matters: rotate SSH passwords last so you can still reach prem to run the PG `ALTER ROLE`. If you lock yourself out, Tailscale SSH key auth is the recovery path — confirm key auth works *before* starting.

### 7.2 Delete the plaintext store

After every consumer is reading from the vault and a 7-day soak confirms nothing silently still depends on the file:

```bash
# Verify no remaining references
grep -rni "ssh\.txt\|certificates/.*\.txt" E:/ClaudeCode/projects/mml.odoo/

# Secure-delete (Windows)
sdelete.exe -p 3 E:/ClaudeCode/projects/mml.odoo/mml.hiav/ssh.txt
sdelete.exe -p 3 E:/ClaudeCode/projects/mml.odoo/mml.hiav/certificates/*.txt
rmdir E:/ClaudeCode/projects/mml.odoo/mml.hiav/certificates

# Update mml.hiav/CLAUDE.md to remove the "ssh.txt — contains credentials" section
# and replace with the vault access procedure.
```

### 7.3 Sanity-check git history

```bash
# From each MML repo root
git log --all --full-history -- "**/ssh.txt" "**/certificates/*.txt"
git log -p --all -S "BEGIN PRIVATE KEY" -- "*.txt"
```

Any history hit means treat the affected repo as containing a leaked secret: rewrite history with `git filter-repo` and rotate again — those secrets are permanently in any clone anyone has pulled.

### 7.4 Document the vault access path

Update `mml.hiav/CLAUDE.md` to replace the SSH Access section with:

- Vault location (URL or self-host endpoint)
- Authentication (CLI command, recovery kit location)
- How to add a secret
- How to rotate (per-secret runbook reference)
- Where the offline recovery kit is physically stored
- Break-glass contact (vendor support for managed; pointer to recovery kit for self-host)

### 7.5 Add a guardrail

Pre-commit hook (or CI check) on every MML repo that fails the commit if a file matching `ssh.txt`, `*.pem`, `*.key`, `*.p12`, or content matching `BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY` is staged. Tools: `gitleaks`, `trufflehog`, or a custom shell hook. Prevents recurrence in whatever directory replaces `mml.hiav/` for planning notes.

---

## Appendix: notes on data not verified

- **Pricing** checked April 2026 via vendor sites and third-party trackers. Pricing changes; verify at signup. NZD figures use ~1.65 USD→NZD which floats daily.
- **Cloudflare Origin Cert** validity defaults to 15 years per Cloudflare's published convention; existing certs were generated at unknown dates — the rotation step in 7.1 makes the date question moot.
- **HashiCorp Vault HCP** end-of-life dates (2026-07-01) confirmed via HashiCorp's migration notice.
- **Infisical SSH CA** has been on the public roadmap since 2025; verify current status before relying on it.
- **AWS region pricing** for ap-southeast-2 (Sydney) is closest to NZ but cross-Tasman; no NZ-resident regulatory requirements currently apply to MML.
