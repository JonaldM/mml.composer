# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Read the root `mml.odoo.apps/CLAUDE.md` first for platform-wide conventions. This file covers `mml.barcodes`-specific detail only.

---

## Module: `mml_barcode_registry`

GTIN lifecycle management for MML's ~400 SKUs. Manages GS1 number blocks (prefixes), generates GTIN-13/GTIN-14 sequences, and allocates barcodes to products with one click. Depends on `mml_base`, `stock`, `product`, `mail`.

---

## Running Tests

**Pure-Python only** (GS1 math, no Odoo needed):
```bash
# From mml.barcodes/ — no conftest.py here, so point pytest at the test file directly
pytest mml_barcode_registry/tests/test_gs1.py -q
```

`test_gs1.py` manually inserts the `services/` directory into `sys.path`, so it runs standalone without any conftest.

**Odoo integration tests** (require live Odoo database — all other test files):
```bash
python odoo-bin --test-enable -u mml_barcode_registry -d <db> --stop-after-init
```

> Note: This workspace has no `conftest.py` or `pytest.ini`. The root `mml.odoo.apps/conftest.py` installs Odoo stubs but is not automatically picked up unless pytest is run from the repo root. All tests except `test_gs1.py` are Odoo integration tests (`TransactionCase`) and require `odoo-bin`.

---

## Architecture

### Models

| Model | Table | Purpose |
|-------|-------|---------|
| `mml.barcode.prefix` | `mml_barcode_prefix` | GS1 7-digit company prefix block (e.g. `9419416`), defines sequence range and priority |
| `mml.barcode.registry` | `mml_barcode_registry` | One record per GTIN slot; stores 12-digit sequence, computed GTIN-13/GTIN-14, and lifecycle status |
| `mml.barcode.allocation` | `mml_barcode_allocation` | Links a registry slot to a product; maintains allocation history |
| `mml.brand` | `mml_brand` | Thin brand lookup used to tag allocations (matched from product category name) |
| `product.product` (extended) | — | Adds `barcode_allocation_id`, `barcode_in_registry`, one-click `action_allocate_barcode()` |

### Registry Lifecycle (state machine)

```
unallocated → reserved → in_use → retired → unallocated (after 48-month cool-down)
unallocated → in_use (direct, via one-click allocate)
```

Transitions are validated by `_validate_transition()` — any invalid hop raises `UserError`.

### Allocation Lifecycle (state machine)

```
active → dormant → active  (reactivate)
dormant → discontinued  (blocked until reuse_eligible_date; returns registry slot to pool)
```

- `action_dormant()` sets `discontinue_date = today` and `reuse_eligible_date = today + 48 months`.
- `action_discontinue()` enforces the 48-month cool-down. On success, sets registry back to `unallocated`.
- Product archive/unarchive automatically triggers `action_dormant()` / `action_reactivate()` via the `product.product.write()` override.

### One-Click Allocation (`product.product.action_allocate_barcode`)

1. Finds the lowest-priority active prefix that still has unallocated slots.
2. Claims the next slot using `SELECT FOR UPDATE SKIP LOCKED` (race-safe).
3. Creates `mml.barcode.allocation` record.
4. Sets `registry.status = 'in_use'`.
5. Writes GTIN-13 to `product.barcode`.
6. Creates a `product.packaging` record (name `'Outer Carton'`) with the GTIN-14.
7. Emits `barcode.gtin.allocated` event to `mml.event` (best-effort; failure does not roll back the allocation).

### GS1 Math (`services/gs1.py`)

Pure Python, no Odoo dependency. Implements GS1 MOD-10 check digit.

- `compute_check_digit(sequence: str) -> int` — works on sequences of any even or odd length.
- `build_gtin13(sequence: str) -> str` — appends check digit to a 12-digit sequence.
- `build_gtin14(sequence: str) -> str` — prepends indicator digit `'1'`, appends check digit; always 14 digits.

GTIN-14 indicator digit is hardcoded to `'1'` (standard outer carton).

### Import Wizard (`barcode.import.wizard`)

CSV/XLSX import for migrating existing GS1 records. Accepts columns: `sequence` (12-digit, required), `gtin_13` (optional, validated against computed value), `description` (optional, used to match and auto-allocate to a product by barcode then by name). Idempotent — re-importing skips existing sequences. Requires `openpyxl` for XLSX; falls back to a helpful error if not installed.

### Platform Integration

- `hooks.py` registers capabilities (`barcode.allocate`, `barcode.generate_sequences`, `barcode.registry.read`) and the `BarcodeService` service locator key `'barcode'` with `mml_base` on install.
- `BarcodeService` in `services/barcode_service.py` is the inter-module API surface — other modules call it via `env['mml.registry'].get('barcode')` without importing this module directly.

---

## Seeded Data

`data/barcode_prefix_data.xml` seeds the MML primary prefix (`9419416`, range `11999–99999`, `noupdate="1"`). After install, run **"Generate Sequences"** from the Barcode Prefixes menu to populate the pool (up to 88,001 slots, chunked in 1,000-record batches). The hard cap per `action_generate_sequences()` call is 100,000 slots.

---

## Key Constraints

- GS1 prefix must be exactly 7 digits (`_check_prefix_format`).
- `gtin_13` and `gtin_14` are unique across the entire table (SQL constraints).
- `sequence` is unique per company.
- Prefix is unique per company.
- Brand name is unique per company.
- `ondelete='restrict'` on `registry_id` in allocations — you cannot delete a registry record that has allocation history.

## Available Commands

- `/tdd` — write tests first; pure-Python GS1 math tests run without Odoo
- `/plan` — implementation plan before adding new allocation states or import logic
- `/code-review` — review before pushing module updates
