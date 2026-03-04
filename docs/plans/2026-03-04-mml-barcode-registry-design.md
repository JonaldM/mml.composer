# MML Barcode Registry — Design Document

**Date:** 2026-03-04
**Module:** `mml_barcode_registry`
**Version:** 19.0.1.0.0
**Repo:** https://github.com/JonaldM/mml.barcodes
**Author:** MML / Harold (reviewed by Jono)
**Status:** Approved — ready for implementation planning

---

## 1. Objective

Replace the existing Excel-based GTIN allocation spreadsheet with a native Odoo 19 module providing barcode lifecycle management, one-click GTIN allocation, and full assignment history.

**Current state:** 897 of 1,000 GTIN-13 sequences allocated under prefix `9419416`. 103 remaining. No SSCC generation (deferred). No link between barcodes and Odoo product records.

---

## 2. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| `mml.brand` location | Inside `mml_barcode_registry` | Module independence; other modules cannot depend on this one. `mml_base` stays platform-only. |
| `mml_base` integration | Full — capabilities, service locator, billing events | Built for SaaS from day one; `barcode.gtin.allocated` events enable metered billing. |
| XLSX import | Both XLSX (`openpyxl`) and CSV | Broader market — not all self-hosted deployments guarantee `openpyxl`. |
| Dashboard | Standard Odoo views (graph + tree + menu composition) | No custom OWL required; sufficient for v1. Can be upgraded to OWL dashboard in a future sprint. |
| Architecture | Registry + Allocation split (Approach B) | Full assignment history per GTIN; supports retail compliance, GS1 reuse audit trail, and larger enterprise customers. |

---

## 3. Architecture & Module Structure

```
barcodes/
└── mml_barcode_registry/
    ├── __init__.py
    ├── __manifest__.py           # depends: mml_base, stock, product, mail
    ├── hooks.py                  # register capabilities + billing event on install/uninstall
    ├── models/
    │   ├── __init__.py
    │   ├── mml_brand.py          # mml.brand
    │   ├── barcode_prefix.py     # mml.barcode.prefix
    │   ├── barcode_registry.py   # mml.barcode.registry (GTIN pool)
    │   ├── barcode_allocation.py # mml.barcode.allocation (assignment history)
    │   └── product_product.py    # product.product _inherit
    ├── services/
    │   ├── __init__.py
    │   ├── gs1.py                # Pure Python MOD-10 check digit (no self.env)
    │   └── barcode_service.py    # BarcodeService — allocate_next(), get_allocation()
    ├── wizard/
    │   ├── __init__.py
    │   └── barcode_import_wizard.py  # XLSX + CSV seed import
    ├── views/
    │   ├── mml_brand_views.xml
    │   ├── barcode_registry_views.xml
    │   ├── barcode_allocation_views.xml
    │   ├── barcode_prefix_views.xml
    │   ├── product_views.xml
    │   ├── dashboard_views.xml
    │   ├── wizard_views.xml
    │   └── menu.xml
    ├── security/
    │   ├── ir.model.access.csv
    │   └── barcode_registry_security.xml  # record rules (company_id)
    ├── data/
    │   └── barcode_prefix_data.xml        # MML primary prefix seed
    ├── tests/
    │   ├── __init__.py
    │   ├── test_gs1.py
    │   ├── test_allocation.py
    │   ├── test_generate_sequences.py
    │   ├── test_lifecycle.py
    │   └── test_import_wizard.py
    └── static/
        └── description/
            └── icon.png
```

**Core architectural split:**
- `mml.barcode.registry` = the GTIN number pool. One record per number slot. Never deleted. Pool-level status only.
- `mml.barcode.allocation` = the assignment event. One record per product-per-GTIN assignment. Accumulates across reuse cycles. Never deleted.

---

## 4. Data Model

### 4.1 `mml.brand`

| Field | Type | Notes |
|---|---|---|
| name | Char | required |
| company_id | Many2one → res.company | multi-company |

### 4.2 `mml.barcode.prefix`

| Field | Type | Notes |
|---|---|---|
| name | Char | e.g. "MML Primary" |
| prefix | Char(7) | e.g. "9419416" |
| sequence_start | Integer | First sequence in block |
| sequence_end | Integer | Last sequence in block |
| next_sequence | Integer | Computed — next unallocated |
| capacity | Integer | Computed — total slots |
| allocated_count | Integer | Computed — non-unallocated records |
| utilisation_pct | Float | Computed — allocated_count / capacity * 100 |
| active | Boolean | Default True |
| priority | Integer | Default 10; lower = used first |
| company_id | Many2one → res.company | |

