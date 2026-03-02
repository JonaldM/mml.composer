from odoo.tests.common import TransactionCase


class _StubFreightService:
    def __init__(self, env):
        self.env = env

    def create_tender(self, vals):
        return 42


class TestServiceRegistry(TransactionCase):

    def setUp(self):
        super().setUp()
        # Clean up any registrations from this test class between tests
        self.env['mml.registry'].deregister('_test_freight')

    def test_registered_service_is_returned(self):
        """service() returns the registered service instance."""
        self.env['mml.registry'].register('_test_freight', _StubFreightService)
        svc = self.env['mml.registry'].service('_test_freight')
        self.assertIsInstance(svc, _StubFreightService)

    def test_unregistered_service_returns_null(self):
        """service() returns a NullService when the service is not registered."""
        svc = self.env['mml.registry'].service('nonexistent_xyz')
        # NullService must not raise — all attribute access returns None
        result = svc.any_method_name()
        self.assertIsNone(result)

    def test_null_service_chained_calls_return_none(self):
        """NullService supports any method call without raising."""
        from odoo.addons.mml_base.services.null_service import NullService
        svc = NullService()
        self.assertIsNone(svc.create_tender({'lines': []}))
        self.assertIsNone(svc.get_booking_lead_time(99))

    def test_deregister_reverts_to_null(self):
        """deregister() removes the service; subsequent calls return NullService."""
        self.env['mml.registry'].register('_test_freight', _StubFreightService)
        self.env['mml.registry'].deregister('_test_freight')
        svc = self.env['mml.registry'].service('_test_freight')
        self.assertIsNone(svc.create_tender({}))
