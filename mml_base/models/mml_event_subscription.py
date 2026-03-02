import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MmlEventSubscription(models.Model):
    _name = 'mml.event.subscription'
    _description = 'MML Event Subscription'

    event_type = fields.Char(required=True, index=True)
    handler_model = fields.Char(required=True)
    handler_method = fields.Char(required=True)
    module = fields.Char(required=True, index=True)

    @api.model
    def register(
        self,
        event_type: str,
        handler_model: str,
        handler_method: str,
        module: str,
    ) -> None:
        """Register a handler for an event type. Called from post_init_hook. Idempotent."""
        exists = self.search_count([
            ('event_type', '=', event_type),
            ('handler_model', '=', handler_model),
            ('handler_method', '=', handler_method),
        ])
        if not exists:
            self.create({
                'event_type': event_type,
                'handler_model': handler_model,
                'handler_method': handler_method,
                'module': module,
            })

    @api.model
    def deregister_module(self, module: str) -> None:
        """Remove all subscriptions registered by a module. Called from uninstall_hook."""
        self.search([('module', '=', module)]).unlink()

    @api.model
    def dispatch(self, event) -> None:
        """Find all subscriptions for event.event_type and call their handlers."""
        subscriptions = self.search([('event_type', '=', event.event_type)])
        for sub in subscriptions:
            try:
                model = self.env.get(sub.handler_model)
                if model is not None:
                    getattr(model, sub.handler_method)(event)
            except Exception:
                _logger.exception(
                    'Event handler %s.%s failed for event %s (id=%s)',
                    sub.handler_model,
                    sub.handler_method,
                    event.event_type,
                    event.id,
                )
