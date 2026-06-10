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
        self.assertEqual(self.prefix.capacity, 10)


def test_prefix_has_sequence_range_constraint():
    """A constrains method must reject inverted/negative sequence ranges.

    Without it a user can save sequence_start > sequence_end; capacity then
    computes to zero and generation silently produces no records.
    """
    import pathlib
    src = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'models' / 'barcode_prefix.py'
    ).read_text()
    assert "@api.constrains('sequence_start', 'sequence_end')" in src, (
        "barcode_prefix.py must declare an @api.constrains on "
        "('sequence_start', 'sequence_end')"
    )
    assert 'ValidationError' in src, (
        "the range constraint must raise ValidationError on an invalid range"
    )
