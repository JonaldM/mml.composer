# mml.barcodes/mml_barcode_registry/tests/test_lifecycle.py
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

    # ── Allocation state machine ─────────────────────────────────────────────

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
        alloc.action_reactivate()
        self.assertEqual(alloc.status, 'active')
        self.assertFalse(alloc.discontinue_date)
        self.assertFalse(alloc.reuse_eligible_date)

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
        registry.write({'current_allocation_id': alloc.id})
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

    # ── Registry state machine ───────────────────────────────────────────────

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
            'status': 'dormant',
            'allocation_date': date.today(),
            'discontinue_date': date.today(),
            'reuse_eligible_date': future_date,
            'company_id': self.env.company.id,
        })
        registry.write({'current_allocation_id': alloc.id})
        with self.assertRaises(UserError):
            registry.action_return_to_pool()

    def test_full_reuse_cycle(self):
        """Full cycle: unallocated → in_use → retired → unallocated after 48mo."""
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
        registry.write({'current_allocation_id': alloc.id})
        # Discontinue the allocation — registry returns to unallocated
        alloc.action_discontinue()
        self.assertEqual(registry.status, 'unallocated')
        self.assertFalse(registry.current_allocation_id)
        self.assertEqual(alloc.status, 'discontinued')

    # ── Sequence field validation ─────────────────────────────────────────────

    def test_blank_sequence_rejected(self):
        """Empty sequence must not be saveable."""
        from odoo.exceptions import ValidationError
        with self.assertRaises((ValidationError, Exception)):
            self.env['mml.barcode.registry'].create({
                'sequence': '',
                'prefix_id': self.prefix.id,
                'status': 'unallocated',
                'company_id': self.env.company.id,
            })

    def test_non_numeric_sequence_rejected(self):
        """Non-digit sequence must be rejected."""
        from odoo.exceptions import ValidationError
        with self.assertRaises((ValidationError, Exception)):
            self.env['mml.barcode.registry'].create({
                'sequence': 'ABCD12345678',
                'prefix_id': self.prefix.id,
                'status': 'unallocated',
                'company_id': self.env.company.id,
            })

    def test_wrong_length_sequence_rejected(self):
        """Sequence must be exactly 12 digits."""
        from odoo.exceptions import ValidationError
        with self.assertRaises((ValidationError, Exception)):
            self.env['mml.barcode.registry'].create({
                'sequence': '12345',
                'prefix_id': self.prefix.id,
                'status': 'unallocated',
                'company_id': self.env.company.id,
            })

    # ── GS1 cool-down date ────────────────────────────────────────────────────

    def test_reuse_eligible_date_counts_from_allocation_date(self):
        """
        GS1 best practice: 48-month cool-down starts from first allocation date,
        not from discontinuation date.
        """
        allocation_date = date(2020, 1, 1)
        expected_eligible = allocation_date + relativedelta(months=48)

        registry = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': allocation_date,
            'company_id': self.env.company.id,
        })
        alloc.action_dormant()
        self.assertEqual(
            alloc.reuse_eligible_date,
            expected_eligible,
            msg=(
                f"Expected reuse_eligible_date to be {expected_eligible} "
                f"(allocation_date + 48 months), got {alloc.reuse_eligible_date}. "
                "Cool-down must be counted from allocation_date, not discontinuation date."
            ),
        )
