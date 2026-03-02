from odoo.tests.common import TransactionCase


class TestEventLedger(TransactionCase):

    def test_emit_creates_record(self):
        """emit() creates a persisted mml.event record."""
        before = self.env['mml.event'].search_count([])
        self.env['mml.event'].emit(
            'freight.booking.confirmed',
            quantity=1,
            billable_unit='freight_booking',
        )
        after = self.env['mml.event'].search_count([])
        self.assertEqual(after, before + 1)

    def test_emit_sets_fields_correctly(self):
        """emit() populates all fields on the created record."""
        self.env['mml.event'].emit(
            'freight.booking.confirmed',
            quantity=2,
            billable_unit='freight_booking',
            res_model='freight.booking',
            res_id=99,
            payload={'ref': 'FBK-001'},
        )
        event = self.env['mml.event'].search([
            ('event_type', '=', 'freight.booking.confirmed'),
            ('res_id', '=', 99),
        ], limit=1)
        self.assertEqual(event.quantity, 2.0)
        self.assertEqual(event.billable_unit, 'freight_booking')
        self.assertEqual(event.res_model, 'freight.booking')
        self.assertEqual(event.res_id, 99)
        self.assertIn('FBK-001', event.payload_json)
        self.assertFalse(event.synced_to_platform)

    def test_emit_tags_company(self):
        """emit() always tags the event with the current company."""
        self.env['mml.event'].emit('test.event', quantity=1, billable_unit='test')
        event = self.env['mml.event'].search(
            [('event_type', '=', 'test.event')], limit=1
        )
        self.assertEqual(event.company_id, self.env.company)

    def test_emit_defaults_synced_false(self):
        """New events are not synced to platform by default."""
        event = self.env['mml.event'].emit(
            'test.unsynced', quantity=1, billable_unit='test'
        )
        self.assertFalse(event.synced_to_platform)

    def test_emit_empty_payload_is_valid_json(self):
        """emit() with no payload stores valid empty JSON object."""
        event = self.env['mml.event'].emit(
            'test.empty_payload', quantity=1, billable_unit='test'
        )
        import json
        parsed = json.loads(event.payload_json)
        self.assertEqual(parsed, {})
