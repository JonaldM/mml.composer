"""Post-migration for mml_barcode_registry 19.0.1.0.1.

Ensures BarcodeService and barcode capabilities are registered in mml.registry
and mml.capability after a module upgrade.

Why this is needed:
    post_init_hook only runs on fresh module install (-i), NOT on upgrade (-u).
    When upgrading an existing Odoo instance, the ir.config_parameter entry for
    'mml_registry.service.barcode' and the mml.capability rows for this module
    may be absent or stale if the module was previously at a lower version,
    leaving mml.registry returning NullService for every call to
    service('barcode') and capability checks silently returning False.

    The folder is versioned 19.0.1.0.1 (one patch above the prior installed
    19.0.1.0.0) so Odoo's migration manager actually runs it on -u; a folder
    equal to the installed version is skipped.

Manual verification:
    SELECT value FROM ir_config_parameter
    WHERE key = 'mml_registry.service.barcode';
    -- Expected: path to BarcodeService class

    SELECT name FROM mml_capability
    WHERE module = 'mml_barcode_registry';
    -- Expected: barcode.allocate, barcode.generate_sequences, barcode.registry.read
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version: str) -> None:
    """Re-register BarcodeService and barcode capabilities in mml.registry.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. None/empty means
            fresh install -- post_init_hook already handles that case, but
            calling _register_barcode_platform() again is harmless (idempotent).
    """
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mml_barcode_registry.hooks import _register_barcode_platform

    env = api.Environment(cr, SUPERUSER_ID, {})
    _register_barcode_platform(env)
    _logger.info(
        'mml_barcode_registry 19.0.1.0.1: re-registered BarcodeService and '
        'barcode capabilities in mml.registry / mml.capability'
    )
