from odoo import fields, models


class RoqShipmentGroupFreight(models.Model):
    _inherit = 'roq.shipment.group'

    freight_tender_id = fields.Many2one(
        'freight.tender',
        string='Freight Tender',
        ondelete='set null',
        readonly=True,
        help='Freight tender created when this shipment group was confirmed.',
    )
