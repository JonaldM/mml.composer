from odoo.tests.common import TransactionCase


class TestLicense(TransactionCase):

    def setUp(self):
        super().setUp()
        # Remove any existing license records so tests start clean
        self.env['mml.license'].search([]).unlink()

    def test_get_current_creates_default(self):
        """get_current() creates an internal-tier license when none exists."""
        lic = self.env['mml.license'].get_current()
        self.assertIsNotNone(lic)
        self.assertEqual(lic.tier, 'internal')

    def test_get_current_is_idempotent(self):
        """get_current() called twice returns the same record, not two records."""
        lic1 = self.env['mml.license'].get_current()
        lic2 = self.env['mml.license'].get_current()
        self.assertEqual(lic1.id, lic2.id)
        self.assertEqual(self.env['mml.license'].search_count([]), 1)

    def test_internal_tier_permits_all_modules(self):
        """Internal tier (wildcard) permits any module name."""
        lic = self.env['mml.license'].get_current()
        self.assertTrue(lic.module_permitted('mml_freight'))
        self.assertTrue(lic.module_permitted('mml_roq_forecast'))
        self.assertTrue(lic.module_permitted('anything_at_all'))

    def test_explicit_grants_permit_only_listed_modules(self):
        """A license with explicit module list only permits listed modules."""
        lic = self.env['mml.license'].create({
            'tier': 'starter',
            'module_grants_json': '["mml_edi"]',
        })
        self.assertTrue(lic.module_permitted('mml_edi'))
        self.assertFalse(lic.module_permitted('mml_freight'))
        self.assertFalse(lic.module_permitted('mml_roq_forecast'))

    def test_default_floor_is_zero(self):
        """Fresh internal license has zero floor amount."""
        lic = self.env['mml.license'].get_current()
        self.assertEqual(lic.floor_amount, 0.0)

    def test_default_seat_limit_is_zero_unlimited(self):
        """Default seat_limit of 0 means unlimited."""
        lic = self.env['mml.license'].get_current()
        self.assertEqual(lic.seat_limit, 0)
