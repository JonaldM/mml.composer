from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # GS1 policy has, since 2019, been NOT to reuse GTINs at all. Returning a
    # discontinued GTIN to the pool for reallocation is therefore disabled by
    # default and only happens if MML explicitly opts in here. Even when enabled,
    # the 48-month cool-down (from the discontinue/last-supply date) still applies.
    allow_gtin_reuse = fields.Boolean(
        string='Allow GTIN reuse',
        default=False,
        help='When enabled, a discontinued GTIN may be returned to the '
             'unallocated pool and reassigned to a different product after the '
             '48-month cool-down. Disabled by default: GS1 best practice is to '
             'never reuse a GTIN. Leave off unless you have a deliberate reason.',
    )
