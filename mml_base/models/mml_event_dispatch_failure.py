"""mml.event.dispatch.failure — log of handler invocations isolated by savepoint.

When mml.event.subscription.dispatch() invokes a subscribed handler inside a
Postgres SAVEPOINT and the handler raises, the savepoint is rolled back and a
record is written to this model. The producing module's mml.event row
(created in the surrounding transaction) is NOT rolled back — only the failed
handler's effects are. Dispatch then continues with the next subscriber.

Records here are read-only for end users and full-CRUD for system admins; they
are intended for triage of cross-module failures and offline retry.
"""
from odoo import fields, models


class MmlEventDispatchFailure(models.Model):
    _name = 'mml.event.dispatch.failure'
    _description = 'Failed event-handler invocation (savepoint-isolated)'
    _order = 'create_date desc'

    event_id = fields.Many2one(
        'mml.event',
        required=True,
        ondelete='cascade',
        index=True,
        help='Event whose dispatch raised in a handler.',
    )
    subscription_id = fields.Many2one(
        'mml.event.subscription',
        required=True,
        ondelete='cascade',
        help='Subscription whose handler raised. Cascades on uninstall.',
    )
    handler_model = fields.Char(
        required=True,
        help='Odoo model name of the handler that raised.',
    )
    handler_method = fields.Char(
        required=True,
        help='Method name on handler_model that raised. Always matches ^_on_[a-z_]+$.',
    )
    error_class = fields.Char(
        help='Class name of the exception raised by the handler.',
    )
    error_message = fields.Text(
        help='str() of the exception raised by the handler.',
    )
    traceback = fields.Text(
        help='Full traceback for offline debugging.',
    )
    create_date = fields.Datetime(readonly=True)
    resolved = fields.Boolean(
        default=False,
        index=True,
        help='Set to True once the failure has been triaged or replayed.',
    )
    resolved_at = fields.Datetime(
        help='When the failure was marked resolved.',
    )
    resolved_by = fields.Many2one(
        'res.users',
        help='User who marked the failure resolved.',
    )

    def write(self, vals):
        """Stamp resolved_at / resolved_by when a row transitions to resolved.

        Only records that are newly resolved (False -> True in this write) are
        stamped, and only when the caller has not supplied those fields itself.
        Records that were already resolved keep their original stamp, and a
        write that sets resolved=False does not stamp anything.
        """
        if vals.get('resolved') and 'resolved_at' not in vals and 'resolved_by' not in vals:
            newly_resolved = self.filtered(lambda r: not r.resolved)
            res = super().write(vals)
            if newly_resolved:
                newly_resolved.write({
                    'resolved_at': fields.Datetime.now(),
                    'resolved_by': self.env.uid,
                })
            return res
        return super().write(vals)
