# mml.barcodes/mml_barcode_registry/hooks.py
import logging

_logger = logging.getLogger(__name__)


def _register_barcode_platform(env) -> None:
    """Register mml_barcode_registry capabilities and BarcodeService.

    Shared helper called by both post_init_hook (fresh install) and the
    19.0.1.0.1 post-migration script (upgrade).  Idempotent: re-registering
    a capability or service is a no-op if the entry already exists.

    Why this helper exists:
        post_init_hook only runs on fresh module install (-i), NOT on
        upgrade (-u).  Without this helper the BarcodeService entry in
        ir.config_parameter and the mml.capability rows would silently
        vanish after a production -u, causing mml.registry to return
        NullService for every call to service('barcode').
    """
    from odoo.addons.mml_barcode_registry.services.barcode_service import BarcodeService

    env['mml.capability'].register(
        [
            'barcode.allocate',
            'barcode.generate_sequences',
            'barcode.registry.read',
        ],
        module='mml_barcode_registry',
    )
    env['mml.registry'].register('barcode', BarcodeService)
    _logger.info('mml_barcode_registry: capabilities and service registered')


def post_init_hook(env) -> None:
    """Register capabilities and service on module install."""
    _register_barcode_platform(env)


def uninstall_hook(env) -> None:
    """Deregister all mml_barcode_registry entries on uninstall."""
    env['mml.capability'].deregister_module('mml_barcode_registry')
    env['mml.registry'].deregister('barcode')
    env['mml.event.subscription'].deregister_module('mml_barcode_registry')
    _logger.info('mml_barcode_registry: capabilities and service deregistered')
