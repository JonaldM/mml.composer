# mml.barcodes/mml_barcode_registry/models/product_product.py
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
        # Guard direct edits to a registry-managed barcode. If a product has an
        # active allocation, its barcode is owned by the registry; clearing or
        # overwriting it here would leave the allocation 'active' / registry
        # 'in_use' while the product no longer carries the GTIN. Allow the write
        # only when the new barcode matches the active allocation's GTIN-13.
        if 'barcode' in vals:
            Allocation = self.env['mml.barcode.allocation']
            for product in self:
                active_alloc = Allocation.search([
                    ('product_id', '=', product.id),
                    ('status', '=', 'active'),
                ], limit=1)
                if not active_alloc:
                    continue
                managed_gtin = active_alloc.registry_id.gtin_13
                if vals['barcode'] != managed_gtin:
                    raise UserError(
                        f"Product '{product.display_name}' has an active barcode "
                        f"allocation (GTIN-13 {managed_gtin}). Its barcode is managed "
                        f"by the barcode registry and cannot be changed or cleared "
                        f"directly. Discontinue or deactivate the allocation first."
                    )

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

        existing_active = self.env['mml.barcode.allocation'].search([
            ('product_id', '=', self.id),
            ('company_id', '=', self.env.company.id),
            ('status', '=', 'active'),
        ], limit=1)
        if existing_active:
            raise UserError(
                f"Product already has an active GTIN allocation: "
                f"{existing_active.registry_id.gtin_13}. "
                f"Retire or deactivate the existing allocation first."
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

        # 7. The GTIN-14 (outer carton) is already modelled on the registry
        # record (registry.gtin_14). The product.packaging model was removed in
        # Odoo 19 (merged into UoM), so we no longer create a packaging record —
        # doing so would crash and roll back the whole allocation. Consumers that
        # need the GTIN-14 read it from the allocation's registry_id.gtin_14.

        # 8. Emit billing event — best-effort; failure must not roll back the
        # allocation. Emit as sudo: the mml.event ledger ACL grants base.group_user
        # read only, so a non-admin clicking allocate cannot create the event as
        # themselves and it would be silently lost. Still resilient (warn on
        # failure) so a ledger problem never rolls back a successful allocation.
        try:
            self.env['mml.event'].sudo().emit(
                'barcode.gtin.allocated',
                billable_unit='gtin',
                quantity=1.0,
                res_model='product.product',
                res_id=self.id,
                source_module='mml_barcode_registry',
                payload={'gtin_13': registry.gtin_13, 'gtin_14': registry.gtin_14},
            )
        except Exception:
            _logger.warning(
                "Failed to emit barcode.gtin.allocated event for product %s "
                "(gtin_13=%s). Allocation succeeded.",
                self.id, registry.gtin_13,
                exc_info=True,
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
