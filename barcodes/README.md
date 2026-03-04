# MML Barcode Registry

Odoo 19 module that replaces MML's Excel GTIN spreadsheet with a full barcode lifecycle registry, one-click GTIN allocation, and a seed import wizard.

**Module:** `mml_barcode_registry`
**Depends on:** `mml_base`, `stock`, `product`, `mail`
**Application:** Yes — appears as standalone "Barcodes" tile on the home screen

---

## What it does

| Feature | Description |
|---------|-------------|
| **GTIN pool** | `mml.barcode.registry` — permanent record per GTIN-13; never deleted |
| **Allocation history** | `mml.barcode.allocation` — one row per product/GTIN assignment; accumulates across reuse cycles |
| **One-click allocation** | "Allocate Barcode" button on product form; atomically claims next available GTIN with `FOR UPDATE SKIP LOCKED` |
| **GS1 48-month rule** | Discontinued GTINs cannot be reused until 48 months after discontinuation; enforced at the model layer |
| **Archive hook** | Archiving a product automatically sets its allocation dormant; un-archiving reactivates it |
| **Import wizard** | Upload existing XLSX or CSV spreadsheet to seed the registry from your historical data |
| **Billing events** | Emits `barcode.gtin.allocated` event to `mml.event` on each allocation for usage metering |

---

## GS1 Lifecycle

```
Registry:   unallocated ──► in_use ──► retired ──► unallocated (after 48 months)

Allocation: active ──► dormant ──► discontinued
                 ▲         │           │
                 └─────────┘           └── registry returns to unallocated pool
                (reactivate)
```

- **unallocated** — GTIN is in the pool, ready to assign
- **in_use** — GTIN is assigned to a live product
- **retired** — product discontinued; GTIN in 48-month cool-down
- **unallocated (again)** — GTIN back in pool after cool-down

---

## Module structure

```
mml_barcode_registry/
├── models/
│   ├── mml_brand.py              ← Brand master (links to product category)
│   ├── barcode_prefix.py         ← GS1 prefix config + bulk sequence generation
│   ├── barcode_registry.py       ← GTIN pool (permanent records)
│   ├── barcode_allocation.py     ← Assignment history + state machine
│   └── product_product.py        ← Inherit: one-click allocate, archive hook
├── services/
│   ├── gs1.py                    ← Pure Python: MOD-10 check digit, GTIN-13/14 builder
│   └── barcode_service.py        ← mml_base service locator adapter
├── wizard/
│   └── barcode_import_wizard.py  ← XLSX/CSV import with check digit validation
├── views/                        ← Odoo form/list/search/graph views + menus
├── security/                     ← ACL + company-scoped record rules
├── data/
│   └── barcode_prefix_data.xml   ← MML primary GS1 prefix seed (9419416, noupdate)
└── tests/
    ├── test_gs1.py               ← Pure Python: MOD-10 algorithm
    ├── test_generate_sequences.py ← Prefix sequence generation
    ├── test_lifecycle.py         ← Allocation + registry state machines
    ├── test_allocation.py        ← Archive hook + one-click allocation
    └── test_import_wizard.py     ← CSV/XLSX import wizard
```

---

## First-time setup

1. Install the module:
   ```bash
   odoo-bin -d <db> -i mml_barcode_registry --stop-after-init
   ```

2. The MML primary prefix (`9419416`) is seeded automatically with `noupdate="1"`.

3. Go to **Barcodes → Configuration → Prefixes**, open **MML Primary**, and click **Generate Sequences** to populate the pool (creates ~88,001 registry slots from sequence 11999–99999).

4. Optionally use **Barcodes → Import** to bulk-load existing GTIN assignments from your spreadsheet. The wizard accepts CSV or XLSX and matches products by barcode or name.

---

## One-click allocation

On any product form (requires `stock.group_stock_manager`):

1. The **"Allocate Barcode"** link appears next to the Barcode field when the product has no barcode.
2. Clicking it atomically claims the next unallocated GTIN from the highest-priority prefix.
3. The product's `barcode` field is set to the GTIN-13, a packaging record (GTIN-14 outer carton) is created, and a `barcode.gtin.allocated` billing event is emitted.

---

## Import wizard CSV format

| Column | Required | Notes |
|--------|----------|-------|
| `sequence` | Yes | 12-digit full sequence (prefix + zero-padded suffix) |
| `gtin_13` | No | If supplied, check digit is validated; computed value is always used |
| `description` | No | Matched against product name (case-insensitive) if barcode match fails |

The wizard is **idempotent** — re-importing the same rows will not create duplicate records.

---

## Running tests

```bash
# Pure Python (no Odoo instance needed)
cd barcodes
python -m pytest mml_barcode_registry/tests/test_gs1.py -v

# Odoo model tests
odoo-bin -d <db> --test-tags=/mml_barcode_registry --stop-after-init
```

---

## Security model

| Group | Brand | Prefix | Registry | Allocation | Wizard |
|-------|-------|--------|----------|------------|--------|
| `base.group_user` | read | read | read | read | — |
| `stock.group_stock_manager` | read/write/create | — | read/write/create | read/write/create | full |
| `base.group_system` | full | full | full | full | full |

Record rules enforce company-level isolation on all models.
The **Configuration** menu (Prefixes, Brands) is restricted to `base.group_system`.
