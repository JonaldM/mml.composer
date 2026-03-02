import logging
from odoo.tests.common import TransactionCase


class TestEventSubscription(TransactionCase):

    def setUp(self):
        super().setUp()
        # Clean up test subscriptions between tests
        self.env['mml.event.subscription'].deregister_module('_test_module')

    def test_register_creates_subscription(self):
        """register() creates a subscription record."""
        self.env['mml.event.subscription'].register(
            event_type='test.event',
            handler_model='mml.event.subscription',
            handler_method='_noop',
            module='_test_module',
        )
        count = self.env['mml.event.subscription'].search_count([
            ('event_type', '=', 'test.event'),
            ('module', '=', '_test_module'),
        ])
        self.assertEqual(count, 1)

    def test_register_is_idempotent(self):
        """Registering the same handler twice does not create a duplicate."""
        for _ in range(2):
            self.env['mml.event.subscription'].register(
                event_type='test.idempotent',
                handler_model='mml.event.subscription',
                handler_method='_noop',
                module='_test_module',
            )
        count = self.env['mml.event.subscription'].search_count([
            ('event_type', '=', 'test.idempotent'),
        ])
        self.assertEqual(count, 1)

    def test_deregister_module_removes_all(self):
        """deregister_module() removes all subscriptions for that module."""
        for i in range(3):
            self.env['mml.event.subscription'].register(
                event_type=f'test.event_{i}',
                handler_model='mml.event.subscription',
                handler_method='_noop',
                module='_test_module',
            )
        self.env['mml.event.subscription'].deregister_module('_test_module')
        count = self.env['mml.event.subscription'].search_count([
            ('module', '=', '_test_module'),
        ])
        self.assertEqual(count, 0)

    def test_dispatch_calls_handler(self):
        """dispatch() calls the registered handler method."""
        # Use a real model method that we can verify was called via a side effect
        # We'll register a handler that emits a secondary event as proof
        self.env['mml.event.subscription'].register(
            event_type='test.dispatchable',
            handler_model='mml.event.subscription',
            handler_method='_test_handler',
            module='_test_module',
        )
        # Patch _test_handler onto the model for this test
        called = []
        original = type(self.env['mml.event.subscription'])
        original._test_handler = lambda self, event: called.append(event.event_type)
        try:
            self.env['mml.event'].emit('test.dispatchable', quantity=1, billable_unit='test')
            self.assertIn('test.dispatchable', called)
        finally:
            del original._test_handler

    def test_no_handler_for_unsubscribed_event(self):
        """emit() on an event with no subscribers does not raise."""
        # Should complete without error
        self.env['mml.event'].emit(
            'test.no_subscribers_xyz', quantity=1, billable_unit='test'
        )

    def test_failing_handler_does_not_break_emit(self):
        """A handler that raises an exception is caught; emit() still returns the event."""
        self.env['mml.event.subscription'].register(
            event_type='test.failing_handler',
            handler_model='mml.event.subscription',
            handler_method='_bad_handler',
            module='_test_module',
        )
        original = type(self.env['mml.event.subscription'])
        original._bad_handler = lambda self, event: (_ for _ in ()).throw(RuntimeError('boom'))
        try:
            # Must not raise — exception is caught and logged
            with self.assertLogs('odoo.addons.mml_base.models.mml_event_subscription', level='ERROR'):
                event = self.env['mml.event'].emit(
                    'test.failing_handler', quantity=1, billable_unit='test'
                )
            self.assertIsNotNone(event)
            self.assertTrue(event.id)
        finally:
            del original._bad_handler
