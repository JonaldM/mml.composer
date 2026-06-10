# mml.barcodes/mml_barcode_registry/services/barcode_service.py
"""
BarcodeService - registered with mml.registry under key 'barcode'.
Allows other modules to call barcode operations without a hard import.

Retrieved via ``env['mml.registry'].service('barcode')``, which instantiates
the class with the calling environment - matching the constructor contract of
every other platform service (EDIService, TPLService, ROQService,
FreightService): ``__init__(self, env)``. Methods operate on ``self.env``.
"""


class BarcodeService:
    """
    Thin adapter exposing barcode allocation operations via the service locator.

    Instantiated by ``mml.registry.service('barcode')`` with the active
    environment; all methods operate on ``self.env``.
    """

    def __init__(self, env):
        self.env = env

    def allocate_next(self, product_id: int) -> dict:
        """
        Allocate the next available GTIN to the given product.

        Returns:
            dict with keys: gtin_13, gtin_14, allocation_id
        Raises:
            UserError if no GTINs are available or product already has one.
        """
        product = self.env['product.product'].browse(product_id)
        product.action_allocate_barcode()
        allocation = self.env['mml.barcode.allocation'].search([
            ('product_id', '=', product_id),
            ('status', '=', 'active'),
        ], limit=1, order='id desc')
        if not allocation:
            from odoo.exceptions import UserError
            raise UserError(
                f'Barcode allocation for product {product_id} failed: '
                'no active allocation found after action_allocate_barcode(). '
                'Check barcode pool availability.'
            )
        return {
            'gtin_13': allocation.gtin_13,
            'gtin_14': allocation.registry_id.gtin_14,
            'allocation_id': allocation.id,
        }

    def get_allocation(self, product_id: int) -> dict | None:
        """
        Return the active allocation for a product, or None if none exists.
        """
        allocation = self.env['mml.barcode.allocation'].search([
            ('product_id', '=', product_id),
            ('status', '=', 'active'),
        ], limit=1)
        if not allocation:
            return None
        return {
            'gtin_13': allocation.gtin_13,
            'gtin_14': allocation.registry_id.gtin_14,
            'allocation_id': allocation.id,
            'allocation_date': allocation.allocation_date,
        }