### 4.3 `mml.barcode.registry`

The GTIN pool. One record per number slot. Never deleted.

| Field | Type | Notes |
|---|---|---|
| sequence | Char(12) | 12-digit sequence (no check digit) |
| check_digit | Integer | Computed+stored, GS1 MOD-10 |
| gtin_13 | Char(13) | Computed+stored, UNIQUE index |
| gtin_14 | Char(14) | Computed+stored, UNIQUE index |
| prefix_id | Many2one → mml.barcode.prefix | |
| status | Selection | `unallocated \| reserved \| in_use \| retired` |
| current_allocation_id | Many2one → mml.barcode.allocation | Nullable; active allocation |
| allocation_ids | One2many → mml.barcode.allocation | Full history |
| reuse_eligible_date | Date | Computed — from latest allocation's reuse_eligible_date |
| company_id | Many2one → res.company | |

**SQL constraints:**
```python
_sql_constraints = [
    ('gtin13_uniq', 'UNIQUE(gtin_13)', 'GTIN-13 must be unique.'),
    ('gtin14_uniq', 'UNIQUE(gtin_14)', 'GTIN-14 must be unique.'),
    ('sequence_prefix_uniq', 'UNIQUE(sequence, company_id)', 'Sequence must be unique per company.'),
]
```

### 4.4 `mml.barcode.allocation`

Assignment history. One record per product-per-GTIN assignment. Never deleted.

| Field | Type | Notes |
|---|---|---|
| registry_id | Many2one → mml.barcode.registry | required |
| product_id | Many2one → product.product | required |
| brand_id | Many2one → mml.brand | |
| status | Selection | `active \| dormant \| discontinued` |
| allocation_date | Date | Date assigned |
| discontinue_date | Date | Date product was discontinued |
| reuse_eligible_date | Date | Computed — discontinue_date + 48 months |
| notes | Text | |
| company_id | Many2one → res.company | |

---

## 5. State Machine

### Registry status
```
unallocated → in_use        (on allocation creation)
in_use      → retired       (manual override only, or if allocation discontinued + 48mo not yet passed)
retired     → unallocated   (when allocation discontinued AND reuse_eligible_date <= today)
```

### Allocation status
```
active      → dormant       (product archived)
dormant     → active        (product un-archived; registry stays in_use)
dormant     → discontinued  (manual; validates reuse_eligible_date <= today)
```

When allocation is `discontinued`, registry reverts to `unallocated` — the GTIN slot is back in the pool.

---

## 6. Core Logic

### 6.1 GS1 MOD-10 (`services/gs1.py`)

Pure Python, no Odoo dependency. Handles both 12-digit (GTIN-13) and 13-digit (GTIN-14) inputs.

```python
def compute_check_digit(sequence: str) -> int:
    digits = [int(d) for d in sequence]
    odd_sum = sum(digits[i] for i in range(0, len(digits), 2))
    even_sum = sum(digits[i] for i in range(1, len(digits), 2))
    if len(digits) % 2 == 0:   # GTIN-13: 12-digit input
        total = odd_sum + even_sum * 3
    else:                       # GTIN-14: 13-digit input
        total = odd_sum * 3 + even_sum
    return (10 - (total % 10)) % 10
```

### 6.2 One-Click Allocation

Triggered from `product.product` form.

1. Query `mml.barcode.prefix` — active, ordered by `priority ASC`, then `utilisation_pct ASC`
2. `SELECT ... FOR UPDATE SKIP LOCKED` on `mml.barcode.registry` — first `unallocated` record for prefix, ordered `sequence ASC`
3. If none: raise `UserError` with remaining capacity count and GS1 NZ contact link
4. Create `mml.barcode.allocation` (`status=active`, `allocation_date=today`, `product_id`, `brand_id` from product template)
5. Update registry: `status=in_use`, `current_allocation_id=new allocation`
6. Write `gtin_13` → `product.barcode`; create `product.packaging` (`name="Outer Carton"`, `barcode=gtin_14`, `qty=1`, `product_id=product`)
7. Emit `mml.event` — `event_type='barcode.gtin.allocated'`, `billable_unit='gtin'`, `quantity=1.0`
8. Return `ir.actions.client` display_notification

### 6.3 Generate Sequences

