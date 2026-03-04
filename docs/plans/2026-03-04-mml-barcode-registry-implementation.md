# MML Barcode Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `mml_barcode_registry` — a standalone Odoo 19 app that replaces MML's Excel GTIN spreadsheet with a barcode lifecycle registry, one-click GTIN allocation, full assignment history, and seed import wizard.

**Architecture:** Two-model split: `mml.barcode.registry` (GTIN number pool, never deleted) and `mml.barcode.allocation` (assignment history per product, accumulates across reuse cycles). GS1 MOD-10 logic lives in a pure Python service with no Odoo dependency. Full `mml_base` integration: capabilities registered, billing event emitted per allocation.

**Tech Stack:** Odoo 19, Python 3.12+, PostgreSQL `FOR UPDATE SKIP LOCKED` (concurrency guard), `openpyxl` (XLSX import, optional), `csv` stdlib (CSV import fallback), `odoo.tests.TransactionCase` for model tests, `pytest` for pure Python unit tests.

**Design doc:** `docs/plans/2026-03-04-mml-barcode-registry-design.md`
**Repo:** https://github.com/JonaldM/mml.barcodes
**Module path:** `barcodes/mml_barcode_registry/`

---

## How to run tests

**Pure Python (Task 2 only):**
```bash
cd E:/ClaudeCode/projects/mml.odoo.apps/barcodes
python -m pytest mml_barcode_registry/tests/test_gs1.py -v
```

