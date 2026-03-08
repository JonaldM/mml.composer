# mml.barcodes/mml_barcode_registry/services/barcode_service.py
"""
BarcodeService — registered with mml.registry under key 'barcode'.
Allows other modules to call barcode operations without a hard import.
"""


class BarcodeService:
    """
    Thin adapter exposing barcode allocation operations via the service locator.
    All methods take `env` as the first argument (no self.env).
    """

    @staticmethod
    def allocate_next(env, product_id: int) -> dict:
        """
        Allocate the next available GTIN to the given product.

        Returns:
            dict with keys: gtin_13, gtin_14, allocation_id
        Raises:
            UserError if no GTINs are available or product already has one.
        """
        product = env['product.product'].browse(product_id)
        product.action_allocate_barcode()
        allocation = env['mml.barcode.allocation'].search([
            ('product_id', '=', product_id),
            ('status', '=', 'active'),
        ], limit=1, order='id desc')
        return {
            'gtin_13': allocation.gtin_13,
            'gtin_14': allocation.registry_id.gtin_14,
            'allocation_id': allocation.id,
        }

    @staticmethod
    def get_allocation(env, product_id: int) -> dict | None:
        """
        Return the active allocation for a product, or None if none exists.
        """
        allocation = env['mml.barcode.allocation'].search([
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
