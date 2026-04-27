import json
from odoo import api, fields, models


class MmlEvent(models.Model):
    _name = 'mml.event'
    _description = 'MML Event Ledger'
    _rec_name = 'event_type'
    _order = 'timestamp desc'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company
    )
    instance_ref = fields.Char(
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
    dedupe_key = fields.Char(
        index=True,
        help=(
            'Optional idempotency key. If provided to emit_idempotent(), '
            'duplicate emits with the same dedupe_key are no-ops returning '
            'the original event. Indexed; partial UNIQUE constraint where '
            'dedupe_key IS NOT NULL is added by the 19.0.1.1.0 '
            'post-migration script.'
        ),
    )

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

    @api.model
    def emit_idempotent(
        self,
        event_type: str,
        *,
        dedupe_key: str,
        quantity: float = 1.0,
        billable_unit: str = '',
        res_model: str = '',
        res_id: int = 0,
        payload: dict | None = None,
        source_module: str = '',
    ) -> 'MmlEvent':
        """Idempotent variant of :meth:`emit`.

        Returns the existing event if ``dedupe_key`` was already used; else
        creates a new event tagged with the key (which a partial UNIQUE
        index protects against concurrent duplicates).

        Caller MUST supply a non-empty ``dedupe_key``. Use :meth:`emit` for
        events that have no stable idempotency key.

        Recommended pattern for the key::

            f'{source_module}:{res_model}:{res_id}:{logical_op}'

        e.g. ``'mml_freight:freight.booking:42:confirmed'``.
        """
        if not dedupe_key:
            raise ValueError(
                'emit_idempotent requires a non-empty dedupe_key; '
                'use emit() if no key is available'
            )
        existing = self.sudo().search(
            [('dedupe_key', '=', dedupe_key)], limit=1
        )
        if existing:
            return existing
        event = self.create({
            'event_type': event_type,
            'quantity': quantity,
            'billable_unit': billable_unit,
            'res_model': res_model,
            'res_id': res_id,
            'payload_json': json.dumps(payload or {}),
            'source_module': source_module,
            'dedupe_key': dedupe_key,
            'instance_ref': self.env['ir.config_parameter'].sudo().get_param(
                'mml.instance_ref', default=''
            ),
        })
        self.env['mml.event.subscription'].dispatch(event)
        return event
