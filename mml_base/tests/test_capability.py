from odoo.tests.common import TransactionCase


class TestCapabilityRegistry(TransactionCase):

    def test_register_and_has(self):
        """register() stores capability; has() returns True for it."""
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        self.assertTrue(self.env['mml.capability'].has('freight.tender.create'))

    def test_has_returns_false_for_unknown(self):
        """has() returns False for a capability that was never registered."""
        self.assertFalse(self.env['mml.capability'].has('nonexistent.capability'))

    def test_deregister_module_removes_all(self):
        """deregister_module() removes all capabilities registered by that module."""
        self.env['mml.capability'].register(
            ['freight.tender.create', 'freight.booking.confirm'],
            module='mml_freight',
        )
        self.env['mml.capability'].deregister_module('mml_freight')
        self.assertFalse(self.env['mml.capability'].has('freight.tender.create'))
        self.assertFalse(self.env['mml.capability'].has('freight.booking.confirm'))

    def test_register_is_idempotent(self):
        """Registering the same capability twice does not create duplicates."""
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        self.env['mml.capability'].register(['freight.tender.create'], module='mml_freight')
        count = self.env['mml.capability'].search_count([
            ('name', '=', 'freight.tender.create'),
        ])
        self.assertEqual(count, 1)
