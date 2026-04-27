# Runbook: Switch the PetPro storefront from admin RPC to a dedicated user

**Date:** 2026-04-27
**Author:** Claude (sprint P2)
**Audience:** Jonathan / ops on duty
**Module shipped in this PR:** `mml_petpro_storefront_user`
**Scope:** PetPro Next.js storefront (`pet.pro.website`) + Odoo 19 host
**Estimated downtime:** None if you keep the admin creds in place until the swap. ~30 seconds during the env reload otherwise.

---

## Why we are doing this

The petpro.co.nz storefront is a headless Next.js app that talks to Odoo
over JSON-RPC. Today the server-side `getOdooClient()` factory authenticates
with `ODOO_ADMIN_EMAIL` / `ODOO_ADMIN_PASSWORD` — i.e. **every** product
query, cart write, and partner lookup runs at admin scope. Any user input
that reaches `client.call()` therefore has the full Odoo ERP in its blast
radius (e.g. could read `account.move`, `hr.employee`, `mml.license`, etc.,
even though the storefront has no UI for it).

Defense-in-depth: the storefront should authenticate as a dedicated
`petpro_storefront@petpro.co.nz` user that is *only* a member of the
`MML PetPro Storefront` group, which has the minimum ACLs declared in
`mml_petpro_storefront_user/security/ir.model.access.csv`.

This runbook describes the manual steps to flip from admin → dedicated user.

---

## What this PR provides

```
mml_petpro_storefront_user/
├── __manifest__.py
├── __init__.py
├── README.md
├── security/
│   ├── petpro_storefront_groups.xml   ← res.groups "MML PetPro Storefront"
│   └── ir.model.access.csv             ← min-priv ACLs for that group
├── data/
│   └── petpro_storefront_user.xml     ← res.users template (NO password)
└── tests/
    ├── __init__.py
    └── test_acl_csv.py                 ← pure-pytest CSV/XML structural test
```

**Important:** The user template intentionally ships **without a password**.
The user is created in a "cannot log in" state. You set the password in
step 4 below. This is by design — fail closed.

---

## Steps

### 1. Pull the parent repo on the Odoo host

```bash
ssh ops@<odoo-host>
cd /opt/odoo/addons/mml.odoo.apps   # adjust to your install path
git fetch origin
git checkout master
git pull
# Or, while the branch is still open:
git checkout claude-sprint/petpro-odoo-user-scaffold
```

Verify the new module appears:

```bash
ls mml_petpro_storefront_user/
```

You should see `__manifest__.py`, `security/`, `data/`, etc.

---

### 2. Install the module

```bash
sudo -u odoo /opt/odoo/odoo-bin \
    --config /etc/odoo/odoo.conf \
    -d <database-name> \
    -i mml_petpro_storefront_user \
    --stop-after-init
```

Then restart the running Odoo systemd service:

```bash
sudo systemctl restart odoo
```

Watch the logs for any `IntegrityError` or ACL warnings:

```bash
sudo journalctl -u odoo -f --since "2 minutes ago"
```

Expected: clean install. The user `petpro_storefront@petpro.co.nz` exists
but has no password, so it cannot log in (yet). That is correct.

---

### 3. Sanity-check the group + ACL footprint

In Odoo UI:

1. Open **Settings → Users & Companies → Groups**.
2. Search "MML PetPro Storefront". Confirm exactly one group exists.
3. Open the group. Under **Access Rights**, confirm the rows match the
   table in `mml_petpro_storefront_user/README.md`:
   - 13 read-only entries (catalogue, stock, invoices, delivery, payment,
     attributes)
   - 3 read/write/create-but-no-unlink entries (`res.partner`,
     `sale.order`, `sale.order.line`)
4. Confirm **Inherited** lists `Internal User` only (so the user has the
   minimum baseline portal-like access plus our explicit ACLs, nothing
   else).

---

### 4. Set the password and (preferred) generate an API key

#### Set a password

In Odoo UI:

1. **Settings → Users & Companies → Users**.
2. Search "MML PetPro Storefront" and open the record.
3. Use the **Action → Change Password** menu (Odoo 19 supports this on
   the user form). Generate a random 32-character password — do not
   reuse the admin password, do not reuse a human's password.
4. Copy the password to your password manager **before** saving.

Or via shell (faster, scriptable):

