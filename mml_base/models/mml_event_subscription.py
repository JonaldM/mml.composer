import logging
import re
import traceback as _traceback

try:
    from psycopg2 import OperationalError
except ImportError:  # pure-python test harness: psycopg2 absent or stubbed flat
    class OperationalError(Exception):
        """Stand-in when psycopg2 isn't importable (stubbed test env)."""

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Handler methods must look like ``_on_freight_booking_confirmed``. Digits are
# allowed (the event namespace includes e.g. ``3pl.*``, so handlers like
# ``_on_3pl_inbound_queued`` are legitimate); the leading ``_on_`` keeps the
# allowlist tight against arbitrary getattr dispatch.
_HANDLER_METHOD_RE = re.compile(r'^_on_[a-z0-9_]+$')


def _is_valid_handler_method(name: str) -> bool:
    """Return True if ``name`` is a safe handler method name.

    The dispatch loop calls ``getattr(model, sub.handler_method)(event)``; permitting
    arbitrary names would let a malicious or buggy subscription invoke any attribute on
    the handler model. Constraining to ``^_on_[a-z_]+$`` enforces the convention that
    event handlers are private hooks named like ``_on_freight_booking_confirmed``.
    """
    if not isinstance(name, str):
        return False
    return bool(_HANDLER_METHOD_RE.match(name))


class MmlEventSubscription(models.Model):
    _name = 'mml.event.subscription'
    _description = 'MML Event Subscription'
    _rec_name = 'event_type'

    _unique_subscription = models.Constraint(
        'UNIQUE(event_type, handler_model, handler_method, module)',
        'A subscription for this event_type/handler_model/handler_method/module combination already exists.',
    )

    event_type = fields.Char(required=True, index=True)
    handler_model = fields.Char(required=True)
    handler_method = fields.Char(required=True, size=128)
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
            ('module', '=', module),
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
        """Find all subscriptions for event.event_type and call their handlers.

        Each handler is invoked inside its own Postgres SAVEPOINT
        (``self.env.cr.savepoint()``). If a handler raises:

        * the savepoint is rolled back, undoing only that handler's DB writes
        * the failure is recorded in ``mml.event.dispatch.failure`` for triage
        * dispatch continues with the next subscriber

        The producer's ``mml.event.create()`` and any other work in the
        surrounding transaction are unaffected. This means a broken handler
        in module B no longer rolls back the billable event emitted by
        module A.

        Handler-method names must match ``^_on_[a-z_]+$``; subscriptions that
        violate this are logged and skipped without invocation.
        """
        subscriptions = self.search([('event_type', '=', event.event_type)])
        for sub in subscriptions:
            if not _is_valid_handler_method(sub.handler_method):
                _logger.error(
                    'mml.event: rejected dispatch to %s.%s — method name does not match '
                    'safe pattern ^_on_[a-z_]+$ (subscription id=%s)',
                    sub.handler_model, sub.handler_method, sub.id,
                )
                continue
            self._dispatch_one(event, sub)

    def _dispatch_one(self, event, sub) -> None:
        """Invoke a single subscriber inside its own savepoint.

        Failures are isolated and logged to ``mml.event.dispatch.failure``;
        they never propagate to the caller of :meth:`dispatch`.
        """
        try:
            with self.env.cr.savepoint():
                model = self.env.get(sub.handler_model)
                if model is None:
                    # Stale subscription (module uninstalled without its hook,
                    # or model renamed). Log at ERROR so the lost delivery is
                    # visible for triage rather than vanishing silently.
                    _logger.error(
                        'mml.event: subscription id=%s targets unknown model '
                        '%r (handler %s); event %s NOT delivered. Clean up or '
                        're-register this subscription.',
                        sub.id, sub.handler_model, sub.handler_method,
                        event.event_type,
                    )
                    return
                getattr(model, sub.handler_method)(event)
        except OperationalError:
            # Serialization failure / deadlock (pgcode 40001 / 40P01) is
            # transient and has already poisoned the cursor — re-raise so
            # Odoo's request layer retries the whole transaction instead of
            # recording a misleading permanent failure row and continuing on a
            # dead cursor.
            raise
        except Exception as exc:  # noqa: BLE001 — by design: handler isolation
            # The savepoint context manager has already rolled back the
            # handler's DB writes by the time we get here. Now persist a
            # triage record so admins can replay/debug offline.
            self._log_dispatch_failure(event, sub, exc)

    def _log_dispatch_failure(self, event, sub, exc: BaseException) -> None:
        """Record an isolated handler failure in mml.event.dispatch.failure.

        We log at ERROR with full context, then create a row via sudo() so
        the writer's group does not need full CRUD on the failure model.
        """
        tb_text = _traceback.format_exc()
        _logger.error(
            'mml.event: handler %s.%s raised %s for event %s (id=%s, sub=%s); '
            'savepoint rolled back, dispatch continues. Logged to '
            'mml.event.dispatch.failure for triage.',
            sub.handler_model,
            sub.handler_method,
            type(exc).__name__,
            event.event_type,
            event.id,
            sub.id,
        )
        try:
            self.env['mml.event.dispatch.failure'].sudo().create({
                'event_id': event.id,
                'subscription_id': sub.id,
                'handler_model': sub.handler_model,
                'handler_method': sub.handler_method,
                'error_class': type(exc).__name__,
                'error_message': str(exc),
                'traceback': tb_text,
            })
        except Exception:  # noqa: BLE001 — never let logging crash dispatch
            _logger.exception(
                'mml.event: failed to persist dispatch failure record for '
                '%s.%s (event id=%s); original handler error: %s',
                sub.handler_model,
                sub.handler_method,
                event.id,
                exc,
            )
