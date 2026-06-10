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
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc'
    _rec_name = 'gtin_13'

    # Partial unique index (WHERE status = 'active') cannot be expressed via
    # _sql_constraints (which maps to CHECK CONSTRAINTs, not partial indexes).
    # models.Constraint was removed in favour of _sql_constraints in Odoo 19;
    # the v17 models.Constraint API that accepted a WHERE clause caused
    # TypeError: issubclass() arg 1 must be a class during metaclass processing.
    # Instead the partial index is created in init() below (runs on install and
    # every upgrade) for PostgreSQL-level race protection — two concurrent txns
    # both pass the ORM @api.constrains under READ COMMITTED, so the DB index is
    # the real guard. The ORM-level @api.constrains _check_unique_active_allocation
    # below remains as a friendly-error fallback for the common case.

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
        tracking=True,
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
        help='Earliest date GTIN can be reallocated (discontinue/last-supply date '
             '+ 48 months). Note: GS1 policy since 2019 is not to reuse GTINs at all; '
             'reuse is disabled unless the company opts in via "Allow GTIN reuse".',
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    def init(self):
        # Enforce one active allocation per (product, company) at the DB level.
        # A partial unique index is the only thing that closes the concurrent-
        # insert race two READ COMMITTED transactions slip through the
        # @api.constrains check with. BaseModel.init() runs on install and on
        # every module upgrade; IF NOT EXISTS keeps it idempotent.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS barcode_allocation_active_uniq
            ON mml_barcode_allocation (product_id, company_id)
            WHERE status = 'active'
        """)
        # Enforce one active allocation per registry slot at the DB level. Without
        # this, two different products can each take an active allocation pointing
        # at the SAME registry slot — the (product_id, company_id) index above does
        # not catch it because the products differ. This closes the double-
        # allocation race so a single GTIN can never be live on two products.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS barcode_allocation_registry_active_uniq
            ON mml_barcode_allocation (registry_id)
            WHERE status = 'active'
        """)

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
            # Cool-down baseline is the discontinue / last-supply date (today the
            # product stops being supplied), NOT allocation_date. Basing it on
            # allocation_date made a SKU allocated >4 years ago reuse-eligible the
            # instant it was archived — while it could still be on retailer shelves.
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

        Returning the registry slot to the unallocated pool (GTIN reuse) only
        happens when the company has opted in via company.allow_gtin_reuse AND the
        48-month cool-down has elapsed — GS1 policy since 2019 is not to reuse
        GTINs at all. When reuse is disabled the slot is retired instead, so the
        GTIN is never handed to another product.
        """
        today = date.today()
        for rec in self:
            rec._validate_transition('discontinued')
            reuse_allowed = rec.company_id.allow_gtin_reuse

            if reuse_allowed:
                # Only enforce/require the cool-down when reuse is actually on the
                # table — otherwise the slot is simply retired below.
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

            # Update the registry slot only if this allocation is still the current
            # one. Filters on both id and current_allocation_id to avoid a TOCTOU
            # window where a concurrent allocation has already claimed the slot.
            registry_to_clear = self.env['mml.barcode.registry'].search([
                ('id', '=', rec.registry_id.id),
                ('current_allocation_id', '=', rec.id),
            ])
            if registry_to_clear:
                if reuse_allowed:
                    # Opted in + cooled down: GTIN may be reassigned.
                    registry_to_clear.write({
                        'status': 'unallocated',
                        'current_allocation_id': False,
                    })
                else:
                    # Default: never reuse. Retire the slot (in_use → retired) so
                    # the GTIN is permanently taken out of circulation.
                    registry_to_clear.action_retire()
                    registry_to_clear.write({'current_allocation_id': False})
