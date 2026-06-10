# mml_test_sprint — MML module test harness

A **standalone test runner** (Playwright UI checks + SSH/XML-RPC probes) for the
MML Odoo apps. It is a developer tool, not an Odoo module.

## NOT an Odoo addon — keep it OUT of `addons_path`

This directory has **no `__manifest__.py`** and must **never** be placed on, or
referenced by, any Odoo `addons_path`. Odoo would otherwise try to scan it and
its `modules/` / `playwright/` Python packages, which are test code, not addons.
Keep `mml_test_sprint/` outside every directory Odoo loads addons from.

## Configuration — environment variables only (no baked-in secrets)

This harness used to ship hardcoded defaults for the target box (its IP/URL, an
SSH key path, a root SSH login, and the password `"test"`). Those have been
**removed**. All host/credential/target values are now read from environment
variables, and the harness **fails closed** with a clear message if a required
variable is unset — it will not silently fall back to the old dev box.

Set these before running (export them, or use the `python -m mml_test_sprint`
CLI flags which populate the same vars):

| Variable | Purpose |
|---|---|
| `MML_TEST_BASE_URL` | Odoo base URL, e.g. `http://<host>:8090` |
| `MML_TEST_LOGIN_EMAIL` | Odoo login email |
| `MML_TEST_LOGIN_PASSWORD` | Odoo login password (**secret**) |
| `MML_TEST_DATABASE` | Odoo database name |
| `MML_TEST_SSH_HOST` | host used for DB queries over SSH |
| `MML_TEST_SSH_USER` | SSH user (use a least-privileged account, not root) |
| `MML_TEST_SSH_KEY` | path to the SSH private key (default `~/.ssh/id_ed25519`) |
| `MML_TEST_DB_CONTAINER` | docker container name of the DB |
| `MML_TEST_DB_USER` | postgres role |

The one-off scripts under `scripts/` read additional vars (e.g.
`MML_TEST_ODOO_CONF`, `MML_TEST_GRANT_LOGIN`, the `MML_ROQ_*` deploy paths) —
each script documents its required vars in its module docstring and exits with a
clear error if any are missing.

> Never commit real values for these variables. Use a local untracked `.env`,
> your shell profile, or a secrets manager.
