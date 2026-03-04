# barcodes/mml_barcode_registry/models/product_product.py
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    barcode_allocation_id = fields.Many2one(
        'mml.barcode.allocation',
        compute='_compute_barcode_allocation_id',
        string='Active Barcode Allocation',
        store=False,
    )
    barcode_allocation_count = fields.Integer(
        compute='_compute_barcode_allocation_id',
        string='Barcode Allocations',
        store=False,
    )
    barcode_in_registry = fields.Boolean(
        compute='_compute_barcode_in_registry',
        store=False,
        help='True if product.barcode is tracked in the registry',
    )

    @api.depends()
    def _compute_barcode_allocation_id(self):
        Allocation = self.env['mml.barcode.allocation']
        for product in self:
            active_alloc = Allocation.search([
                ('product_id', '=', product.id),
                ('status', '=', 'active'),
            ], limit=1)
            product.barcode_allocation_id = active_alloc
            product.barcode_allocation_count = Allocation.search_count([
                ('product_id', '=', product.id),
            ])

    @api.depends('barcode')
    def _compute_barcode_in_registry(self):
        Registry = self.env['mml.barcode.registry']
        for product in self:
            if not product.barcode:
                product.barcode_in_registry = False
            else:
                product.barcode_in_registry = bool(
                    Registry.search_count([('gtin_13', '=', product.barcode)])
                )

    def write(self, vals):
        res = super().write(vals)
        if 'active' not in vals:
            return res

        Allocation = self.env['mml.barcode.allocation']
        if not vals['active']:
            # Product archived → set active allocations dormant
            active_allocs = Allocation.search([
                ('product_id', 'in', self.ids),
                ('status', '=', 'active'),
            ])
            if active_allocs:
                active_allocs.action_dormant()
        else:
            # Product un-archived → reactivate dormant allocations
            dormant_allocs = Allocation.search([
                ('product_id', 'in', self.ids),
                ('status', '=', 'dormant'),
            ])
            if dormant_allocs:
                dormant_allocs.action_reactivate()

        return res
