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

    def test_service_rehydrates_after_registry_cleared(self):
        """Simulate forked worker: clear in-process dict, service() must still work."""
        from odoo.addons.mml_base.models import mml_registry as reg_module

        class _DummyService:
            def __init__(self, env):
                self.env = env
            def is_null(self):
                return False

        self.env['mml.registry'].register('test_rehydrate', _DummyService)
        # Simulate worker fork: wipe the in-process dict
        reg_module._SERVICE_REGISTRY.clear()
        # service() must re-hydrate from DB and return a working instance
        svc = self.env['mml.registry'].service('test_rehydrate')
        self.assertFalse(svc.is_null(), "Expected real service, got NullService after re-hydration")
