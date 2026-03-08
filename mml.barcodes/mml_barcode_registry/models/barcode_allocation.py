from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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


def _months_until(target_date, today):
    """Return approximate months remaining (ceiling) until target_date from today."""
    delta = relativedelta(target_date, today)
    months = delta.years * 12 + delta.months
    return months + 1 if delta.days > 0 else months


class BarcodeAllocation(models.Model):
    _name = 'mml.barcode.allocation'
    _description = 'Barcode Allocation History'
    _order = 'allocation_date desc'
    _rec_name = 'gtin_13'

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
        help='Earliest date GTIN can be reallocated (allocation_date + 48 months, per GS1 best practice)',
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.depends('gtin_13', 'product_id.display_name', 'status')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.gtin_13 or '?'} → "
                f"{rec.product_id.display_name or '?'} [{rec.status}]"
            )

    @api.constrains('product_id', 'company_id', 'status')
    def _check_unique_active_allocation(self):
        for rec in self:
            if rec.status != 'active':
                continue
            duplicate = self.search([
                ('product_id', '=', rec.product_id.id),
                ('company_id', '=', rec.company_id.id),
                ('status', '=', 'active'),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f"Product '{rec.product_id.display_name}' already has an active "
                    f"barcode allocation (GTIN: {duplicate.registry_id.gtin_13}). "
                    f"Deactivate the existing allocation before creating a new one."
                )

    def _validate_transition(self, new_status):
        self.ensure_one()
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
            reuse_start = rec.allocation_date or today
            rec.write({
                'status': 'dormant',
                'discontinue_date': today,
                'reuse_eligible_date': reuse_start + relativedelta(months=48),
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
            if not rec.reuse_eligible_date:
                raise UserError(
                    f"GTIN {rec.gtin_13 or rec.registry_id.sequence!r} has no reuse eligible "
                    f"date set. Set 'discontinue_date' and allow the system to compute "
                    f"the eligibility date before discontinuing."
                )
            if rec.reuse_eligible_date > today:
                months = _months_until(rec.reuse_eligible_date, today)
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be discontinued yet. "
                    f"Reuse eligible in approximately {months} month(s) "
                    f"(eligible date: {rec.reuse_eligible_date})."
                )
            rec.write({'status': 'discontinued'})
            # Return registry slot to pool if this is the active allocation
            registry = rec.registry_id
            if registry.current_allocation_id == rec:
                registry.write({
                    'status': 'unallocated',
                    'current_allocation_id': False,
                })
