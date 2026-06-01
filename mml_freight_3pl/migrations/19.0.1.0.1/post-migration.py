"""Post-migration for mml_freight_3pl 19.0.1.0.1.

Ensures the bridge event subscription for 'freight.booking.confirmed' is
registered in mml.event.subscription after an upgrade.

Why this is needed:
    post_init_hook only runs on fresh module install (-i), NOT on upgrade (-u).
    When upgrading an existing Odoo instance, the subscription record created
    by the original post_init_hook call may be absent or stale, leaving the
    bridge event handler silently dead — freight bookings confirmed after the
    upgrade would not trigger the 3PL inward-order queue.

    The folder is versioned 19.0.1.0.1 (one patch above the prior installed
    19.0.1.0.0) so Odoo's migration manager actually runs it on -u; a folder
    equal to the installed version is skipped.

    _register_bridge_subscriptions() is idempotent: mml.event.subscription
    .register() is a no-op if the row already exists, so running this
    migration when the subscription is present is harmless.

Manual verification:
    SELECT event_type, handler_model, handler_method
    FROM mml_event_subscription
    WHERE module = 'mml_freight_3pl';
    -- Expected: one row — freight.booking.confirmed / mml.3pl.bridge /
    --           _on_freight_booking_confirmed
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Re-register mml_freight_3pl event subscription in mml.event.subscription.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. None/empty means
            fresh install -- post_init_hook already handles that case, but
            calling register() again is harmless (idempotent).
    """
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mml_freight_3pl.hooks import _register_bridge_subscriptions

    env = api.Environment(cr, SUPERUSER_ID, {})
    _register_bridge_subscriptions(env)
    _logger.info(
        'mml_freight_3pl 19.0.1.0.1: re-registered bridge event subscription(s)'
    )
