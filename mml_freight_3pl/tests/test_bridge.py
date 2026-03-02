"""
Tests for mml_freight_3pl bridge module.
Pure-Python structural tests run with plain pytest.
Odoo integration tests require --test-enable.
"""
import pytest

try:
    from odoo.tests.common import TransactionCase
except ImportError:
    TransactionCase = object  # fallback for pure-Python pytest run


def test_manifest_auto_install():
    """Bridge manifest must declare auto_install: True."""
    import ast
    import os
    manifest_path = os.path.join(os.path.dirname(__file__), '..', '__manifest__.py')
    with open(manifest_path) as f:
        manifest = ast.literal_eval(f.read())
    assert manifest.get('auto_install') is True


def test_manifest_depends_both_modules():
    """Bridge depends on both mml_freight and stock_3pl_core."""
    import ast
    import os
    manifest_path = os.path.join(os.path.dirname(__file__), '..', '__manifest__.py')
    with open(manifest_path) as f:
        manifest = ast.literal_eval(f.read())
    deps = manifest.get('depends', [])
    assert 'mml_freight' in deps
    assert 'stock_3pl_core' in deps


def test_hooks_have_post_init_and_uninstall():
    """hooks.py must define both post_init_hook and uninstall_hook."""
    import os
    hooks_path = os.path.join(os.path.dirname(__file__), '..', 'hooks.py')
    with open(hooks_path) as f:
        content = f.read()
    assert 'def post_init_hook' in content
    assert 'def uninstall_hook' in content


def test_bridge_model_name():
    """bridge model file must define mml.3pl.bridge."""
    import os
    bridge_path = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'mml_3pl_bridge.py'
    )
    with open(bridge_path) as f:
        content = f.read()
    assert "mml.3pl.bridge" in content


@pytest.mark.odoo_integration
class TestFreight3PLBridge(TransactionCase):
    """Odoo integration tests — require --test-enable. Skipped by plain pytest."""

    def test_subscriptions_registered(self):
        """Bridge subscription is registered on install."""
        subs = self.env['mml.event.subscription'].search([
            ('module', '=', 'mml_freight_3pl'),
            ('event_type', '=', 'freight.booking.confirmed'),
        ])
        self.assertEqual(len(subs), 1)

    def test_bridge_handler_model_exists(self):
        """mml.3pl.bridge model is accessible."""
        self.assertIsNotNone(self.env.get('mml.3pl.bridge'))
