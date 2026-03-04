from odoo import fields, models


class MmlBrand(models.Model):
    _name = 'mml.brand'
    _description = 'MML Brand'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('name_company_uniq', 'UNIQUE(name, company_id)', 'Brand name must be unique per company.'),
    ]