```bash
sudo -u odoo /opt/odoo/odoo-bin shell \
    --config /etc/odoo/odoo.conf \
    -d <database-name>
```

```python
import secrets
pw = secrets.token_urlsafe(32)
user = env.ref('mml_petpro_storefront_user.user_petpro_storefront')
user.password = pw
env.cr.commit()
print('PASSWORD =', pw)
```

#### Generate an Odoo API key (preferred over password for headless RPC)

Odoo 19 supports per-user API keys with their own scope and TTL. Strongly
preferred over a long-lived password.

1. Log into Odoo as the storefront user (using the password you just set,
   in a fresh incognito browser).
2. Click the user avatar → **My Profile → Account Security → New API Key**.
3. Name it `petpro-storefront-prod-2026-04-27`.
4. Copy the key. **It is shown exactly once.** Paste it into your password
   manager + into the new env var below.

---

### 5. Swap the storefront environment variables

> **Note:** The `pet.pro.website` Next.js repo lives in a separate git repo
> from `mml.odoo.apps`. The actual code change to `lib/odoo/client.ts`
> (read `ODOO_API_KEY` instead of `ODOO_ADMIN_PASSWORD`) is a follow-up
> petpro PR. Until that ships, you have two options:
>
> - **Option A (zero code change):** set `ODOO_ADMIN_EMAIL` =
>   `petpro_storefront@petpro.co.nz` and `ODOO_ADMIN_PASSWORD` = the new
>   password. The storefront then uses the new least-priv user immediately.
>   The variable *names* lie, but the runtime behaviour is correct.
> - **Option B (preferred):** wait for the petpro PR that introduces
>   `ODOO_API_KEY` / `ODOO_API_LOGIN` and uses Odoo's API-key flow. Then
>   migrate.

For Option A, on the storefront host (or in your Vercel project env):

```
# OLD
ODOO_ADMIN_EMAIL=admin@petpro.co.nz
ODOO_ADMIN_PASSWORD=<old admin pw>

# NEW
ODOO_ADMIN_EMAIL=petpro_storefront@petpro.co.nz
ODOO_ADMIN_PASSWORD=<the new password from step 4>
```

For Option B (after the petpro repo PR lands), the new convention is:

```
ODOO_API_LOGIN=petpro_storefront@petpro.co.nz
ODOO_API_KEY=<the API key from step 4>
```

Note that `ODOO_URL`, `ODOO_DB`, `ODOO_HOST` do not change.

---

### 6. Restart the storefront

```bash
# Docker compose deployment (most common):
cd /opt/petpro/pet.pro.website
docker compose down
docker compose up -d

# Or Vercel: redeploy after env-var update.
```

---

### 7. Verify

#### Health check

```bash
curl -s https://petpro.co.nz/api/health | jq .
```

Expected: `{ "ok": true, "odoo": "reachable", ... }`.

If you see `"odoo": "auth_failed"` or HTTP 500: the password / API key is
wrong, or the user lacks an ACL the storefront needs. See "Rollback" below.

#### Smoke test (manual)

1. Open https://petpro.co.nz in a fresh incognito browser.
2. Browse to `/shop` — products should render.
3. Open a PDP — variants, price, stock indicator should render.
4. Add to cart — should update the cart bubble and `/cart` page.
5. Go to `/checkout` as a guest — should be able to enter a delivery
   address and proceed to the payment step.
6. (If safe in the prod environment:) make a small test order with a
   Stripe test card.

#### Smoke test (automated)

```bash
cd /opt/petpro/pet.pro.website
pnpm test:e2e -- --grep "checkout|cart|catalogue"
```

#### Audit log spot check

In Odoo: **Settings → Technical → Logging → Audit Logs** (or your
equivalent), filter by user = `petpro_storefront@petpro.co.nz`. Confirm
you see read traffic on `product.template`, `stock.quant`, `sale.order`
matching what the storefront is doing in real time.

---

### 8. Rotate / disable the old admin credentials

Once you have confirmed the storefront is healthy on the new credentials
**for at least 24 hours**:

1. In Odoo, change the `ODOO_ADMIN_EMAIL` admin user's password to a new
   random value (kept by ops, not by the storefront).
2. Confirm the storefront still works (it should — it is no longer using
   the admin account).
3. Update your password manager. The storefront and the admin user now
   have separate, independently rotatable credentials.