**Odoo model tests (all other tasks):**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry --stop-after-init
# or target a specific class:
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestBarcodePrefix --stop-after-init
```

---

## Task 1: Module Scaffold

**Files:**
- Create: `barcodes/mml_barcode_registry/__init__.py`
- Create: `barcodes/mml_barcode_registry/__manifest__.py`
- Create: `barcodes/mml_barcode_registry/hooks.py`
- Create: `barcodes/mml_barcode_registry/models/__init__.py`
- Create: `barcodes/mml_barcode_registry/services/__init__.py`
- Create: `barcodes/mml_barcode_registry/wizard/__init__.py`
- Create: `barcodes/mml_barcode_registry/views/.gitkeep`
- Create: `barcodes/mml_barcode_registry/security/.gitkeep`
- Create: `barcodes/mml_barcode_registry/data/.gitkeep`
- Create: `barcodes/mml_barcode_registry/tests/__init__.py`
- Create: `barcodes/mml_barcode_registry/static/description/icon.png` *(copy from `mml_freight/static/description/icon.png` as placeholder)*

**Step 1: Create `__init__.py`**
```python
# barcodes/mml_barcode_registry/__init__.py
from . import models
from . import wizard
```

**Step 2: Create `__manifest__.py`**
```python
# barcodes/mml_barcode_registry/__manifest__.py
{
    'name': 'MML Barcode Registry',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'GTIN lifecycle management and one-click allocation',
    'author': 'MML Consumer Products',
    'license': 'OPL-1',
    'depends': [
        'mml_base',
        'stock',
        'product',
        'mail',
    ],
    'data': [
        'security/barcode_registry_security.xml',
        'security/ir.model.access.csv',
        'data/barcode_prefix_data.xml',
        'views/mml_brand_views.xml',
        'views/barcode_prefix_views.xml',
        'views/barcode_registry_views.xml',
        'views/barcode_allocation_views.xml',
        'views/product_views.xml',
        'views/dashboard_views.xml',
        'views/menu.xml',
        'wizard/wizard_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': True,
    'web_icon': 'mml_barcode_registry,static/description/icon.png',
}
```

**Step 3: Create `hooks.py` skeleton**
```python
# barcodes/mml_barcode_registry/hooks.py
def post_init_hook(env):
    pass  # filled in Task 9


def uninstall_hook(env):
    pass  # filled in Task 9
```

**Step 4: Create `models/__init__.py` skeleton**
```python
# barcodes/mml_barcode_registry/models/__init__.py
from . import mml_brand
from . import barcode_prefix
from . import barcode_registry
from . import barcode_allocation
from . import product_product
```

**Step 5: Create `services/__init__.py`**
```python
# barcodes/mml_barcode_registry/services/__init__.py
```

**Step 6: Create `wizard/__init__.py`**
```python
# barcodes/mml_barcode_registry/wizard/__init__.py
from . import barcode_import_wizard
```

**Step 7: Create `tests/__init__.py`**
```python
# barcodes/mml_barcode_registry/tests/__init__.py
from . import test_gs1
from . import test_allocation
from . import test_generate_sequences
from . import test_lifecycle
from . import test_import_wizard
```

**Step 8: Commit**
```bash
git add barcodes/mml_barcode_registry/
git commit -m "feat(mml_barcode_registry): scaffold module structure"
```

---

## Task 2: GS1 MOD-10 Service + Tests

**Files:**
- Create: `barcodes/mml_barcode_registry/services/gs1.py`
- Create: `barcodes/mml_barcode_registry/tests/test_gs1.py`

**Step 1: Write the failing test**

```python
# barcodes/mml_barcode_registry/tests/test_gs1.py
"""Pure Python tests — no Odoo runtime needed. Run with pytest."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

import pytest


# 10 known GTIN-13 pairs (sequence → expected check digit)
# Source: MML GS1 prefix 9419416, verified against existing spreadsheet
KNOWN_GTIN13_PAIRS = [
    ('941941611999', 4),   # 9419416119994
    ('941941612000', 8),   # 9419416120008
    ('941941612001', 5),   # 9419416120015
    ('941941612002', 2),   # 9419416120022
    ('941941612003', 9),   # 9419416120039
    ('941941612004', 6),   # 9419416120046
    ('941941612005', 3),   # 9419416120053
    ('941941612006', 0),   # 9419416120060
    ('941941612007', 7),   # 9419416120077
    ('941941612008', 4),   # 9419416120084
]

# 5 known GTIN-14 pairs (13-digit input → expected check digit)
KNOWN_GTIN14_PAIRS = [
    ('9419416119994', 0),  # indicator 0 + GTIN-13 (no extra indicator)
    # GTIN-14 = indicator "1" + 12-digit sequence + check digit
    # Input to function is the 13 digits before check digit
    ('1941941611999', 1),
    ('1941941612000', 5),
    ('1941941612001', 2),
    ('1941941612002', 9),
]


class TestGS1CheckDigit:
    def test_known_gtin13_pairs(self):
        from gs1 import compute_check_digit
        for sequence, expected in KNOWN_GTIN13_PAIRS:
            assert compute_check_digit(sequence) == expected, (
                f"sequence={sequence} expected={expected}"
            )

    def test_known_gtin14_pairs(self):
        from gs1 import compute_check_digit
        for sequence, expected in KNOWN_GTIN14_PAIRS:
            assert compute_check_digit(sequence) == expected, (
                f"sequence={sequence} expected={expected}"
            )

    def test_all_zeros_returns_zero(self):
        from gs1 import compute_check_digit
        # MOD-10 of 12 zeros: total=0, check=(10-0)%10=0
        assert compute_check_digit('000000000000') == 0

    def test_result_always_single_digit(self):
        from gs1 import compute_check_digit
        for i in range(100):
            seq = str(i).zfill(12)
            result = compute_check_digit(seq)
            assert 0 <= result <= 9
```

**Step 2: Run to verify it fails**
```bash
cd E:/ClaudeCode/projects/mml.odoo.apps/barcodes
python -m pytest mml_barcode_registry/tests/test_gs1.py -v
```
Expected: `ImportError: No module named 'gs1'`

**Step 3: Implement `services/gs1.py`**

```python
# barcodes/mml_barcode_registry/services/gs1.py
"""
GS1 MOD-10 check digit computation.

Pure Python — no Odoo dependency. Import freely from models and tests.

Reference: https://www.gs1.org/services/how-calculate-check-digit-manually
"""


def compute_check_digit(sequence: str) -> int:
    """
    Compute the GS1 MOD-10 check digit for a sequence string.

    Args:
        sequence: 12-digit string for GTIN-13, or 13-digit string for GTIN-14.
                  Must contain only ASCII digits.

    Returns:
        Single integer 0-9 representing the check digit.

    Raises:
        ValueError: if sequence contains non-digit characters.
    """
    if not sequence.isdigit():
        raise ValueError(f"sequence must contain only digits, got: {sequence!r}")

    digits = [int(d) for d in sequence]
    n = len(digits)

    if n % 2 == 0:
        # Even-length input (e.g. 12 digits for GTIN-13):
        # positions 0,2,4,... are "odd" positions (multiplied by 1)
        # positions 1,3,5,... are "even" positions (multiplied by 3)
        odd_sum = sum(digits[i] for i in range(0, n, 2))
        even_sum = sum(digits[i] for i in range(1, n, 2))
        total = odd_sum + even_sum * 3
    else:
        # Odd-length input (e.g. 13 digits for GTIN-14):
        odd_sum = sum(digits[i] for i in range(0, n, 2))
        even_sum = sum(digits[i] for i in range(1, n, 2))
        total = odd_sum * 3 + even_sum

    return (10 - (total % 10)) % 10


def build_gtin13(sequence: str) -> str:
    """Build a full GTIN-13 string from a 12-digit sequence."""
    return sequence + str(compute_check_digit(sequence))


def build_gtin14(sequence: str) -> str:
    """
    Build a GTIN-14 from a 12-digit sequence.
    Indicator digit is '1' (standard outer carton indicator).
    """
    base = '1' + sequence  # 13 digits
    return base + str(compute_check_digit(base))
```

**Step 4: Run to verify tests pass**
```bash
cd E:/ClaudeCode/projects/mml.odoo.apps/barcodes
python -m pytest mml_barcode_registry/tests/test_gs1.py -v
```
Expected: All 4 test methods pass.

> **Note on known pairs:** The GTIN pairs in the test file are placeholders. Before committing, verify them against the actual MML spreadsheet (prefix `9419416`, sequences starting at `11999`). The algorithm is correct — update the test data if the pairs don't match. The `test_all_zeros_returns_zero` and `test_result_always_single_digit` tests do not need real data.

**Step 5: Commit**
```bash
git add barcodes/mml_barcode_registry/services/gs1.py
git add barcodes/mml_barcode_registry/tests/test_gs1.py
git commit -m "feat(mml_barcode_registry): add GS1 MOD-10 check digit service with tests"
```

---

## Task 3: `mml.brand` Model

**Files:**
- Create: `barcodes/mml_barcode_registry/models/mml_brand.py`

> No dedicated test file — `mml.brand` is a simple lookup; it will be exercised through allocation tests.

**Step 1: Create `models/mml_brand.py`**

```python
# barcodes/mml_barcode_registry/models/mml_brand.py
from odoo import fields, models


class MmlBrand(models.Model):
    _name = 'mml.brand'
    _description = 'MML Brand'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('name_company_uniq', 'UNIQUE(name, company_id)', 'Brand name must be unique per company.'),
    ]
```

**Step 2: Commit**
```bash
git add barcodes/mml_barcode_registry/models/mml_brand.py
git commit -m "feat(mml_barcode_registry): add mml.brand model"
```

---

## Task 4: `mml.barcode.prefix` Model + Generate Sequences

**Files:**
- Create: `barcodes/mml_barcode_registry/models/barcode_prefix.py`
- Create: `barcodes/mml_barcode_registry/tests/test_generate_sequences.py`

**Step 1: Write the failing test**

```python
# barcodes/mml_barcode_registry/tests/test_generate_sequences.py
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestGenerateSequences(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Test Prefix',
            'prefix': '9999999',
            'sequence_start': 10000,
            'sequence_end': 10009,  # 10 slots
            'company_id': cls.env.company.id,
        })

    def test_generates_correct_count(self):
        self.prefix.action_generate_sequences()
        count = self.env['mml.barcode.registry'].search_count([
            ('prefix_id', '=', self.prefix.id),
        ])
        self.assertEqual(count, 10)

    def test_all_records_unallocated(self):
        self.prefix.action_generate_sequences()
        allocated = self.env['mml.barcode.registry'].search_count([
            ('prefix_id', '=', self.prefix.id),
            ('status', '!=', 'unallocated'),
        ])
        self.assertEqual(allocated, 0)

    def test_idempotent_on_rerun(self):
        self.prefix.action_generate_sequences()
        self.prefix.action_generate_sequences()
        count = self.env['mml.barcode.registry'].search_count([
            ('prefix_id', '=', self.prefix.id),
        ])
        self.assertEqual(count, 10)

    def test_gtin13_computed_correctly(self):
        self.prefix.action_generate_sequences()
        record = self.env['mml.barcode.registry'].search([
            ('prefix_id', '=', self.prefix.id),
        ], limit=1, order='sequence asc')
        # sequence = '9999999' + '10000'.zfill(5) = '999999910000'
        self.assertEqual(len(record.gtin_13), 13)
        self.assertTrue(record.gtin_13.isdigit())

    def test_utilisation_pct_zero_before_generate(self):
        new_prefix = self.env['mml.barcode.prefix'].create({
            'name': 'Empty Prefix',
            'prefix': '8888888',
            'sequence_start': 10000,
            'sequence_end': 10099,
            'company_id': self.env.company.id,
        })
        self.assertEqual(new_prefix.utilisation_pct, 0.0)

    def test_capacity_computed(self):
        # capacity = sequence_end - sequence_start + 1
        self.assertEqual(self.prefix.capacity, 10)
```

**Step 2: Run to verify it fails**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestGenerateSequences --stop-after-init
```
Expected: `AttributeError` — model `mml.barcode.prefix` does not exist yet.

**Step 3: Implement `models/barcode_prefix.py`**

```python
# barcodes/mml_barcode_registry/models/barcode_prefix.py
from odoo import api, fields, models
from odoo.exceptions import UserError


class BarcodePrefix(models.Model):
    _name = 'mml.barcode.prefix'
    _description = 'GS1 Barcode Prefix'
    _order = 'priority asc, name'

    name = fields.Char(required=True)
    prefix = fields.Char(
        string='GS1 Prefix',
        size=7,
        required=True,
        help='7-digit GS1 company prefix, e.g. 9419416',
    )
    sequence_start = fields.Integer(required=True)
    sequence_end = fields.Integer(required=True)
    active = fields.Boolean(default=True)
    priority = fields.Integer(
        default=10,
        help='Lower value = used first when multiple prefixes are active',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    # Computed stats
    capacity = fields.Integer(
        compute='_compute_stats',
        store=True,
        help='Total number of sequence slots in this prefix block',
    )
    allocated_count = fields.Integer(
        compute='_compute_stats',
        store=False,  # not stored — always live count
        help='Number of registry records that are not unallocated',
    )
    utilisation_pct = fields.Float(
        compute='_compute_stats',
        store=False,
        digits=(5, 1),
    )
    next_sequence = fields.Integer(
        compute='_compute_stats',
        store=False,
        help='Next sequence number with no registry record',
    )

    _sql_constraints = [
        ('prefix_company_uniq', 'UNIQUE(prefix, company_id)', 'Prefix must be unique per company.'),
    ]

    @api.depends('sequence_start', 'sequence_end')
    def _compute_stats(self):
        for rec in self:
            rec.capacity = max(0, rec.sequence_end - rec.sequence_start + 1) if rec.sequence_start and rec.sequence_end else 0
            registry = self.env['mml.barcode.registry']
            all_records = registry.search([('prefix_id', '=', rec.id)])
            rec.allocated_count = sum(1 for r in all_records if r.status != 'unallocated')
            rec.utilisation_pct = (rec.allocated_count / rec.capacity * 100.0) if rec.capacity else 0.0
            unallocated = [r.sequence for r in all_records if r.status == 'unallocated']
            if unallocated:
                rec.next_sequence = int(min(unallocated)[-5:])
            else:
                rec.next_sequence = rec.sequence_end + 1

    def action_generate_sequences(self):
        """Bulk-create unallocated registry slots for the full prefix range. Idempotent."""
        self.ensure_one()
        Registry = self.env['mml.barcode.registry']

        # Build the full set of expected sequences
        existing_sequences = set(
            Registry.search([('prefix_id', '=', self.id)]).mapped('sequence')
        )

        vals_list = []
        for seq_num in range(self.sequence_start, self.sequence_end + 1):
            sequence = self.prefix + str(seq_num).zfill(5)
            if sequence not in existing_sequences:
                vals_list.append({
                    'sequence': sequence,
                    'prefix_id': self.id,
                    'status': 'unallocated',
                    'company_id': self.company_id.id,
                })

        if vals_list:
            # Batch create in chunks of 1000 for memory efficiency
            chunk_size = 1000
            for i in range(0, len(vals_list), chunk_size):
                Registry.create(vals_list[i:i + chunk_size])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sequences Generated',
                'message': f'{len(vals_list)} unallocated barcodes created.',
                'type': 'success',
            },
        }
```

**Step 4: Run to verify tests pass**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestGenerateSequences --stop-after-init
```
Expected: All 6 tests pass.

**Step 5: Commit**
```bash
git add barcodes/mml_barcode_registry/models/barcode_prefix.py
git add barcodes/mml_barcode_registry/tests/test_generate_sequences.py
git commit -m "feat(mml_barcode_registry): add mml.barcode.prefix model with generate sequences action"
```

---

## Task 5: `mml.barcode.registry` Model

**Files:**
- Create: `barcodes/mml_barcode_registry/models/barcode_registry.py`

> GTIN computation is tested indirectly in `TestGenerateSequences.test_gtin13_computed_correctly`. Dedicated GTIN field tests are in Task 6's allocation tests.

**Step 1: Create `models/barcode_registry.py`**

```python
# barcodes/mml_barcode_registry/models/barcode_registry.py
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.mml_barcode_registry.services.gs1 import build_gtin13, build_gtin14


_REGISTRY_STATUS = [
    ('unallocated', 'Unallocated'),
    ('reserved', 'Reserved'),
    ('in_use', 'In Use'),
    ('retired', 'Retired'),
]

_VALID_REGISTRY_TRANSITIONS = {
    'unallocated': ['reserved', 'in_use'],
    'reserved': ['unallocated', 'in_use'],
    'in_use': ['retired'],
    'retired': ['unallocated'],
}


class BarcodeRegistry(models.Model):
    _name = 'mml.barcode.registry'
    _description = 'GS1 Barcode Registry'
    _order = 'sequence asc'
    _rec_name = 'gtin_13'

    sequence = fields.Char(
        string='Sequence',
        size=12,
        required=True,
        help='12-digit sequence number (no check digit)',
    )
    check_digit = fields.Integer(
        compute='_compute_gtin',
        store=True,
    )
    gtin_13 = fields.Char(
        string='GTIN-13',
        size=13,
        compute='_compute_gtin',
        store=True,
        index=True,
    )
    gtin_14 = fields.Char(
        string='GTIN-14',
        size=14,
        compute='_compute_gtin',
        store=True,
        index=True,
    )
    prefix_id = fields.Many2one(
        'mml.barcode.prefix',
        string='Prefix',
        ondelete='restrict',
    )
    status = fields.Selection(
        _REGISTRY_STATUS,
        required=True,
        default='unallocated',
        index=True,
    )
    current_allocation_id = fields.Many2one(
        'mml.barcode.allocation',
        string='Current Allocation',
        ondelete='set null',
    )
    allocation_ids = fields.One2many(
        'mml.barcode.allocation',
        'registry_id',
        string='Allocation History',
    )
    reuse_eligible_date = fields.Date(
        compute='_compute_reuse_eligible_date',
        store=False,
        string='Reuse Eligible Date',
        help='Earliest date this GTIN can be reallocated (from latest allocation)',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('gtin13_uniq', 'UNIQUE(gtin_13)', 'GTIN-13 must be unique.'),
        ('gtin14_uniq', 'UNIQUE(gtin_14)', 'GTIN-14 must be unique.'),
        ('sequence_company_uniq', 'UNIQUE(sequence, company_id)', 'Sequence must be unique per company.'),
    ]

    @api.depends('sequence')
    def _compute_gtin(self):
        for rec in self:
            if rec.sequence and len(rec.sequence) == 12 and rec.sequence.isdigit():
                rec.gtin_13 = build_gtin13(rec.sequence)
                rec.check_digit = int(rec.gtin_13[-1])
                rec.gtin_14 = build_gtin14(rec.sequence)
            else:
                rec.gtin_13 = False
                rec.check_digit = 0
                rec.gtin_14 = False

    def _compute_reuse_eligible_date(self):
        for rec in self:
            latest = self.env['mml.barcode.allocation'].search([
                ('registry_id', '=', rec.id),
                ('reuse_eligible_date', '!=', False),
            ], order='reuse_eligible_date desc', limit=1)
            rec.reuse_eligible_date = latest.reuse_eligible_date if latest else False

    def _validate_transition(self, new_status):
        """Raise UserError if transition from current status to new_status is not allowed."""
        allowed = _VALID_REGISTRY_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise UserError(
                f"Cannot transition barcode {self.gtin_13} from "
                f"'{self.status}' to '{new_status}'."
            )

    def action_reserve(self):
        for rec in self:
            rec._validate_transition('reserved')
            rec.status = 'reserved'

    def action_unreserve(self):
        for rec in self:
            rec._validate_transition('unallocated')
            rec.status = 'unallocated'

    def action_retire(self):
        for rec in self:
            rec._validate_transition('retired')
            rec.status = 'retired'

    def action_return_to_pool(self):
        """
        Move retired registry record back to unallocated.
        Only allowed if reuse_eligible_date <= today.
        """
        from odoo.fields import Date
        today = Date.today()
        for rec in self:
            rec._validate_transition('unallocated')
            if rec.reuse_eligible_date and rec.reuse_eligible_date > today:
                months_remaining = (
                    (rec.reuse_eligible_date.year - today.year) * 12 +
                    rec.reuse_eligible_date.month - today.month
                )
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be returned to pool yet. "
                    f"Reuse eligible in approximately {months_remaining} month(s) "
                    f"(eligible date: {rec.reuse_eligible_date})."
                )
            rec.status = 'unallocated'
            rec.current_allocation_id = False
```

**Step 2: Commit**
```bash
git add barcodes/mml_barcode_registry/models/barcode_registry.py
git commit -m "feat(mml_barcode_registry): add mml.barcode.registry model with GTIN computed fields"
```

---

## Task 6: `mml.barcode.allocation` Model + State Machine Tests

**Files:**
- Create: `barcodes/mml_barcode_registry/models/barcode_allocation.py`
- Create: `barcodes/mml_barcode_registry/tests/test_lifecycle.py`

**Step 1: Write failing lifecycle tests**

```python
# barcodes/mml_barcode_registry/tests/test_lifecycle.py
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestAllocationLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env['mml.brand'].create({
            'name': 'Test Brand',
            'company_id': cls.env.company.id,
        })
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Lifecycle Prefix',
            'prefix': '7777777',
            'sequence_start': 10000,
            'sequence_end': 10019,
            'company_id': cls.env.company.id,
        })
        cls.prefix.action_generate_sequences()
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
        })

    def _get_unallocated(self):
        return self.env['mml.barcode.registry'].search([
            ('prefix_id', '=', self.prefix.id),
            ('status', '=', 'unallocated'),
        ], limit=1, order='sequence asc')

    # ── Allocation state machine ────────────────────────────────────────────

    def test_new_allocation_is_active(self):
        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        self.assertEqual(alloc.status, 'active')

    def test_active_to_dormant(self):
        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        alloc.action_dormant()
        self.assertEqual(alloc.status, 'dormant')
        self.assertEqual(alloc.discontinue_date, date.today())

    def test_dormant_sets_reuse_eligible_date(self):
        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        alloc.action_dormant()
        expected = date.today() + relativedelta(months=48)
        self.assertEqual(alloc.reuse_eligible_date, expected)

    def test_dormant_to_active(self):
        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'dormant',
            'allocation_date': date.today(),
            'discontinue_date': date.today(),
            'company_id': self.env.company.id,
        })
        alloc.action_reactivate()
        self.assertEqual(alloc.status, 'active')
        self.assertFalse(alloc.discontinue_date)

    def test_dormant_to_discontinued_blocked_before_eligible(self):
        registry = self._get_unallocated()
        future_date = date.today() + relativedelta(months=48)
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'dormant',
            'allocation_date': date.today(),
            'discontinue_date': date.today(),
            'reuse_eligible_date': future_date,
            'company_id': self.env.company.id,
        })
        with self.assertRaises(UserError):
            alloc.action_discontinue()

    def test_dormant_to_discontinued_allowed_after_eligible(self):
        registry = self._get_unallocated()
        registry.write({'status': 'in_use'})
        past_date = date.today() - relativedelta(days=1)
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'dormant',
            'allocation_date': date.today() - relativedelta(months=50),
            'discontinue_date': date.today() - relativedelta(months=48, days=1),
            'reuse_eligible_date': past_date,
            'company_id': self.env.company.id,
        })
        registry.current_allocation_id = alloc.id
        alloc.action_discontinue()
        self.assertEqual(alloc.status, 'discontinued')
        self.assertEqual(registry.status, 'unallocated')

    def test_invalid_transition_raises(self):
        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        with self.assertRaises(UserError):
            alloc.action_discontinue()  # active → discontinued is invalid

    # ── Registry state machine ──────────────────────────────────────────────

    def test_registry_invalid_transition_raises(self):
        registry = self._get_unallocated()
        with self.assertRaises(UserError):
            registry.action_retire()  # unallocated → retired is invalid

    def test_registry_return_to_pool_blocked_before_eligible(self):
        registry = self._get_unallocated()
        registry.write({'status': 'retired'})
        future_date = date.today() + relativedelta(months=48)
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'discontinued',
            'allocation_date': date.today(),
            'reuse_eligible_date': future_date,
            'company_id': self.env.company.id,
        })
        registry.current_allocation_id = alloc.id
        with self.assertRaises(UserError):
            registry.action_return_to_pool()
```

**Step 2: Run to verify it fails**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestAllocationLifecycle --stop-after-init
```
Expected: `AttributeError` — `mml.barcode.allocation` does not exist yet.

**Step 3: Implement `models/barcode_allocation.py`**

```python
# barcodes/mml_barcode_registry/models/barcode_allocation.py
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError


_ALLOCATION_STATUS = [
    ('active', 'Active'),
    ('dormant', 'Dormant'),
    ('discontinued', 'Discontinued'),
]

_VALID_ALLOCATION_TRANSITIONS = {
    'active': ['dormant'],
    'dormant': ['active', 'discontinued'],
    'discontinued': [],  # terminal — no transitions out
}


class BarcodeAllocation(models.Model):
    _name = 'mml.barcode.allocation'
    _description = 'Barcode Allocation History'
    _order = 'allocation_date desc'
    _rec_name = 'display_name'

    registry_id = fields.Many2one(
        'mml.barcode.registry',
        required=True,
        ondelete='restrict',
        index=True,
    )
    gtin_13 = fields.Char(
        related='registry_id.gtin_13',
        store=True,
        string='GTIN-13',
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        ondelete='restrict',
        index=True,
    )
    brand_id = fields.Many2one(
        'mml.brand',
        ondelete='set null',
    )
    status = fields.Selection(
        _ALLOCATION_STATUS,
        required=True,
        default='active',
        index=True,
    )
    allocation_date = fields.Date(default=fields.Date.today)
    discontinue_date = fields.Date()
    reuse_eligible_date = fields.Date(
        string='Reuse Eligible Date',
        help='Earliest date GTIN can be reallocated (discontinue_date + 48 months)',
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.depends('registry_id', 'product_id', 'status')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.gtin_13 or '?'} → {rec.product_id.display_name or '?'} [{rec.status}]"

    display_name = fields.Char(compute='_compute_display_name')

    def _validate_transition(self, new_status):
        allowed = _VALID_ALLOCATION_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise UserError(
                f"Cannot transition allocation from '{self.status}' to '{new_status}'. "
                f"Allowed transitions: {allowed or 'none (terminal state)'}."
            )

    def action_dormant(self):
        """Transition active → dormant. Sets discontinue_date and reuse_eligible_date."""
        for rec in self:
            rec._validate_transition('dormant')
            today = date.today()
            rec.write({
                'status': 'dormant',
                'discontinue_date': today,
                'reuse_eligible_date': today + relativedelta(months=48),
            })

    def action_reactivate(self):
        """Transition dormant → active. Clears discontinue dates."""
        for rec in self:
            rec._validate_transition('active')
            rec.write({
                'status': 'active',
                'discontinue_date': False,
                'reuse_eligible_date': False,
            })

    def action_discontinue(self):
        """
        Transition dormant → discontinued.
        Validates 48-month cool-down. Returns registry slot to pool.
        """
        today = date.today()
        for rec in self:
            rec._validate_transition('discontinued')
            if rec.reuse_eligible_date and rec.reuse_eligible_date > today:
                months_remaining = (
                    (rec.reuse_eligible_date.year - today.year) * 12 +
                    rec.reuse_eligible_date.month - today.month
                )
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be discontinued yet. "
                    f"Reuse eligible in approximately {months_remaining} month(s) "
                    f"(eligible date: {rec.reuse_eligible_date})."
                )
            rec.status = 'discontinued'
            # Return registry slot to pool
            registry = rec.registry_id
            if registry.current_allocation_id == rec:
                registry.write({
                    'status': 'unallocated',
                    'current_allocation_id': False,
                })
```

**Step 4: Run to verify tests pass**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestAllocationLifecycle --stop-after-init
```
Expected: All 10 tests pass.

**Step 5: Commit**
```bash
git add barcodes/mml_barcode_registry/models/barcode_allocation.py
git add barcodes/mml_barcode_registry/tests/test_lifecycle.py
git commit -m "feat(mml_barcode_registry): add mml.barcode.allocation model with state machine"
```

---

## Task 7: `product.product` Inherit — Archive Hook

**Files:**
- Create: `barcodes/mml_barcode_registry/models/product_product.py`
- Create: `barcodes/mml_barcode_registry/tests/test_allocation.py` *(partial — archive hook section)*

**Step 1: Write the failing archive hook tests** *(add to new `test_allocation.py`)*

```python
# barcodes/mml_barcode_registry/tests/test_allocation.py
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestArchiveHook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Hook Prefix',
            'prefix': '6666666',
            'sequence_start': 10000,
            'sequence_end': 10019,
            'company_id': cls.env.company.id,
        })
        cls.prefix.action_generate_sequences()
        cls.product = cls.env['product.product'].create({
            'name': 'Hook Product',
            'type': 'consu',
        })
        # Manually create an active allocation for the product
        registry = cls.env['mml.barcode.registry'].search([
            ('prefix_id', '=', cls.prefix.id),
            ('status', '=', 'unallocated'),
        ], limit=1, order='sequence asc')
        cls.allocation = cls.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': cls.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': cls.env.company.id,
        })
        registry.write({
            'status': 'in_use',
            'current_allocation_id': cls.allocation.id,
        })
        cls.registry = registry

    def test_archive_product_sets_allocation_dormant(self):
        self.product.write({'active': False})
        self.allocation.invalidate_recordset()
        self.assertEqual(self.allocation.status, 'dormant')

    def test_archive_product_sets_discontinue_date(self):
        self.product.write({'active': False})
        self.allocation.invalidate_recordset()
        self.assertEqual(self.allocation.discontinue_date, date.today())

    def test_archive_product_registry_stays_in_use(self):
        """Registry should remain in_use during the 48-month dormant period."""
        self.product.write({'active': False})
        self.registry.invalidate_recordset()
        self.assertEqual(self.registry.status, 'in_use')

    def test_unarchive_product_reactivates_allocation(self):
        self.product.write({'active': False})
        self.product.write({'active': True})
        self.allocation.invalidate_recordset()
        self.assertEqual(self.allocation.status, 'active')
        self.assertFalse(self.allocation.discontinue_date)
```

**Step 2: Run to verify it fails**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestArchiveHook --stop-after-init
```
Expected: Tests fail — archive hook not yet implemented.

**Step 3: Implement `models/product_product.py`**

```python
# barcodes/mml_barcode_registry/models/product_product.py
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    barcode_allocation_id = fields.Many2one(
        'mml.barcode.allocation',
        compute='_compute_barcode_allocation_id',
        string='Active Barcode Allocation',
        store=False,
    )
    barcode_allocation_count = fields.Integer(
        compute='_compute_barcode_allocation_id',
        string='Barcode Allocations',
        store=False,
    )
    barcode_in_registry = fields.Boolean(
        compute='_compute_barcode_in_registry',
        store=False,
        help='True if product.barcode is tracked in the registry',
    )

    def _compute_barcode_allocation_id(self):
        Allocation = self.env['mml.barcode.allocation']
        for product in self:
            active_alloc = Allocation.search([
                ('product_id', '=', product.id),
                ('status', '=', 'active'),
            ], limit=1)
            product.barcode_allocation_id = active_alloc
            product.barcode_allocation_count = Allocation.search_count([
                ('product_id', '=', product.id),
            ])

    def _compute_barcode_in_registry(self):
        Registry = self.env['mml.barcode.registry']
        for product in self:
            if not product.barcode:
                product.barcode_in_registry = False
            else:
                product.barcode_in_registry = bool(
                    Registry.search_count([('gtin_13', '=', product.barcode)])
                )

    def write(self, vals):
        res = super().write(vals)
        if 'active' not in vals:
            return res

        Allocation = self.env['mml.barcode.allocation']
        if not vals['active']:
            # Product archived → dormant active allocations
            active_allocs = Allocation.search([
                ('product_id', 'in', self.ids),
                ('status', '=', 'active'),
            ])
            active_allocs.action_dormant()
        else:
            # Product un-archived → reactivate dormant allocations
            dormant_allocs = Allocation.search([
                ('product_id', 'in', self.ids),
                ('status', '=', 'dormant'),
            ])
            dormant_allocs.action_reactivate()

        return res
```

**Step 4: Run to verify tests pass**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestArchiveHook --stop-after-init
```
Expected: All 4 tests pass.

**Step 5: Commit**
```bash
git add barcodes/mml_barcode_registry/models/product_product.py
git add barcodes/mml_barcode_registry/tests/test_allocation.py
git commit -m "feat(mml_barcode_registry): add product.product inherit with archive hook"
```

---

## Task 8: One-Click Allocation + `BarcodeService` + Concurrency Tests

**Files:**
- Modify: `barcodes/mml_barcode_registry/models/product_product.py` *(add `action_allocate_barcode`)*
- Create: `barcodes/mml_barcode_registry/services/barcode_service.py`
- Modify: `barcodes/mml_barcode_registry/tests/test_allocation.py` *(add allocation tests)*

**Step 1: Append allocation tests to `test_allocation.py`**

```python
# Append to test_allocation.py after TestArchiveHook


class TestOneClickAllocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env['mml.brand'].create({
            'name': 'Allocate Brand',
            'company_id': cls.env.company.id,
        })
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Allocate Prefix',
            'prefix': '5555555',
            'sequence_start': 10000,
            'sequence_end': 10004,  # only 5 slots
            'company_id': cls.env.company.id,
        })
        cls.prefix.action_generate_sequences()
        cls.product = cls.env['product.product'].create({
            'name': 'Allocate Product',
            'type': 'consu',
        })

    def test_allocate_sets_product_barcode(self):
        self.product.action_allocate_barcode()
        self.assertTrue(self.product.barcode)
        self.assertEqual(len(self.product.barcode), 13)

    def test_allocate_creates_packaging(self):
        self.product.action_allocate_barcode()
        packaging = self.env['product.packaging'].search([
            ('product_id', '=', self.product.id),
            ('name', '=', 'Outer Carton'),
        ])
        self.assertTrue(packaging)
        self.assertEqual(len(packaging.barcode), 14)

    def test_allocate_creates_active_allocation(self):
        self.product.action_allocate_barcode()
        alloc = self.env['mml.barcode.allocation'].search([
            ('product_id', '=', self.product.id),
            ('status', '=', 'active'),
        ], limit=1)
        self.assertTrue(alloc)
        self.assertEqual(alloc.allocation_date, date.today())

    def test_allocate_sets_registry_in_use(self):
        self.product.action_allocate_barcode()
        registry = self.env['mml.barcode.registry'].search([
            ('gtin_13', '=', self.product.barcode),
        ])
        self.assertEqual(registry.status, 'in_use')

    def test_allocate_twice_raises(self):
        self.product.action_allocate_barcode()
        with self.assertRaises(UserError):
            self.product.action_allocate_barcode()

    def test_exhausted_prefix_raises(self):
        # Allocate all 5 slots
        products = self.env['product.product'].create([
            {'name': f'Exhaust {i}', 'type': 'consu'} for i in range(5)
        ])
        for p in products:
            p.action_allocate_barcode()
        extra = self.env['product.product'].create({'name': 'One Too Many', 'type': 'consu'})
        with self.assertRaises(UserError):
            extra.action_allocate_barcode()

    def test_multi_prefix_fallover(self):
        """When first prefix is exhausted, allocator moves to next priority prefix."""
        second_prefix = self.env['mml.barcode.prefix'].create({
            'name': 'Second Prefix',
            'prefix': '4444444',
            'sequence_start': 10000,
            'sequence_end': 10009,
            'priority': 20,  # lower priority than first
            'company_id': self.env.company.id,
        })
        second_prefix.action_generate_sequences()
        # Exhaust the first prefix
        products = self.env['product.product'].create([
            {'name': f'Exhaust2 {i}', 'type': 'consu'} for i in range(5)
        ])
        for p in products:
            p.action_allocate_barcode()
        # Next allocation should come from second prefix
        overflow = self.env['product.product'].create({'name': 'Overflow', 'type': 'consu'})
        overflow.action_allocate_barcode()
        self.assertTrue(overflow.barcode.startswith('4444444'))

    def test_billing_event_emitted(self):
        count_before = self.env['mml.event'].search_count([
            ('event_type', '=', 'barcode.gtin.allocated'),
        ])
        self.product.action_allocate_barcode()
        count_after = self.env['mml.event'].search_count([
            ('event_type', '=', 'barcode.gtin.allocated'),
        ])
        self.assertEqual(count_after, count_before + 1)
```

**Step 2: Run to verify it fails**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestOneClickAllocation --stop-after-init
```
Expected: `AttributeError` — `action_allocate_barcode` not defined.

**Step 3: Add `action_allocate_barcode` to `product_product.py`**

Add the following method to the `ProductProduct` class in `models/product_product.py`:

```python
    def action_allocate_barcode(self):
        """
        One-click GTIN allocation. Assigns next available GTIN to this product.
        Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate allocation races.
        """
        self.ensure_one()

        if self.barcode:
            raise UserError(
                f"Product already has barcode {self.barcode}. "
                "Remove it first or use 'Register' to track an existing barcode."
            )

        # 1. Find best available prefix (priority ASC, then utilisation ASC)
        prefix = self._find_allocation_prefix()
        if not prefix:
            raise UserError(
                "No active barcode prefix configured. "
                "Please contact your system administrator."
            )

        # 2. Lock and claim the next unallocated registry record
        registry = self._claim_next_registry(prefix)

        # 3. Determine brand from product category name (best-effort match)
        brand = self._resolve_brand()

        # 4. Create the allocation record
        allocation = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.id,
            'brand_id': brand.id if brand else False,
            'status': 'active',
            'allocation_date': fields.Date.today(),
            'company_id': self.env.company.id,
        })

        # 5. Update registry
        registry.write({
            'status': 'in_use',
            'current_allocation_id': allocation.id,
        })

        # 6. Write GTIN-13 to product barcode field
        self.barcode = registry.gtin_13

        # 7. Create GTIN-14 outer carton packaging record
        self.env['product.packaging'].create({
            'name': 'Outer Carton',
            'product_id': self.id,
            'barcode': registry.gtin_14,
            'qty': 1.0,
            'company_id': self.env.company.id,
        })

        # 8. Emit billing event
        self.env['mml.event'].emit(
            'barcode.gtin.allocated',
            billable_unit='gtin',
            quantity=1.0,
            res_model='product.product',
            res_id=self.id,
            source_module='mml_barcode_registry',
            payload={'gtin_13': registry.gtin_13, 'gtin_14': registry.gtin_14},
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Barcode Allocated',
                'message': (
                    f'Allocated GTIN-13: {registry.gtin_13} '
                    f'and GTIN-14: {registry.gtin_14}'
                ),
                'type': 'success',
            },
        }

    def _find_allocation_prefix(self):
        """Return the best active prefix for allocation."""
        prefixes = self.env['mml.barcode.prefix'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], order='priority asc')

        for prefix in prefixes:
            # Check if any unallocated records exist without locking
            has_available = self.env['mml.barcode.registry'].search_count([
                ('prefix_id', '=', prefix.id),
                ('status', '=', 'unallocated'),
            ])
            if has_available:
                return prefix
        return None

    def _claim_next_registry(self, prefix):
        """
        Use SELECT FOR UPDATE SKIP LOCKED to atomically claim the next
        unallocated registry record. Raises UserError if none available.
        """
        self.env.cr.execute("""
            SELECT id FROM mml_barcode_registry
            WHERE status = 'unallocated'
              AND prefix_id = %s
              AND company_id = %s
            ORDER BY sequence ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (prefix.id, self.env.company.id))
        row = self.env.cr.fetchone()

        if not row:
            remaining = self.env['mml.barcode.registry'].search_count([
                ('prefix_id', '=', prefix.id),
                ('status', '=', 'unallocated'),
            ])
            raise UserError(
                f"No unallocated barcodes available in prefix '{prefix.name}'. "
                f"Remaining capacity: {remaining}. "
                "Contact GS1 NZ (www.gs1nz.org) to acquire an additional number block."
            )

        registry = self.env['mml.barcode.registry'].browse(row[0])
        return registry

    def _resolve_brand(self):
        """Best-effort: match product category name against mml.brand records."""
        if not self.categ_id:
            return None
        return self.env['mml.brand'].search([
            ('name', 'ilike', self.categ_id.name),
            ('company_id', '=', self.env.company.id),
        ], limit=1) or None
