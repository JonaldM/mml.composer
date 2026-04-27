# Platform-Layer Module Tests

This directory holds tests for MML's platform-tier modules — the
infrastructure layer that has no app-level UI but still needs UI
verification (admin reachability, model registration, ACL contracts).

## Modules covered

| Module | Test class / runner | Why it's here |
|--------|---------------------|---------------|
| `mml_base` | `test_mml_base.MmlBaseUiTests` | Capability/event/license/subscription registry. No menu, only Technical-menu reachability. |
| `mml_petpro_storefront_user` | `test_mml_petpro_storefront_user.MmlPetproStorefrontUserTests` | Group + `res.users` template added by P2. SKIP-friendly when not installed. |
| `mml_roq_freight` | `test_bridges_headless.run_mml_roq_freight_checks` | Bridge between ROQ Forecast and freight. No UI by design. |
| `mml_freight_3pl` | `test_bridges_headless.run_mml_freight_3pl_checks` | Bridge between freight and 3PL drivers. No UI by design. |

## Test tiers (per module)

Following the pattern set by `mml_test_sprint/modules/base_module.py`:

- **Smoke** — can a privileged user reach the module's surface area
  without errors? For mml_base this means navigating the Technical menu
  and confirming each platform model is registered. For bridges this
  means the module is in `state='installed'`.
- **Spec** — do the documented fields/groups/templates exist as
  declared in the module's CLAUDE.md? Probed via `ir_model_fields`,
  `res_groups`, `ir_ui_view`.
- **Workflows** — does the ACL contract hold (group_user read-only,
  group_system full CRUD)? Are there any persisted records that
  violate the documented invariants (e.g. `handler_method`s that
  don't match `^_on_[a-z_]+$`)?

## Running

The tests register themselves into the standard runner. From the repo root:

```bash
python -m mml_test_sprint
```

Run against a specific target by editing `mml_test_sprint/config.py`,
or via env vars (read in `mml_test_sprint/helpers/__init__.py`):

```bash
MML_TEST_BASE_URL=http://100.94.135.90:8090 \
MML_TEST_DATABASE=MML_19_prod_test \
MML_TEST_LOGIN=jono@mml.co.nz \
MML_TEST_PASSWORD=Test123 \
python -m mml_test_sprint
```

## Hetzner test target

Canonical target for the sprint (Tailscale):

- URL: `http://100.94.135.90:8090`
- DB: `MML_19_prod_test`
- Login: `jono@mml.co.nz` / `Test123`

The harness's existing `config.py` defaults point at `46.62.148.99:8090`
(mml_dev). Switch by editing `BASE_URL`/`DATABASE`/`LOGIN_*` or
overriding via env (see env section above).

## Why mml_base is "headless plus UI"

`mml_base` ships **no menu**, **no `ir.actions.act_window`**, and
`application = False`. It still has a UI surface that admins use:

1. `Settings -> Technical -> Database Structure -> Models` (the
   built-in `base.action_model_model`) — every `mml.*` model must
   appear here.
2. The auto-generated list/form Odoo offers when you drill from the
   Technical menu into a specific model.

The smoke tier verifies path (1) renders. The spec tier verifies the
contract via `ir_model_fields`, because writing a fragile selector
against the auto-generated form view buys nothing.

## Skips and known gaps

- **Dispatch failure model.** `mml.event.dispatch.failure` is added by
  S4 (post-this-sprint). All dispatch-failure assertions SKIP if the
  model is absent.
- **Storefront user module.** Not yet deployed to the canonical test
  target. All assertions SKIP cleanly when `mml_petpro_storefront_user`
  is not installed.
- **license_key field-level groups.** Odoo registers field-level
  `groups=` declarations into `ir_model_fields_group_rel` only on some
  versions. The check WARNs (rather than FAILs) when the row isn't
  present, since the constraint may be enforced solely at the Python
  level via the field decorator.
