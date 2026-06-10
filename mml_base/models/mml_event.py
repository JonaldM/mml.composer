import json

try:
    from psycopg2.errors import UniqueViolation
except ImportError:  # pure-python test harness: psycopg2 absent or stubbed flat
    class UniqueViolation(Exception):
        """Stand-in when psycopg2 isn't importable (stubbed test env)."""

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
            'the original event. A partial UNIQUE index where dedupe_key '
            'IS NOT NULL enforces this at the DB level; it is created by '
            'init() (so it exists on a fresh install) and mirrored by the '
            '19.0.1.1.0 post-migration (for already-upgraded DBs).'
        ),
    )

    def init(self):
        """Create the partial UNIQUE index that makes emit_idempotent safe.

        Defined here — not only in a migration — because Odoo never runs
        ``migrations/`` scripts on a *fresh* install (``-i``), which is exactly
        MML's go-live path (installing into the migrated 15->19 DB). Without
        this, ``index=True`` on ``dedupe_key`` yields only a plain non-unique
        index and concurrent ``emit_idempotent`` calls under multiple workers
        could both insert — duplicate billable events and double dispatch.

        ``CREATE ... IF NOT EXISTS`` with the same name the post-migration uses
        keeps this a no-op on DBs that already have the index. NULL dedupe_key
        rows (plain ``emit()``) are exempt from the partial index.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS mml_event_dedupe_key_uniq
            ON mml_event (dedupe_key)
            WHERE dedupe_key IS NOT NULL
        """)

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
        """Create and persist a billable event. Call from any mml_* module.

        The ledger is platform telemetry written on behalf of whatever business
        action fired it, so the create is done with ``sudo()``: the ACL grants
        normal users only read on ``mml.event`` (create is system-only), and a
        plain create would raise AccessError for an ordinary internal user
        clicking e.g. "Confirm Booking". Values are all server-built here.
        """
        event = self.sudo().create({
            'event_type': event_type,
            'quantity': quantity,
            'billable_unit': billable_unit,
            'res_model': res_model,
            'res_id': res_id,
            'payload_json': json.dumps(payload or {}, default=str),
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
        try:
            with self.env.cr.savepoint():
                event = self.sudo().create({
                    'event_type': event_type,
                    'quantity': quantity,
                    'billable_unit': billable_unit,
                    'res_model': res_model,
                    'res_id': res_id,
                    'payload_json': json.dumps(payload or {}, default=str),
                    'source_module': source_module,
                    'dedupe_key': dedupe_key,
                    'instance_ref': self.env['ir.config_parameter'].sudo().get_param(
                        'mml.instance_ref', default=''
                    ),
                })
        except UniqueViolation:
            # A concurrent worker emitted the same dedupe_key first; the partial
            # UNIQUE index rejected our insert. Return the winner rather than
            # letting the IntegrityError abort the caller's transaction (the
            # whole point of idempotency is that the second caller succeeds).
            # The savepoint has rolled back our failed insert.
            return self.sudo().search(
                [('dedupe_key', '=', dedupe_key)], limit=1
            )
        self.env['mml.event.subscription'].dispatch(event)
        return event
