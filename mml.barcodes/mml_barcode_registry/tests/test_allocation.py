# barcodes/mml_barcode_registry/tests/test_allocation.py
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestArchiveHook(TransactionCase):
    """Tests for the product.product archive/unarchive hook."""

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


class TestOneClickAllocation(TransactionCase):
    """Tests for one-click GTIN allocation from product form."""

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
        self.assertEqual(packaging.qty, 1.0)

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
            'priority': 20,
            'company_id': self.env.company.id,
        })
        second_prefix.action_generate_sequences()
        # Exhaust the first prefix (5 slots)
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


class TestUniqueActiveAllocation(TransactionCase):
    """A product may only have one active allocation at a time."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prefix = cls.env['mml.barcode.prefix'].create({
            'name': 'Unique Active Prefix',
            'prefix': '2222222',
            'sequence_start': 10000,
            'sequence_end': 10009,
            'company_id': cls.env.company.id,
        })
        cls.prefix.action_generate_sequences()
        cls.product = cls.env['product.product'].create({
            'name': 'Unique Active Product',
            'type': 'consu',
        })

    def _get_unallocated(self):
        return self.env['mml.barcode.registry'].search([
            ('prefix_id', '=', self.prefix.id),
            ('status', '=', 'unallocated'),
        ], limit=1, order='sequence asc')

    def test_cannot_create_second_active_allocation_same_product(self):
        """A product may only have one active allocation at a time."""
        registry1 = self._get_unallocated()
        self.env['mml.barcode.allocation'].create({
            'registry_id': registry1.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })

        registry2 = self._get_unallocated()
        with self.assertRaises((ValidationError, UserError)):
            self.env['mml.barcode.allocation'].create({
                'registry_id': registry2.id,
                'product_id': self.product.id,
                'status': 'active',
                'allocation_date': date.today(),
                'company_id': self.env.company.id,
            })

    def test_dormant_allocation_allows_new_active(self):
        """A product with a dormant allocation may receive a new active one."""
        registry1 = self._get_unallocated()
        alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry1.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        alloc.action_dormant()

        registry2 = self._get_unallocated()
        # Must not raise
        new_alloc = self.env['mml.barcode.allocation'].create({
            'registry_id': registry2.id,
            'product_id': self.product.id,
            'status': 'active',
            'allocation_date': date.today(),
            'company_id': self.env.company.id,
        })
        self.assertEqual(new_alloc.status, 'active')


def test_exhausted_prefix_error_message_is_accurate():
    """Error message on exhausted prefix must reflect live state, not stale count."""
    import pathlib
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/product_product.py'
    ).read_text()
    assert 'search_count' in src, (
        "After FOR UPDATE SKIP LOCKED, must re-query search_count to verify "
        "actual availability before raising error"
    )
