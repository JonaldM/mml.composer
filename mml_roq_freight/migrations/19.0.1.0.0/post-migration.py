"""Post-migration for mml_roq_freight 19.0.1.0.0.

Ensures the bridge event subscriptions for 'roq.shipment_group.confirmed'
and 'freight.booking.confirmed' exist in the database.

Why this is needed:
    post_init_hook only runs on fresh module install (-i), NOT on upgrade (-u).
    When upgrading an existing Odoo instance to v19, the subscriptions created
    by the original post_init_hook call are normally present in the DB.
    However, if the DB was migrated without retaining the subscription records,
    or if the module was installed via a path that skipped post_init_hook,
    this migration re-registers them idempotently.

    mml.event.subscription.register() is idempotent: it is a no-op if the
    subscription row already exists, so running it here is safe even when the
    records are present.

Manual verification:
    SELECT event_type, handler_model, handler_method
    FROM mml_event_subscription
    WHERE module = 'mml_roq_freight';
    -- Expected: two rows — roq.shipment_group.confirmed and freight.booking.confirmed
"""
import logging

_logger = logging.getLogger(__name__)

_SUBSCRIPTIONS = [
    {
        'event_type': 'roq.shipment_group.confirmed',
        'handler_model': 'mml.roq.freight.bridge',
        'handler_method': '_on_shipment_group_confirmed',
    },
    {
        'event_type': 'freight.booking.confirmed',
        'handler_model': 'mml.roq.freight.bridge',
        'handler_method': '_on_freight_booking_confirmed',
    },
]


def migrate(cr, version):
    """Re-register mml_roq_freight event subscriptions.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. None/empty means
            fresh install — post_init_hook already handles that case, but
            calling register() again is harmless (idempotent).
    """
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    sub_model = env['mml.event.subscription']
    for sub in _SUBSCRIPTIONS:
        sub_model.register(
            event_type=sub['event_type'],
            handler_model=sub['handler_model'],
            handler_method=sub['handler_method'],
            module='mml_roq_freight',
        )
    _logger.info(
        'mml_roq_freight 19.0.1.0.0: ensured %d event subscription(s) are registered',
        len(_SUBSCRIPTIONS),
    )