On `mml.barcode.prefix`. Idempotent bulk-create of unallocated registry records across the full prefix range. Skips existing sequences. Batch-creates in chunks of 1,000. Returns notification with count created.

### 6.4 Auto-Discontinue Hook (`product.product.write()`)

- `active → False`: find active allocation for product → `action_dormant()` → sets `discontinue_date=today`, computes `reuse_eligible_date`
- `active → True` (un-archive): find dormant allocation for product → `action_reactivate()` → status back to `active`

### 6.5 `BarcodeService` (`services/barcode_service.py`)

Registered with `mml.registry` under key `'barcode'`. Exposes:
- `allocate_next(env, product_id: int) -> dict` — returns `{gtin_13, gtin_14, allocation_id}`
- `get_allocation(env, product_id: int) -> dict | None`

Allows other modules to call barcode operations via service locator without a hard import.

---

## 7. Views & UX

### Registry list view
Tree with `decoration-success/warning/muted` status badges. Columns: GTIN-13, GTIN-14, Current Allocation, Status, Prefix. Search by status, reuse-eligible filter. Group by Status (default), Prefix.

### Allocation list view
Full history per GTIN. Columns: GTIN-13, Product, Brand, Status, Allocation Date, Discontinue Date, Reuse Eligible Date. Accessible via registry form One2many tab and standalone menu.

### Prefix form view
Stat buttons: active / dormant / unallocated counts (click-through to filtered registry list). Utilisation field: `{allocated_count} / {capacity} ({utilisation_pct:.1f}%)`. "Generate Sequences" button (visible when `allocated_count < capacity`). Red inline alert when `utilisation_pct > 90`.

### Dashboard (homepage)
- Homepage action opens registry list view, grouped by status
- Menu item: "By Brand" — graph view of allocations grouped by brand (bar chart)
- Menu item: "By Status" — graph view of registry grouped by status (pie chart)
- Menu item: "Prefixes" — prefix list view with utilisation

### Product form integration
- Smart button: "Barcode" with GTIN-13 (visible when allocated; links to allocation record)
- "Allocate Barcode" button: visible only when `product.barcode` is empty
- Warning banner: `product.barcode` set but no registry allocation found ("Not tracked — Register it")

### Import wizard
Upload (XLSX or CSV), prefix selector, preview first 10 rows, confirm. On confirm: validates check digits (flags mismatches as warnings), matches products by `barcode` field, creates registry + allocation records. Idempotent.

---

## 8. Security

| Model | Internal User | Stock Manager | Admin/Settings |
|---|---|---|---|
| `mml.barcode.registry` | Read | Full CRUD | Full CRUD |
| `mml.barcode.allocation` | Read | Full CRUD | Full CRUD |
| `mml.barcode.prefix` | Read | Read | Full CRUD |
| `mml.brand` | Read | Read/Write | Full CRUD |
| Import wizard | — | Access | Access |

Record rules: `company_id`-based multi-company isolation on all models.

---

## 9. mml_base Integration

**`post_init_hook`:**
```python
env['mml.capability'].register([
    'barcode.allocate',
    'barcode.generate_sequences',
    'barcode.registry.read',
], module='mml_barcode_registry')
env['mml.registry'].register('barcode', BarcodeService)
```

**`uninstall_hook`:** deregisters all capabilities, service, and event subscriptions.

**Billing event:** `event_type='barcode.gtin.allocated'`, `billable_unit='gtin'`, `quantity=1.0`, emitted on every allocation.

---

## 10. Testing

| Test file | Coverage |
|---|---|
| `test_gs1.py` | MOD-10 against 10 known GTIN pairs; pure unit, no DB |
| `test_allocation.py` | One-click flow; exhausted prefix error; concurrency (FOR UPDATE SKIP LOCKED); multi-prefix fallover |
| `test_generate_sequences.py` | Exact count creation; idempotency |
| `test_lifecycle.py` | All valid/invalid transitions; 48-month guard; archive/unarchive hook; full reuse cycle |
| `test_import_wizard.py` | XLSX + CSV; 897 active + 103 unallocated; check digit warnings; idempotency |

---

## 11. Out of Scope (Future Sprints)

- SSCC-18 pallet label generation (deferred to EDI ASN sprint)
- GS1-128 / DataMatrix barcode image generation
- Physical label printing integration
- GS1 NZ National Product Catalogue API integration
- Custom OWL dashboard with live capacity gauge
- Chatter-based audit trail on registry records