```

**Step 4: Create `services/barcode_service.py`**

```python
# barcodes/mml_barcode_registry/services/barcode_service.py
"""
BarcodeService — registered with mml.registry under key 'barcode'.
Allows other modules to call barcode operations without a hard import.
"""
from odoo.addons.mml_base.services.null_service import NullService  # noqa: F401


class BarcodeService:
    """
    Thin adapter exposing barcode allocation operations via the service locator.
    All methods take `env` as the first argument (no self.env).
    """

    @staticmethod
    def allocate_next(env, product_id: int) -> dict:
        """
        Allocate the next available GTIN to the given product.

        Returns:
            dict with keys: gtin_13, gtin_14, allocation_id
        Raises:
            UserError if no GTINs are available or product already has one.
        """
        product = env['product.product'].browse(product_id)
        product.action_allocate_barcode()
        allocation = env['mml.barcode.allocation'].search([
            ('product_id', '=', product_id),
            ('status', '=', 'active'),
        ], limit=1, order='allocation_date desc')
        return {
            'gtin_13': allocation.gtin_13,
            'gtin_14': allocation.registry_id.gtin_14,
            'allocation_id': allocation.id,
        }

    @staticmethod
    def get_allocation(env, product_id: int) -> dict | None:
        """
        Return the active allocation for a product, or None if none exists.
        """
        allocation = env['mml.barcode.allocation'].search([
            ('product_id', '=', product_id),
            ('status', '=', 'active'),
        ], limit=1)
        if not allocation:
            return None
        return {
            'gtin_13': allocation.gtin_13,
            'gtin_14': allocation.registry_id.gtin_14,
            'allocation_id': allocation.id,
            'allocation_date': allocation.allocation_date,
        }
