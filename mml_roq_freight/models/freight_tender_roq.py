from odoo import fields, models


class FreightTenderROQ(models.Model):
    _inherit = 'freight.tender'

    shipment_group_id = fields.Many2one(
        'roq.shipment.group',
        string='ROQ Shipment Group',
        ondelete='set null',
        readonly=True,
        help='ROQ shipment group that originated this tender.',
    )
