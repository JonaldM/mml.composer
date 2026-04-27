# mml_petpro_storefront_user — PetPro Storefront RPC User

**Module:** `mml_petpro_storefront_user`
**Application:** No (`application = False` — purely declarative; no UI, no Python models)
**Depends on:** `base`, `sale`, `stock`, `product`, `account`, `delivery`, `payment`

---

## Why this module exists

The headless petpro.co.nz Next.js storefront talks to Odoo over JSON-RPC.
Historically it has authenticated as the `ODOO_ADMIN_EMAIL` admin user, which
means **every** product query, cart write, and partner lookup runs at admin
scope. Any user input that flows into `client.call()` therefore has the full
ERP in its blast radius.

This module closes that defense-in-depth gap by scaffolding:

1. A `res.groups` row — `MML PetPro Storefront`
2. A minimum-privilege `ir.model.access.csv` attached to that group
3. A `res.users` template — `petpro_storefront@petpro.co.nz`

After install the operator sets a password + API key out-of-band, swaps the
storefront's environment variables, and admin credentials are no longer in
the storefront container.

---

## ACL footprint (what the storefront user can see)

| Model | Read | Write | Create | Unlink |
|---|---|---|---|---|
| `product.template` | yes | no | no | no |
| `product.product` | yes | no | no | no |
| `product.category` | yes | no | no | no |
| `product.pricelist` | yes | no | no | no |
| `product.pricelist.item` | yes | no | no | no |
| `product.attribute` | yes | no | no | no |
| `product.attribute.value` | yes | no | no | no |
| `product.template.attribute.line` | yes | no | no | no |
| `stock.quant` | yes | no | no | no |
| `res.partner` | yes | yes | yes | **no** |
| `sale.order` | yes | yes | yes | **no** |
| `sale.order.line` | yes | yes | yes | **no** |
| `account.move` | yes | no | no | no |
| `account.move.line` | yes | no | no | no |
| `delivery.carrier` | yes | no | no | no |
| `payment.transaction` | yes | no | no | no |

Every other model is implicitly denied (Odoo's default).

### Trade-offs

- `res.partner` write+create — required for guest checkout to attach a delivery
  address. This is the highest-privilege grant in the set. Guest checkout is
  expected to use a single shared `ODOO_GUEST_PARTNER_ID` parent partner with
  delivery addresses created as child records, which limits the surface to
  *creating* contacts, not *editing arbitrary* contacts. Record rules on
  `res.partner` are out of scope for this scaffold and should follow up if
  required (e.g. restrict update to records the storefront created within the
  current session).
- `sale.order` / `sale.order.line` — no `unlink`. The storefront cannot
  delete orders. Cart abandonment is handled by Odoo's standard cron (or by
  flagging draft orders, not deleting them).
- `account.move` — read only. The storefront displays invoice PDFs and
  totals; it never issues refunds or credit notes.
- `payment.transaction` — read only. Payment state changes flow through the
  payment provider's webhook into Odoo's standard payment module, not
  through the storefront RPC user.

---

## Install

From the parent `mml.odoo.apps` repo on the Odoo host:

```bash
git pull
odoo-bin -d <db> -i mml_petpro_storefront_user --stop-after-init
```

Then follow the runbook to set the password and switch storefront credentials:

```
docs/operations/2026-04-27-petpro-storefront-user-runbook.md
```

The user **cannot log in** until that runbook is completed — by design.
