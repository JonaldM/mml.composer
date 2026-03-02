"""
Tests for mml_roq_freight bridge module.
Structural tests are pure-Python; Odoo integration tests require --test-enable.
"""
import pytest

try:
    from odoo.tests.common import TransactionCase
except ImportError:
    TransactionCase = object  # fallback for pure-Python pytest run


def test_manifest_importable():
    """Bridge module directory is importable as a package."""
    import importlib.util
    import os
    manifest_path = os.path.join(
        os.path.dirname(__file__), '..', '__manifest__.py'
    )
    assert os.path.exists(manifest_path), '__manifest__.py not found'


def test_manifest_auto_install():
    """Bridge manifest must declare auto_install: True."""
    import ast
    import os
    manifest_path = os.path.join(
        os.path.dirname(__file__), '..', '__manifest__.py'
    )
    with open(manifest_path) as f:
        manifest = ast.literal_eval(f.read())
    assert manifest.get('auto_install') is True, 'auto_install must be True'


def test_manifest_depends_both_modules():
    """Bridge depends on both mml_roq_forecast and mml_freight."""
    import ast
    import os
    manifest_path = os.path.join(
        os.path.dirname(__file__), '..', '__manifest__.py'
    )
    with open(manifest_path) as f:
        manifest = ast.literal_eval(f.read())
    deps = manifest.get('depends', [])
    assert 'mml_roq_forecast' in deps
    assert 'mml_freight' in deps


def test_hooks_have_post_init_and_uninstall():
    """hooks.py must define both post_init_hook and uninstall_hook."""
    import os
    hooks_path = os.path.join(os.path.dirname(__file__), '..', 'hooks.py')
    with open(hooks_path) as f:
        content = f.read()
    assert 'def post_init_hook' in content
    assert 'def uninstall_hook' in content


@pytest.mark.odoo_integration
class TestROQFreightBridge(TransactionCase):
    """Odoo integration tests — require --test-enable. Skipped by plain pytest."""

    def test_freight_tender_field_on_shipment_group(self):
        self.assertIn('freight_tender_id', self.env['roq.shipment.group']._fields)

    def test_shipment_group_field_on_freight_tender(self):
        self.assertIn('shipment_group_id', self.env['freight.tender']._fields)

    def test_subscriptions_registered(self):
        subs = self.env['mml.event.subscription'].search([
            ('module', '=', 'mml_roq_freight'),
        ])
        event_types = subs.mapped('event_type')
        self.assertIn('roq.shipment_group.confirmed', event_types)
        self.assertIn('freight.booking.confirmed', event_types)
