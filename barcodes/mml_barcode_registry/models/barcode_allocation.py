# barcodes/mml_barcode_registry/models/barcode_allocation.py
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError


_ALLOCATION_STATUS = [
    ('active', 'Active'),
    ('dormant', 'Dormant'),
    ('discontinued', 'Discontinued'),
]

_VALID_ALLOCATION_TRANSITIONS = {
    'active': ['dormant'],
    'dormant': ['active', 'discontinued'],
    'discontinued': [],  # terminal — no transitions out
}


class BarcodeAllocation(models.Model):
    _name = 'mml.barcode.allocation'
    _description = 'Barcode Allocation History'
    _order = 'allocation_date desc'
    _rec_name = 'display_name'

    registry_id = fields.Many2one(
        'mml.barcode.registry',
        required=True,
        ondelete='restrict',
        index=True,
    )
    gtin_13 = fields.Char(
        related='registry_id.gtin_13',
        store=True,
        string='GTIN-13',
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        ondelete='restrict',
        index=True,
    )
    brand_id = fields.Many2one(
        'mml.brand',
        ondelete='set null',
    )
    status = fields.Selection(
        _ALLOCATION_STATUS,
        required=True,
        default='active',
        index=True,
    )
    allocation_date = fields.Date(default=fields.Date.today)
    discontinue_date = fields.Date()
    reuse_eligible_date = fields.Date(
        string='Reuse Eligible Date',
        help='Earliest date GTIN can be reallocated (discontinue_date + 48 months)',
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('registry_id', 'product_id', 'status')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.gtin_13 or '?'} → "
                f"{rec.product_id.display_name or '?'} [{rec.status}]"
            )

    def _validate_transition(self, new_status):
        allowed = _VALID_ALLOCATION_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise UserError(
                f"Cannot transition allocation from '{self.status}' to '{new_status}'. "
                f"Allowed: {allowed or 'none (terminal state)'}."
            )

    def action_dormant(self):
        """Transition active → dormant. Sets discontinue_date and reuse_eligible_date."""
        for rec in self:
            rec._validate_transition('dormant')
            today = date.today()
            rec.write({
                'status': 'dormant',
                'discontinue_date': today,
                'reuse_eligible_date': today + relativedelta(months=48),
            })

    def action_reactivate(self):
        """Transition dormant → active. Clears discontinue dates."""
        for rec in self:
            rec._validate_transition('active')
            rec.write({
                'status': 'active',
                'discontinue_date': False,
                'reuse_eligible_date': False,
            })

    def action_discontinue(self):
        """
        Transition dormant → discontinued.
        Validates 48-month cool-down. Returns registry slot to pool.
        """
        today = date.today()
        for rec in self:
            rec._validate_transition('discontinued')
            if rec.reuse_eligible_date and rec.reuse_eligible_date > today:
                months_remaining = (
                    (rec.reuse_eligible_date.year - today.year) * 12 +
                    rec.reuse_eligible_date.month - today.month
                )
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be discontinued yet. "
                    f"Reuse eligible in approximately {months_remaining} month(s) "
                    f"(eligible date: {rec.reuse_eligible_date})."
                )
            rec.status = 'discontinued'
            # Return registry slot to pool
            registry = rec.registry_id
            if registry.current_allocation_id == rec:
                registry.write({
                    'status': 'unallocated',
                    'current_allocation_id': False,
                })