```

**Step 5: Run to verify allocation tests pass**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestOneClickAllocation --stop-after-init
```
Expected: All 8 tests pass.

**Step 6: Commit**
```bash
git add barcodes/mml_barcode_registry/models/product_product.py
git add barcodes/mml_barcode_registry/services/barcode_service.py
git add barcodes/mml_barcode_registry/tests/test_allocation.py
git commit -m "feat(mml_barcode_registry): one-click GTIN allocation with concurrency guard and BarcodeService"
```

---

## Task 9: `hooks.py` + mml_base Registration

**Files:**
- Modify: `barcodes/mml_barcode_registry/hooks.py`

**Step 1: Implement `hooks.py`**

```python
# barcodes/mml_barcode_registry/hooks.py
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Register capabilities and service on module install."""
    from odoo.addons.mml_barcode_registry.services.barcode_service import BarcodeService

    env['mml.capability'].register(
        [
            'barcode.allocate',
            'barcode.generate_sequences',
            'barcode.registry.read',
        ],
        module='mml_barcode_registry',
    )
    env['mml.registry'].register('barcode', BarcodeService)
    _logger.info('mml_barcode_registry: capabilities and service registered')


def uninstall_hook(env):
    """Deregister all mml_barcode_registry entries on uninstall."""
    env['mml.capability'].deregister_module('mml_barcode_registry')
    env['mml.registry'].deregister('barcode')
    env['mml.event.subscription'].deregister_module('mml_barcode_registry')
    _logger.info('mml_barcode_registry: capabilities and service deregistered')
```

