# barcodes/mml_barcode_registry/tests/test_allocation.py
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


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
