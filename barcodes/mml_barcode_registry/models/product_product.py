# barcodes/mml_barcode_registry/models/product_product.py
from odoo import api, fields, models
from odoo.exceptions import UserError


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
        if vals['active'] is False:
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

    def action_allocate_barcode(self):
        """
        One-click GTIN allocation. Assigns next available GTIN to this product.
        Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate allocation races.
        """
        self.ensure_one()

        if self.barcode:
            raise UserError(
                f"Product already has barcode {self.barcode}. "
                "Remove it first or use 'Register' to track an existing barcode."
            )

        # 1. Find best available prefix (priority ASC, then by availability)
        prefix = self._find_allocation_prefix()
        if not prefix:
            raise UserError(
                "No active barcode prefix configured. "
                "Please contact your system administrator."
            )

        # 2. Lock and claim the next unallocated registry record
        registry = self._claim_next_registry(prefix)

        # 3. Determine brand from product category name (best-effort match)
        brand = self._resolve_brand()

        # 4. Create the allocation record
        allocation = self.env['mml.barcode.allocation'].create({
            'registry_id': registry.id,
            'product_id': self.id,
            'brand_id': brand.id if brand else False,
            'status': 'active',
            'allocation_date': fields.Date.today(),
            'company_id': self.env.company.id,
        })

        # 5. Update registry
        registry.write({
            'status': 'in_use',
            'current_allocation_id': allocation.id,
        })

        # 6. Write GTIN-13 to product barcode field
        self.write({'barcode': registry.gtin_13})

        # 7. Create GTIN-14 outer carton packaging record
        self.env['product.packaging'].create({
            'name': 'Outer Carton',
            'product_id': self.id,
            'barcode': registry.gtin_14,
            'qty': 1.0,
        })

        # 8. Emit billing event
        self.env['mml.event'].emit(
            'barcode.gtin.allocated',
            billable_unit='gtin',
            quantity=1.0,
            res_model='product.product',
            res_id=self.id,
            source_module='mml_barcode_registry',
            payload={'gtin_13': registry.gtin_13, 'gtin_14': registry.gtin_14},
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Barcode Allocated',
                'message': (
                    f'Allocated GTIN-13: {registry.gtin_13} '
                    f'and GTIN-14: {registry.gtin_14}'
                ),
                'type': 'success',
            },
        }

    def _find_allocation_prefix(self):
        """Return the best active prefix with available unallocated records."""
        prefixes = self.env['mml.barcode.prefix'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], order='priority asc')

        for prefix in prefixes:
            has_available = self.env['mml.barcode.registry'].search_count([
                ('prefix_id', '=', prefix.id),
                ('status', '=', 'unallocated'),
            ])
            if has_available:
                return prefix
        return None

    def _claim_next_registry(self, prefix):
        """
        Use SELECT FOR UPDATE SKIP LOCKED to atomically claim the next
        unallocated registry record. Raises UserError if none available.
        """
        self.env.cr.execute("""
            SELECT id FROM mml_barcode_registry
            WHERE status = 'unallocated'
              AND prefix_id = %s
              AND company_id = %s
            ORDER BY sequence ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (prefix.id, self.env.company.id))
        row = self.env.cr.fetchone()

        if not row:
            remaining = self.env['mml.barcode.registry'].search_count([
                ('prefix_id', '=', prefix.id),
                ('status', '=', 'unallocated'),
            ])
            raise UserError(
                f"No unallocated barcodes available in prefix '{prefix.name}'. "
                f"Remaining capacity: {remaining}. "
                "Contact GS1 NZ (www.gs1nz.org) to acquire an additional number block."
            )

        return self.env['mml.barcode.registry'].browse(row[0])

    def _resolve_brand(self):
        """Best-effort: match product category name against mml.brand records."""
        if not self.categ_id:
            return None
        return self.env['mml.brand'].search([
            ('name', 'ilike', self.categ_id.name),
            ('company_id', '=', self.env.company.id),
        ], limit=1) or None