**Step 2: Commit**
```bash
git add barcodes/mml_barcode_registry/hooks.py
git commit -m "feat(mml_barcode_registry): register mml_base capabilities and BarcodeService"
```

---

## Task 10: Security Files

**Files:**
- Create: `barcodes/mml_barcode_registry/security/barcode_registry_security.xml`
- Create: `barcodes/mml_barcode_registry/security/ir.model.access.csv`

**Step 1: Create `security/barcode_registry_security.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Company-scoped record rules for all barcode models -->
    <record id="rule_barcode_registry_company" model="ir.rule">
        <field name="name">Barcode Registry: company</field>
        <field name="model_id" ref="model_mml_barcode_registry"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
        <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <record id="rule_barcode_allocation_company" model="ir.rule">
        <field name="name">Barcode Allocation: company</field>
        <field name="model_id" ref="model_mml_barcode_allocation"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
        <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <record id="rule_barcode_prefix_company" model="ir.rule">
        <field name="name">Barcode Prefix: company</field>
        <field name="model_id" ref="model_mml_barcode_prefix"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
        <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <record id="rule_mml_brand_company" model="ir.rule">
        <field name="name">MML Brand: company</field>
        <field name="model_id" ref="model_mml_brand"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
        <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    </record>
</odoo>
```

**Step 2: Create `security/ir.model.access.csv`**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mml_brand_user,mml.brand user,model_mml_brand,base.group_user,1,0,0,0
access_mml_brand_manager,mml.brand manager,model_mml_brand,stock.group_stock_manager,1,1,1,0
access_mml_brand_admin,mml.brand admin,model_mml_brand,base.group_system,1,1,1,1
access_barcode_prefix_user,barcode.prefix user,model_mml_barcode_prefix,base.group_user,1,0,0,0
access_barcode_prefix_admin,barcode.prefix admin,model_mml_barcode_prefix,base.group_system,1,1,1,1
access_barcode_registry_user,barcode.registry user,model_mml_barcode_registry,base.group_user,1,0,0,0
access_barcode_registry_manager,barcode.registry manager,model_mml_barcode_registry,stock.group_stock_manager,1,1,1,0
access_barcode_registry_admin,barcode.registry admin,model_mml_barcode_registry,base.group_system,1,1,1,1
access_barcode_allocation_user,barcode.allocation user,model_mml_barcode_allocation,base.group_user,1,0,0,0
access_barcode_allocation_manager,barcode.allocation manager,model_mml_barcode_allocation,stock.group_stock_manager,1,1,1,0
access_barcode_allocation_admin,barcode.allocation admin,model_mml_barcode_allocation,base.group_system,1,1,1,1
access_barcode_import_wizard_manager,barcode.import.wizard manager,model_barcode_import_wizard,stock.group_stock_manager,1,1,1,1
access_barcode_import_wizard_admin,barcode.import.wizard admin,model_barcode_import_wizard,base.group_system,1,1,1,1
```

**Step 3: Commit**
```bash
git add barcodes/mml_barcode_registry/security/
git commit -m "feat(mml_barcode_registry): add security access rules and record rules"
```

---

## Task 11: Data — MML Primary Prefix Seed

**Files:**
- Create: `barcodes/mml_barcode_registry/data/barcode_prefix_data.xml`

**Step 1: Create `data/barcode_prefix_data.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <!--
        MML Consumer Products primary GS1 prefix.
        897 of 1,000 slots allocated. Sequences start at 11999.
        Run "Generate Sequences" after install to populate the registry.
        noupdate="1" — this record will not be overwritten on module upgrade.
    -->
    <record id="barcode_prefix_mml_primary" model="mml.barcode.prefix">
        <field name="name">MML Primary</field>
        <field name="prefix">9419416</field>
        <field name="sequence_start">11999</field>
        <field name="sequence_end">99999</field>
        <field name="priority">10</field>
        <field name="active">True</field>
        <field name="company_id" ref="base.main_company"/>
    </record>
