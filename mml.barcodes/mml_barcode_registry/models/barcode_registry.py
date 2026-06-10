from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.mml_barcode_registry.services.gs1 import build_gtin13, build_gtin14


_REGISTRY_STATUS = [
    ('unallocated', 'Unallocated'),
    ('reserved', 'Reserved'),
    ('in_use', 'In Use'),
    ('retired', 'Retired'),
]

_VALID_REGISTRY_TRANSITIONS = {
    'unallocated': ['reserved', 'in_use'],
    'reserved': ['unallocated', 'in_use'],
    'in_use': ['retired'],
    'retired': ['unallocated'],
}


class BarcodeRegistry(models.Model):
    _name = 'mml.barcode.registry'
    _description = 'GS1 Barcode Registry'
    _order = 'sequence asc'
    _rec_name = 'gtin_13'

    sequence = fields.Char(
        string='Sequence',
        size=12,
        required=True,
        help='12-digit sequence number (no check digit)',
    )
    check_digit = fields.Integer(
        compute='_compute_gtin',
        store=True,
    )
    gtin_13 = fields.Char(
        string='GTIN-13',
        size=13,
        compute='_compute_gtin',
        store=True,
        index=True,
    )
    gtin_14 = fields.Char(
        string='GTIN-14',
        size=14,
        compute='_compute_gtin',
        store=True,
        index=True,
    )
    prefix_id = fields.Many2one(
        'mml.barcode.prefix',
        string='Prefix',
        ondelete='restrict',
    )
    status = fields.Selection(
        _REGISTRY_STATUS,
        required=True,
        default='unallocated',
        index=True,
    )
    current_allocation_id = fields.Many2one(
        'mml.barcode.allocation',
        string='Current Allocation',
        ondelete='set null',
    )
    allocation_ids = fields.One2many(
        'mml.barcode.allocation',
        'registry_id',
        string='Allocation History',
    )
    reuse_eligible_date = fields.Date(
        compute='_compute_reuse_eligible_date',
        store=True,
        string='Reuse Eligible Date',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    # Use _sql_constraints (supported across Odoo 16–19) rather than models.Constraint,
    # which changed internal representation in Odoo 19 and can trigger
    # TypeError: issubclass() arg 1 must be a class during metaclass processing.
    _sql_constraints = [
        ('gtin13_uniq', 'UNIQUE(gtin_13)', 'GTIN-13 must be unique.'),
        ('gtin14_uniq', 'UNIQUE(gtin_14)', 'GTIN-14 must be unique.'),
        ('sequence_company_uniq', 'UNIQUE(sequence, company_id)', 'Sequence must be unique per company.'),
    ]

    @api.depends('sequence')
    def _compute_gtin(self):
        for rec in self:
            if rec.sequence and len(rec.sequence) == 12 and rec.sequence.isdigit():
                rec.gtin_13 = build_gtin13(rec.sequence)
                rec.check_digit = int(rec.gtin_13[-1])
                rec.gtin_14 = build_gtin14(rec.sequence)
            else:
                rec.gtin_13 = False
                rec.check_digit = 0
                rec.gtin_14 = False

    @api.depends('allocation_ids.reuse_eligible_date')
    def _compute_reuse_eligible_date(self):
        for rec in self:
            latest = self.env['mml.barcode.allocation'].search([
                ('registry_id', '=', rec.id),
                ('reuse_eligible_date', '!=', False),
            ], order='reuse_eligible_date desc', limit=1)
            rec.reuse_eligible_date = latest.reuse_eligible_date if latest else False

    @api.constrains('sequence')
    def _check_sequence_format(self):
        for rec in self:
            if not rec.sequence:
                raise ValidationError("Barcode registry sequence cannot be empty.")
            if not rec.sequence.isdigit():
                raise ValidationError(
                    f"Sequence '{rec.sequence}' must contain only digits (0-9)."
                )
            if len(rec.sequence) != 12:
                raise ValidationError(
                    f"Sequence must be exactly 12 digits (got {len(rec.sequence)}: '{rec.sequence}')."
                )

    def _validate_transition(self, new_status):
        """Raise UserError if transition from current status to new_status is not allowed."""
        self.ensure_one()
        allowed = _VALID_REGISTRY_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise UserError(
                f"Cannot transition barcode {(self.gtin_13 or self.sequence)!r} from "
                f"'{self.status}' to '{new_status}'."
            )

    def action_reserve(self):
        for rec in self:
            rec._validate_transition('reserved')
            rec.write({'status': 'reserved'})

    def action_unreserve(self):
        for rec in self:
            rec._validate_transition('unallocated')
            rec.write({'status': 'unallocated'})

    def action_retire(self):
        for rec in self:
            rec._validate_transition('retired')
            rec.write({'status': 'retired'})

    def action_return_to_pool(self):
        """Move retired registry record back to unallocated. Requires the company
        to have opted in to GTIN reuse, plus the 48-month cool-down."""
        today = fields.Date.today()
        for rec in self:
            rec._validate_transition('unallocated')
            # GS1 policy since 2019 is not to reuse GTINs at all. Returning a slot
            # to the pool only happens if the company explicitly opts in.
            if not rec.company_id.allow_gtin_reuse:
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be returned to the pool: GTIN reuse "
                    f"is disabled for this company (GS1 best practice is to never "
                    f"reuse a GTIN). A registry administrator can enable 'Allow GTIN "
                    f"reuse' on the company if reuse is genuinely required.\n\n"
                    f"To obtain new GTINs, apply for an additional prefix block at "
                    f"https://www.gs1nz.org/"
                )
            if rec.reuse_eligible_date and rec.reuse_eligible_date > today:
                delta = relativedelta(rec.reuse_eligible_date, today)
                months_remaining = delta.years * 12 + delta.months + (1 if delta.days > 0 else 0)
                raise UserError(
                    f"GTIN {rec.gtin_13} cannot be returned to pool yet.\n\n"
                    f"GS1 requires a 48-month cool-down before a GTIN may be reassigned "
                    f"to a different product. This prevents barcode conflicts in retailer "
                    f"systems and point-of-sale scanners that cache product data.\n\n"
                    f"Eligible to return to pool: {rec.reuse_eligible_date} "
                    f"({months_remaining} month(s) remaining).\n\n"
                    f"To obtain new GTINs now, apply for an additional prefix block at "
                    f"https://www.gs1nz.org/"
                )
            rec.write({
                'status': 'unallocated',
                'current_allocation_id': False,
            })
