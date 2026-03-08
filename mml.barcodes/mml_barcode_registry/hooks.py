# mml.barcodes/mml_barcode_registry/hooks.py
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Register capabilities and service on module install."""
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


def uninstall_hook(env):
    """Deregister all mml_barcode_registry entries on uninstall."""
    env['mml.capability'].deregister_module('mml_barcode_registry')
    env['mml.registry'].deregister('barcode')
    env['mml.event.subscription'].deregister_module('mml_barcode_registry')
    _logger.info('mml_barcode_registry: capabilities and service deregistered')