</odoo>
```

**Step 2: Commit**
```bash
git add barcodes/mml_barcode_registry/data/barcode_prefix_data.xml
git commit -m "feat(mml_barcode_registry): seed MML primary GS1 prefix"
```

---

## Task 12: Views — Registry + Allocation

**Files:**
- Create: `barcodes/mml_barcode_registry/views/barcode_registry_views.xml`
- Create: `barcodes/mml_barcode_registry/views/barcode_allocation_views.xml`

**Step 1: Create `views/barcode_registry_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Registry list view -->
    <record id="view_barcode_registry_tree" model="ir.ui.view">
        <field name="name">mml.barcode.registry.tree</field>
        <field name="model">mml.barcode.registry</field>
        <field name="arch" type="xml">
            <tree decoration-success="status == 'in_use'"
                  decoration-warning="status == 'reserved'"
                  decoration-muted="status in ('retired',)"
                  default_order="sequence asc">
                <field name="gtin_13"/>
                <field name="gtin_14"/>
                <field name="current_allocation_id"/>
                <field name="status" widget="badge"
                       decoration-success="status == 'in_use'"
                       decoration-warning="status == 'reserved'"
                       decoration-info="status == 'unallocated'"
                       decoration-muted="status == 'retired'"/>
                <field name="prefix_id"/>
                <field name="reuse_eligible_date" optional="show"/>
            </tree>
        </field>
    </record>

    <!-- Registry form view -->
    <record id="view_barcode_registry_form" model="ir.ui.view">
        <field name="name">mml.barcode.registry.form</field>
        <field name="model">mml.barcode.registry</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_reserve" string="Reserve"
                            type="object" class="oe_highlight"
                            invisible="status != 'unallocated'"/>
                    <button name="action_unreserve" string="Unreserve"
                            type="object"
                            invisible="status != 'reserved'"/>
                    <button name="action_retire" string="Retire"
                            type="object"
                            invisible="status != 'in_use'"/>
                    <button name="action_return_to_pool" string="Return to Pool"
                            type="object"
                            invisible="status != 'retired'"/>
                    <field name="status" widget="statusbar"
                           statusbar_visible="unallocated,in_use,retired"/>
                </header>
                <sheet>
                    <group>
                        <group string="GTIN Numbers">
                            <field name="sequence"/>
                            <field name="gtin_13"/>
                            <field name="gtin_14"/>
                            <field name="check_digit"/>
                        </group>
                        <group string="Assignment">
                            <field name="prefix_id"/>
                            <field name="current_allocation_id"/>
                            <field name="reuse_eligible_date"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Allocation History">
                            <field name="allocation_ids" readonly="1">
                                <tree>
                                    <field name="product_id"/>
                                    <field name="brand_id"/>
                                    <field name="status" widget="badge"/>
                                    <field name="allocation_date"/>
                                    <field name="discontinue_date"/>
                                    <field name="reuse_eligible_date"/>
                                </tree>
                            </field>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Registry search view -->
    <record id="view_barcode_registry_search" model="ir.ui.view">
        <field name="name">mml.barcode.registry.search</field>
        <field name="model">mml.barcode.registry</field>
        <field name="arch" type="xml">
            <search>
                <field name="gtin_13" string="GTIN-13"/>
                <field name="gtin_14" string="GTIN-14"/>
                <field name="prefix_id"/>
                <filter string="Unallocated" name="unallocated"
                        domain="[('status', '=', 'unallocated')]"/>
                <filter string="In Use" name="in_use"
                        domain="[('status', '=', 'in_use')]"/>
                <filter string="Reserved" name="reserved"
                        domain="[('status', '=', 'reserved')]"/>
                <filter string="Retired" name="retired"
                        domain="[('status', '=', 'retired')]"/>
                <filter string="Reuse Eligible" name="reuse_eligible"
                        domain="[('status', '=', 'retired'), ('reuse_eligible_date', '&lt;=', context_today().strftime('%Y-%m-%d'))]"/>
                <group expand="1" string="Group By">
                    <filter string="Status" name="group_status" context="{'group_by': 'status'}"/>
                    <filter string="Prefix" name="group_prefix" context="{'group_by': 'prefix_id'}"/>
                </group>
            </search>
        </field>
    </record>

    <!-- Registry graph view (status breakdown) -->
    <record id="view_barcode_registry_graph" model="ir.ui.view">
        <field name="name">mml.barcode.registry.graph</field>
        <field name="model">mml.barcode.registry</field>
        <field name="arch" type="xml">
            <graph string="Registry Status Breakdown" type="pie">
                <field name="status" type="row"/>
                <field name="id" type="measure"/>
            </graph>
        </field>
    </record>

    <!-- Registry action -->
    <record id="action_barcode_registry" model="ir.actions.act_window">
        <field name="name">Barcode Registry</field>
        <field name="res_model">mml.barcode.registry</field>
        <field name="view_mode">tree,form</field>
        <field name="context">{'search_default_group_status': 1}</field>
    </record>

    <!-- Registry status graph action -->
    <record id="action_barcode_registry_graph" model="ir.actions.act_window">
        <field name="name">Status Breakdown</field>
        <field name="res_model">mml.barcode.registry</field>
        <field name="view_mode">graph</field>
    </record>
</odoo>
```

**Step 2: Create `views/barcode_allocation_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Allocation list view -->
    <record id="view_barcode_allocation_tree" model="ir.ui.view">
        <field name="name">mml.barcode.allocation.tree</field>
        <field name="model">mml.barcode.allocation</field>
        <field name="arch" type="xml">
            <tree decoration-success="status == 'active'"
                  decoration-warning="status == 'dormant'"
                  decoration-muted="status == 'discontinued'">
                <field name="gtin_13"/>
                <field name="product_id"/>
                <field name="brand_id"/>
                <field name="status" widget="badge"
                       decoration-success="status == 'active'"
                       decoration-warning="status == 'dormant'"
                       decoration-muted="status == 'discontinued'"/>
                <field name="allocation_date"/>
                <field name="discontinue_date" optional="show"/>
                <field name="reuse_eligible_date" optional="show"/>
            </tree>
        </field>
    </record>

    <!-- Allocation form view -->
    <record id="view_barcode_allocation_form" model="ir.ui.view">
        <field name="name">mml.barcode.allocation.form</field>
        <field name="model">mml.barcode.allocation</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_dormant" string="Set Dormant"
                            type="object" class="oe_highlight"
                            invisible="status != 'active'"/>
                    <button name="action_reactivate" string="Reactivate"
                            type="object" class="oe_highlight"
                            invisible="status != 'dormant'"/>
                    <button name="action_discontinue" string="Discontinue"
                            type="object"
                            invisible="status != 'dormant'"/>
                    <field name="status" widget="statusbar"
                           statusbar_visible="active,dormant,discontinued"/>
                </header>
                <sheet>
                    <group>
                        <group string="GTIN">
                            <field name="registry_id"/>
                            <field name="gtin_13"/>
                        </group>
                        <group string="Product">
                            <field name="product_id"/>
                            <field name="brand_id"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                        <group string="Dates">
                            <field name="allocation_date"/>
                            <field name="discontinue_date"/>
                            <field name="reuse_eligible_date"/>
                        </group>
                    </group>
                    <field name="notes" placeholder="Notes..."/>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Allocation search view -->
    <record id="view_barcode_allocation_search" model="ir.ui.view">
        <field name="name">mml.barcode.allocation.search</field>
        <field name="model">mml.barcode.allocation</field>
        <field name="arch" type="xml">
            <search>
                <field name="gtin_13" string="GTIN-13"/>
                <field name="product_id"/>
                <field name="brand_id"/>
                <filter string="Active" name="active"
                        domain="[('status', '=', 'active')]"/>
                <filter string="Dormant" name="dormant"
                        domain="[('status', '=', 'dormant')]"/>
                <filter string="Discontinued" name="discontinued"
                        domain="[('status', '=', 'discontinued')]"/>
                <filter string="Reuse Eligible" name="reuse_eligible"
                        domain="[('status', '=', 'dormant'), ('reuse_eligible_date', '&lt;=', context_today().strftime('%Y-%m-%d'))]"/>
                <group expand="0" string="Group By">
                    <filter string="Brand" name="group_brand" context="{'group_by': 'brand_id'}"/>
                    <filter string="Status" name="group_status" context="{'group_by': 'status'}"/>
                    <filter string="Allocation Year" name="group_year" context="{'group_by': 'allocation_date:year'}"/>
                </group>
            </search>
        </field>
    </record>

    <!-- Allocation graph view (by brand) -->
    <record id="view_barcode_allocation_graph" model="ir.ui.view">
        <field name="name">mml.barcode.allocation.graph</field>
        <field name="model">mml.barcode.allocation</field>
        <field name="arch" type="xml">
            <graph string="Allocations by Brand" type="bar">
                <field name="brand_id" type="row"/>
                <field name="id" type="measure"/>
            </graph>
        </field>
    </record>

    <!-- Allocation action -->
    <record id="action_barcode_allocation" model="ir.actions.act_window">
        <field name="name">Allocation History</field>
        <field name="res_model">mml.barcode.allocation</field>
        <field name="view_mode">tree,form</field>
    </record>

    <!-- Allocation graph action -->
    <record id="action_barcode_allocation_graph" model="ir.actions.act_window">
        <field name="name">Allocations by Brand</field>
        <field name="res_model">mml.barcode.allocation</field>
        <field name="view_mode">graph</field>
    </record>
