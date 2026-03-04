import json
from odoo import api, fields, models


class MmlEvent(models.Model):
    _name = 'mml.event'
    _description = 'MML Event Ledger'
    _order = 'timestamp desc'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company
    )
    instance_ref = fields.Char(
        store=True,
        help='Identifies the Odoo instance for multi-instance billing',
    )
    event_type = fields.Char(required=True, index=True)
    source_module = fields.Char()
    res_model = fields.Char()
    res_id = fields.Integer()
    payload_json = fields.Text()
    quantity = fields.Float(default=1.0)
    billable_unit = fields.Char()
    synced_to_platform = fields.Boolean(default=False, index=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def emit(
        self,
        event_type: str,
        *,
        quantity: float = 1.0,
        billable_unit: str = '',
        res_model: str = '',
        res_id: int = 0,
        payload: dict | None = None,
        source_module: str = '',
    ) -> 'MmlEvent':
        """Create and persist a billable event. Call from any mml_* module."""
        event = self.create({
            'event_type': event_type,
            'quantity': quantity,
            'billable_unit': billable_unit,
            'res_model': res_model,
            'res_id': res_id,
            'payload_json': json.dumps(payload or {}),
            'source_module': source_module,
            'instance_ref': self.env['ir.config_parameter'].sudo().get_param('mml.instance_ref', default=''),
        })
        self.env['mml.event.subscription'].dispatch(event)
        return event