---

## Trade-offs and known gaps

### `res.partner` write+create

The storefront needs to create delivery addresses for guest checkout.
The simplest thing to scaffold is `res.partner: read+write+create` for the
storefront group. This **is** a privilege escalation surface — a malicious
input could potentially update an existing partner's email if the storefront
code passed the wrong record id.

**Mitigation already in place:**

The storefront uses `ODOO_GUEST_PARTNER_ID` as a single shared parent partner
for all guest checkouts (see `pet.pro.website/lib/odoo/cart.ts`). Each guest
delivery address is created as a child record of that one parent. So in
practice the storefront only ever *creates* new contacts under one known
parent — it should never need to write to arbitrary partners.

**Future hardening (out of scope for this scaffold):**

- Add a `res.partner` record rule that restricts the storefront group to
  records where `parent_id = guest_partner_id` OR `create_uid = self.id`.
- Or: replace the model-level write/create grant with a custom controller
  endpoint that takes a delivery address, validates server-side, and
  creates the partner under the system uid — then the storefront user
  needs only `read` on `res.partner` and the controller becomes the
  trust boundary. This is a bigger change and a follow-up PR.

### `account.move` read

Read-only is correct, but exposes invoice line totals across the whole
company unless filtered by `partner_id`. The storefront's
`/account/invoices` page already does that filter in TypeScript. Future
hardening: add a record rule scoping `account.move` to
`partner_id.commercial_partner_id == env.user.partner_id`.

### Sale-order soft-cancel

Odoo's standard cron archives stale `draft` sale orders after N days; we
deliberately do not give the storefront `unlink`. If a customer abandons a
cart and the cron is too lenient, you may end up with cruft `sale.order`
rows. Tune `sale_order_cancel_cron` if needed.

---

## Rollback

If anything fails after step 6 and you cannot fix it within ~5 minutes:

1. Revert the env vars on the storefront host:
   ```
   ODOO_ADMIN_EMAIL=admin@petpro.co.nz
   ODOO_ADMIN_PASSWORD=<original admin password>
   ```
2. Restart the storefront container:
   ```bash
   docker compose down && docker compose up -d
   ```
3. Re-verify `/api/health` is green.
4. Open a sprint follow-up ticket noting which RPC call failed (search the
   Odoo log for `AccessError` or `Forbidden` against
   `petpro_storefront@petpro.co.nz`) — that will tell us which model to add
   to `ir.model.access.csv` in the next iteration of this module.

The storefront does not need to be uninstalled to roll back — only the env
var swap matters at runtime. The `petpro_storefront` user can sit dormant
until the next attempt.

---

## Acceptance criteria

This runbook is "complete" when:

- [ ] `mml_petpro_storefront_user` is installed on prod.
- [ ] The storefront user has a password and an API key.
- [ ] The storefront's `ODOO_*` env vars point at the storefront user, not
      the admin user.
- [ ] `/api/health` returns `odoo: reachable`.
- [ ] Manual + Playwright smoke tests pass against prod.
- [ ] The admin user's password has been rotated.
- [ ] Odoo audit log shows storefront RPC traffic under the storefront user.

---

## Appendix: which models the storefront actually touches

Source: `pet.pro.website/lib/odoo/`. Cross-checked against the ACL CSV.

| File | Models touched | Operations |
|---|---|---|
| `client.ts` | `res.users` (auth only) | login |
| `products.ts` | `product.template`, `product.product`, `product.category`, `product.pricelist`, `product.attribute*` | read |
| `categories.ts` | `product.category` | read |
| `cart.ts` | `sale.order`, `sale.order.line`, `res.partner` | read, write, create |
| `auth.ts` | `res.partner`, `res.users` | read, create (signup) |
| `shipping.ts` | `delivery.carrier` | read |
| `inventory.ts` | `stock.quant` | read |
| `orders.ts` | `sale.order`, `account.move` | read |
| `wishlist.ts` | `product.wishlist`, `product.product` | read, create — **NOTE:** `product.wishlist` is not currently in the ACL; if wishlist is enabled, add it as a follow-up. |
| `search.ts` | `product.template`, `product.product` | read |

If this matrix changes in a future petpro PR, update
`mml_petpro_storefront_user/security/ir.model.access.csv` to match —
**do not** widen it pre-emptively to admin scope.