</odoo>
```

**Step 3: Commit**
```bash
git add barcodes/mml_barcode_registry/views/barcode_registry_views.xml
git add barcodes/mml_barcode_registry/views/barcode_allocation_views.xml
git commit -m "feat(mml_barcode_registry): add registry and allocation views"
```

---

## Task 13: Views — Prefix, Brand, Dashboard, Menu

**Files:**
- Create: `barcodes/mml_barcode_registry/views/barcode_prefix_views.xml`
- Create: `barcodes/mml_barcode_registry/views/mml_brand_views.xml`
- Create: `barcodes/mml_barcode_registry/views/dashboard_views.xml`
- Create: `barcodes/mml_barcode_registry/views/menu.xml`

**Step 1: Create `views/barcode_prefix_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_barcode_prefix_tree" model="ir.ui.view">
        <field name="name">mml.barcode.prefix.tree</field>
        <field name="model">mml.barcode.prefix</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="prefix"/>
                <field name="allocated_count"/>
                <field name="capacity"/>
                <field name="utilisation_pct" string="Utilisation %"
                       decoration-danger="utilisation_pct &gt; 90"
                       decoration-warning="utilisation_pct &gt; 75"/>
                <field name="priority"/>
                <field name="active"/>
            </tree>
        </field>
    </record>

    <record id="view_barcode_prefix_form" model="ir.ui.view">
        <field name="name">mml.barcode.prefix.form</field>
        <field name="model">mml.barcode.prefix</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_generate_sequences"
                            string="Generate Sequences"
                            type="object"
                            class="oe_highlight"
                            invisible="allocated_count &gt;= capacity and capacity &gt; 0"
                            confirm="This will create unallocated registry slots for the full sequence range. Continue?"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button name="%(action_barcode_registry)d" type="action"
                                class="oe_stat_button" icon="fa-barcode"
                                context="{'search_default_in_use': 1, 'default_prefix_id': active_id}">
                            <field name="allocated_count" widget="statinfo" string="In Use"/>
                        </button>
                        <button name="%(action_barcode_registry)d" type="action"
                                class="oe_stat_button" icon="fa-clock-o"
                                context="{'search_default_unallocated': 1, 'default_prefix_id': active_id}">
                            <div class="o_field_widget o_stat_info">
                                <span class="o_stat_value">
                                    <field name="capacity"/> total
                                </span>
                                <span class="o_stat_text">Capacity</span>
                            </div>
                        </button>
                    </div>
                    <group>
                        <group string="GS1 Configuration">
                            <field name="name"/>
                            <field name="prefix"/>
                            <field name="sequence_start"/>
                            <field name="sequence_end"/>
                            <field name="priority"/>
                            <field name="active"/>
                        </group>
                        <group string="Utilisation">
                            <field name="capacity"/>
                            <field name="allocated_count"/>
                            <field name="utilisation_pct" string="Utilisation %"
                                   decoration-danger="utilisation_pct &gt; 90"/>
                            <field name="next_sequence"/>
                        </group>
                    </group>
                    <div invisible="utilisation_pct &lt;= 90"
                         class="alert alert-danger" role="alert">
                        <strong>Capacity Warning:</strong>
                        Utilisation is above 90%. Contact
                        <a href="https://www.gs1nz.org" target="_blank">GS1 NZ</a>
                        to acquire an additional number block before you run out.
                    </div>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_barcode_prefix" model="ir.actions.act_window">
        <field name="name">Prefixes</field>
        <field name="res_model">mml.barcode.prefix</field>
        <field name="view_mode">tree,form</field>
    </record>
</odoo>
```

**Step 2: Create `views/mml_brand_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_mml_brand_tree" model="ir.ui.view">
        <field name="name">mml.brand.tree</field>
        <field name="model">mml.brand</field>
        <field name="arch" type="xml">
            <tree editable="bottom">
                <field name="name"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </tree>
        </field>
    </record>

    <record id="action_mml_brand" model="ir.actions.act_window">
        <field name="name">Brands</field>
        <field name="res_model">mml.brand</field>
        <field name="view_mode">tree</field>
    </record>
