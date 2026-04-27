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
