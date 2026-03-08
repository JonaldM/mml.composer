# mml.barcodes/mml_barcode_registry/tests/test_import_wizard.py
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
            # GTIN-13 for sequence '333333310002' (prefix 3333333, seq_num 10002)
            'barcode': '3333333100022',
        })

    def _make_wizard(self, csv_data: bytes):
        return self.env['barcode.import.wizard'].create({
            'prefix_id': self.prefix.id,
            'file_data': base64.b64encode(csv_data),
            'file_name': 'test_import.csv',
        })

    def test_csv_import_creates_registry_records(self):
        rows = [
            {'sequence': '333333310000', 'gtin_13': '3333333100008', 'description': ''},
            {'sequence': '333333310001', 'gtin_13': '3333333100015', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        count = self.env['mml.barcode.registry'].search_count([
            ('prefix_id', '=', self.prefix.id),
        ])
        self.assertEqual(count, 2)

    def test_matched_product_gets_active_allocation(self):
        # gtin_13 matches product.barcode exactly — exercises the barcode-match path
        rows = [
            {'sequence': '333333310002', 'gtin_13': '3333333100022', 'description': 'Import Product'},
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
            {'sequence': '333333310003', 'gtin_13': '3333333100039', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        reg = self.env['mml.barcode.registry'].search([
            ('sequence', '=', '333333310003'),
        ])
        self.assertEqual(reg.status, 'unallocated')

    def test_idempotent_on_reimport(self):
        rows = [
            {'sequence': '333333310004', 'gtin_13': '3333333100046', 'description': ''},
        ]
        csv_data = _make_csv(rows)
        self._make_wizard(csv_data).action_import()
        self._make_wizard(csv_data).action_import()
        count = self.env['mml.barcode.registry'].search_count([
            ('sequence', '=', '333333310004'),
        ])
        self.assertEqual(count, 1)

    def test_invalid_check_digit_flagged_as_warning(self):
        # correct GTIN-13 for seq '333333310009' is '3333333100091'; '99' has wrong check digit
        rows = [
            {'sequence': '333333310009', 'gtin_13': '3333333100099', 'description': ''},
        ]
        wizard = self._make_wizard(_make_csv(rows))
        wizard.action_import()
        # Should complete but record a warning about the mismatch
        self.assertTrue(wizard.import_warnings)


def test_import_wizard_uses_savepoint_for_allocation():
    """Auto-allocation block must use savepoint to prevent orphaned registry records."""
    import pathlib
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py'
    ).read_text()
    assert 'savepoint' in src, (
        "Import wizard must wrap auto-allocation in self.env.cr.savepoint() "
        "to roll back registry status if product.write() fails"
    )