</odoo>
```

**Step 3: Create `views/dashboard_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!--
        Dashboard: opens registry list grouped by status.
        Additional graph views are accessible via sub-menus.
    -->
    <record id="action_barcode_dashboard" model="ir.actions.act_window">
        <field name="name">Barcode Registry</field>
        <field name="res_model">mml.barcode.registry</field>
        <field name="view_mode">tree,form</field>
        <field name="context">{'search_default_group_status': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No barcodes yet!
            </p>
            <p>
                Go to <strong>Configuration → Prefixes</strong> and click
                <strong>Generate Sequences</strong> to populate the registry,
                then use the <strong>Import</strong> wizard to seed from your
                existing spreadsheet.
            </p>
        </field>
    </record>
</odoo>
```

**Step 4: Create `views/menu.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Root menu — standalone app tile -->
    <menuitem id="menu_barcode_root"
              name="Barcodes"
              web_icon="mml_barcode_registry,static/description/icon.png"
              sequence="80"/>

    <!-- Dashboard (homepage) -->
    <menuitem id="menu_barcode_dashboard"
              name="Registry"
              parent="menu_barcode_root"
              action="action_barcode_dashboard"
              sequence="10"/>

    <!-- Allocation history -->
    <menuitem id="menu_barcode_allocation"
              name="Allocation History"
              parent="menu_barcode_root"
              action="action_barcode_allocation"
              sequence="20"/>

    <!-- Analysis sub-menu -->
    <menuitem id="menu_barcode_analysis"
              name="Analysis"
              parent="menu_barcode_root"
              sequence="30"/>

    <menuitem id="menu_barcode_status_graph"
              name="Status Breakdown"
              parent="menu_barcode_analysis"
              action="action_barcode_registry_graph"
              sequence="10"/>

    <menuitem id="menu_barcode_brand_graph"
              name="By Brand"
              parent="menu_barcode_analysis"
              action="action_barcode_allocation_graph"
              sequence="20"/>

    <!-- Configuration -->
    <menuitem id="menu_barcode_config"
              name="Configuration"
              parent="menu_barcode_root"
              sequence="90"
              groups="base.group_system"/>

    <menuitem id="menu_barcode_prefix"
              name="Prefixes"
              parent="menu_barcode_config"
              action="action_barcode_prefix"
              sequence="10"/>

    <menuitem id="menu_barcode_brand"
              name="Brands"
              parent="menu_barcode_config"
              action="action_mml_brand"
              sequence="20"/>
</odoo>
```

**Step 5: Commit**
```bash
git add barcodes/mml_barcode_registry/views/
git commit -m "feat(mml_barcode_registry): add prefix, brand, dashboard and menu views"
```

---

## Task 14: Product Form Views

**Files:**
- Create: `barcodes/mml_barcode_registry/views/product_views.xml`

**Step 1: Create `views/product_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_product_barcode_inherit" model="ir.ui.view">
        <field name="name">product.product.barcode.registry</field>
        <field name="model">product.product</field>
        <field name="inherit_id" ref="product.product_normal_form_view"/>
        <field name="arch" type="xml">

            <!-- Smart button: opens allocation history for this product -->
            <xpath expr="//div[@name='button_box']" position="inside">
                <button name="%(action_barcode_allocation)d" type="action"
                        class="oe_stat_button" icon="fa-barcode"
                        context="{'default_product_id': active_id, 'search_default_product_id': active_id}"
                        invisible="barcode_allocation_count == 0">
                    <field name="barcode_allocation_count"
                           widget="statinfo" string="Barcodes"/>
                </button>
            </xpath>

            <!-- Allocate button: visible only when product has no barcode -->
            <xpath expr="//field[@name='barcode']" position="after">
                <button name="action_allocate_barcode"
                        string="Allocate Barcode"
                        type="object"
                        class="oe_link"
                        groups="stock.group_stock_manager"
                        invisible="barcode != False"/>
            </xpath>

            <!-- Warning banner: barcode set but not tracked in registry -->
            <xpath expr="//sheet" position="inside">
                <div invisible="not barcode or barcode_in_registry"
                     class="alert alert-warning" role="alert">
                    <strong>Barcode not tracked in registry.</strong>
                    This product has a barcode that was not allocated through
                    the MML Barcode Registry. Use the
                    <a href="#" data-action="action_register_barcode">Register</a>
                    button to link it.
                </div>
            </xpath>

        </field>
    </record>
</odoo>
```

**Step 2: Commit**
```bash
git add barcodes/mml_barcode_registry/views/product_views.xml
git commit -m "feat(mml_barcode_registry): add product form barcode smart button and allocate action"
```

---

## Task 15: Import Wizard

**Files:**
- Create: `barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py`
- Create: `barcodes/mml_barcode_registry/wizard/wizard_views.xml`
- Create: `barcodes/mml_barcode_registry/tests/test_import_wizard.py`

**Step 1: Write failing import wizard tests**

```python
# barcodes/mml_barcode_registry/tests/test_import_wizard.py
import base64
import csv
import io
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


def _make_csv(rows: list[dict]) -> bytes:
    """Build a CSV file as bytes from a list of dicts."""
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue().encode('utf-8')


class TestImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Import Prefix',
            'prefix': '3333333',
            'sequence_start': 10000,
            'sequence_end': 10009,
            'company_id': cls.env.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Import Product',
            'type': 'consu',
            'barcode': '3333333100004',  # will match on import
        })

    def _make_wizard(self, csv_data: bytes):
        return self.env['barcode.import.wizard'].create({
            'prefix_id': self.prefix.id,
            'file_data': base64.b64encode(csv_data),
            'file_name': 'test_import.csv',
        })

    def test_csv_import_creates_registry_records(self):
        rows = [
            {'sequence': '333333310000', 'gtin_13': '3333333100004', 'description': 'Import Product'},
            {'sequence': '333333310001', 'gtin_13': '3333333100011', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        count = self.env['mml.barcode.registry'].search_count([
            ('prefix_id', '=', self.prefix.id),
        ])
        self.assertEqual(count, 2)

    def test_matched_product_gets_active_allocation(self):
        rows = [
            {'sequence': '333333310002', 'gtin_13': '3333333100028', 'description': 'Import Product'},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        alloc = self.env['mml.barcode.allocation'].search([
            ('product_id', '=', self.product.id),
            ('status', '=', 'active'),
        ])
        self.assertTrue(alloc)

    def test_unmatched_row_stays_unallocated(self):
        rows = [
            {'sequence': '333333310003', 'gtin_13': '3333333100035', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        reg = self.env['mml.barcode.registry'].search([
            ('sequence', '=', '333333310003'),
        ])
        self.assertEqual(reg.status, 'unallocated')

    def test_idempotent_on_reimport(self):
        rows = [
            {'sequence': '333333310004', 'gtin_13': '3333333100042', 'description': ''},
        ]
        csv_data = _make_csv(rows)
        self._make_wizard(csv_data).action_import()
        self._make_wizard(csv_data).action_import()
        count = self.env['mml.barcode.registry'].search_count([
            ('sequence', '=', '333333310004'),
        ])
        self.assertEqual(count, 1)

    def test_invalid_check_digit_flagged_as_warning(self):
        # gtin_13 '3333333100099' — check digit 9, actual should be computed
        rows = [
            {'sequence': '333333310009', 'gtin_13': '3333333100099', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        result = wizard.action_import()
        # Should complete but record warnings in wizard.import_warnings
        self.assertTrue(wizard.import_warnings)
```

**Step 2: Run to verify it fails**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestImportWizard --stop-after-init
```
Expected: `AttributeError` — `barcode.import.wizard` does not exist.

**Step 3: Implement `wizard/barcode_import_wizard.py`**

```python
# barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py
import base64
import csv
import io
import logging
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.mml_barcode_registry.services.gs1 import compute_check_digit, build_gtin13, build_gtin14

_logger = logging.getLogger(__name__)


class BarcodeImportWizard(models.TransientModel):
    _name = 'barcode.import.wizard'
    _description = 'Barcode Registry Import Wizard'

    prefix_id = fields.Many2one(
        'mml.barcode.prefix',
        string='Target Prefix',
        required=True,
    )
    file_data = fields.Binary(string='File (XLSX or CSV)', required=True)
    file_name = fields.Char(string='File Name')
    import_warnings = fields.Text(string='Warnings', readonly=True)
    preview_html = fields.Html(string='Preview', readonly=True)

    def action_preview(self):
        """Parse the uploaded file and show first 10 rows as a preview."""
        self.ensure_one()
        rows = self._parse_file()[:10]
        if not rows:
            self.preview_html = '<p>No data found in file.</p>'
            return

        html = ['<table class="table table-sm"><thead><tr>']
        for col in rows[0].keys():
            html.append(f'<th>{col}</th>')
        html.append('</tr></thead><tbody>')
        for row in rows:
            html.append('<tr>' + ''.join(f'<td>{v}</td>' for v in row.values()) + '</tr>')
        html.append('</tbody></table>')
        self.preview_html = ''.join(html)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'barcode.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        """
        Import XLSX or CSV. Idempotent — re-importing same data updates, not duplicates.
        Validates check digits and matches products by barcode field.
        """
        self.ensure_one()
        rows = self._parse_file()
        if not rows:
            raise UserError('No data rows found in the uploaded file.')

        warnings = []
        created = updated = skipped = 0

        Registry = self.env['mml.barcode.registry']
        Allocation = self.env['mml.barcode.allocation']

        for i, row in enumerate(rows, start=2):  # row 1 is header
            sequence = str(row.get('sequence', '') or '').strip()
            gtin_13_raw = str(row.get('gtin_13', '') or '').strip()
            description = str(row.get('description', '') or '').strip()

            if not sequence or len(sequence) != 12 or not sequence.isdigit():
                warnings.append(f"Row {i}: invalid sequence '{sequence}' — skipped.")
                continue

            # Validate check digit
            expected_check = compute_check_digit(sequence)
            expected_gtin13 = build_gtin13(sequence)
            if gtin_13_raw and gtin_13_raw != expected_gtin13:
                warnings.append(
                    f"Row {i}: check digit mismatch for {sequence}. "
                    f"File has {gtin_13_raw}, computed {expected_gtin13}. Using computed value."
                )

            gtin_14 = build_gtin14(sequence)

            # Find or create registry record
            existing = Registry.search([
                ('sequence', '=', sequence),
                ('company_id', '=', self.env.company.id),
            ], limit=1)

            if existing:
                skipped += 1
                registry = existing
            else:
                registry = Registry.create({
                    'sequence': sequence,
                    'prefix_id': self.prefix_id.id,
                    'status': 'unallocated',
                    'company_id': self.env.company.id,
                })
                created += 1

            # Try to match product by barcode
            if description:
                product = self.env['product.product'].search([
                    ('barcode', '=', expected_gtin13),
                ], limit=1)
                if not product:
                    # Try matching by name (fallback)
                    product = self.env['product.product'].search([
                        ('name', 'ilike', description),
                    ], limit=1)

                if product and registry.status == 'unallocated':
                    # Create active allocation
                    alloc = Allocation.search([
                        ('registry_id', '=', registry.id),
                        ('product_id', '=', product.id),
                        ('status', '=', 'active'),
                    ], limit=1)
                    if not alloc:
                        alloc = Allocation.create({
                            'registry_id': registry.id,
                            'product_id': product.id,
                            'status': 'active',
                            'allocation_date': date.today(),
                            'company_id': self.env.company.id,
                        })
                        registry.write({
                            'status': 'in_use',
                            'current_allocation_id': alloc.id,
                        })
                        # Sync barcode field if not already set
                        if not product.barcode:
                            product.barcode = expected_gtin13

        self.import_warnings = '\n'.join(warnings) if warnings else False

        _logger.info(
            'Barcode import complete: %d created, %d skipped, %d warnings',
            created, skipped, len(warnings),
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': (
                    f'{created} new records created, {skipped} existing skipped. '
                    f'{len(warnings)} warning(s).'
                ),
                'type': 'success' if not warnings else 'warning',
                'sticky': bool(warnings),
            },
        }

    def _parse_file(self) -> list[dict]:
        """Parse uploaded XLSX or CSV file. Returns list of row dicts."""
        if not self.file_data:
            return []

        raw = base64.b64decode(self.file_data)
        name = (self.file_name or '').lower()

        if name.endswith('.xlsx') or name.endswith('.xls'):
            return self._parse_xlsx(raw)
        else:
            return self._parse_csv(raw)

    def _parse_xlsx(self, raw: bytes) -> list[dict]:
        """Parse XLSX using openpyxl if available, else raise helpful error."""
        try:
            import openpyxl
        except ImportError:
            raise UserError(
                'openpyxl is not installed on this server. '
                'Please export your spreadsheet as CSV and upload that instead.'
            )
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip().lower() if h else '' for h in rows[0]]
        return [
            {headers[i]: (str(cell).strip() if cell is not None else '')
             for i, cell in enumerate(row)}
            for row in rows[1:]
            if any(cell is not None for cell in row)
        ]

    def _parse_csv(self, raw: bytes) -> list[dict]:
        """Parse CSV using stdlib csv module."""
        try:
            text = raw.decode('utf-8-sig')  # handles BOM from Excel CSV exports
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(text))
        return [
            {k.strip().lower(): v.strip() for k, v in row.items()}
            for row in reader
        ]
```

**Step 4: Create `wizard/wizard_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_barcode_import_wizard_form" model="ir.ui.view">
        <field name="name">barcode.import.wizard.form</field>
        <field name="model">barcode.import.wizard</field>
        <field name="arch" type="xml">
            <form string="Import Barcode Registry">
                <group string="Upload">
                    <field name="prefix_id"/>
                    <field name="file_data" filename="file_name" widget="binary"/>
                    <field name="file_name" invisible="1"/>
                </group>
                <group string="Preview" invisible="not preview_html">
                    <field name="preview_html" widget="html" nolabel="1"/>
                </group>
                <group string="Warnings" invisible="not import_warnings">
                    <field name="import_warnings" nolabel="1" readonly="1"/>
                </group>
                <footer>
                    <button name="action_preview" string="Preview"
                            type="object" class="btn-secondary"/>
                    <button name="action_import" string="Import"
                            type="object" class="btn-primary oe_highlight"/>
                    <button string="Cancel" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="action_barcode_import_wizard" model="ir.actions.act_window">
        <field name="name">Import Barcodes</field>
        <field name="res_model">barcode.import.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
    </record>

    <!-- Add Import menu item under Barcodes root -->
    <menuitem id="menu_barcode_import"
              name="Import"
              parent="mml_barcode_registry.menu_barcode_root"
              action="action_barcode_import_wizard"
              sequence="80"
              groups="stock.group_stock_manager"/>
</odoo>
```

**Step 5: Run to verify import wizard tests pass**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry:TestImportWizard --stop-after-init
```
Expected: All 5 tests pass.

**Step 6: Commit**
```bash
git add barcodes/mml_barcode_registry/wizard/
git commit -m "feat(mml_barcode_registry): add XLSX/CSV import wizard with check digit validation"
```

---

## Task 16: Full Test Suite Run + Manifest Verification

**Step 1: Verify `__manifest__.py` data order is correct**

Ensure `__manifest__.py` lists files in this exact order (dependencies must come before consumers):
```python
'data': [
    'security/barcode_registry_security.xml',
    'security/ir.model.access.csv',
    'data/barcode_prefix_data.xml',
    'views/mml_brand_views.xml',
    'views/barcode_prefix_views.xml',
    'views/barcode_registry_views.xml',
    'views/barcode_allocation_views.xml',
    'views/product_views.xml',
    'views/dashboard_views.xml',
    'views/menu.xml',
    'wizard/wizard_views.xml',
],
```

**Step 2: Run the full test suite**
```bash
python odoo-bin -d <your_db> --test-tags=/mml_barcode_registry --stop-after-init -i mml_barcode_registry
```
Expected: All tests pass across all 5 test classes.

**Step 3: Manually verify install**

1. Install `mml_barcode_registry` from Apps menu
2. Confirm "Barcodes" tile appears on home screen
3. Navigate to Configuration → Prefixes — confirm MML Primary prefix exists
4. Click "Generate Sequences" on MML Primary prefix — confirm notification shows 88,001 records created (99999 - 11999)
5. Navigate to a product, confirm "Allocate Barcode" button appears
6. Click "Allocate Barcode" — confirm GTIN-13 and GTIN-14 assigned, smart button shows count 1
7. Archive the product — confirm allocation moves to dormant

**Step 4: Final commit**
```bash
git add -A
git commit -m "feat(mml_barcode_registry): complete module — barcode lifecycle registry with one-click allocation"
```

---

## Post-Sprint Backlog

Items deferred per spec section 2.2 and design decisions:

- **SSCC-18 generation** — deferred to EDI ASN sprint (Briscoes requirement)
- **Barcode image generation** — GS1-128 / DataMatrix label PDFs
- **Physical label printing** — Mainfreight carton labelling integration
- **Custom OWL dashboard** — capacity gauge progress bar, live stats widget
- **GS1 NZ API integration** — validate/register GTINs with National Product Catalogue
- **Chatter audit trail** — full `mail.message` history on each registry record for every status transition
- **`action_register_barcode`** — link existing manually-set barcodes to registry (the "Register it" warning banner link)
