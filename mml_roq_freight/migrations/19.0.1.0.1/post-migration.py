"""Post-migration for mml_roq_freight 19.0.1.0.1.

Ensures both bridge event subscriptions ('roq.shipment_group.confirmed' and
'freight.booking.confirmed') are registered in mml.event.subscription after
an upgrade.

Why this is needed:
    post_init_hook only runs on fresh module install (-i), NOT on upgrade (-u).
    When upgrading an existing Odoo instance, the subscription records created
    by the original post_init_hook call may be absent or stale, leaving both
    bridge event handlers silently dead — ROQ shipment-group confirmations
    would not create freight tenders, and freight-booking confirmations would
    not feed lead-time data back to ROQ.

    The folder is versioned 19.0.1.0.1 (one patch above the prior installed
    19.0.1.0.0) so Odoo's migration manager actually runs it on -u; a folder
    equal to the installed version is skipped.  The pre-existing
    migrations/19.0.1.0.0/post-migration.py was also intended to handle this
    but was at the same version as the installed module and therefore never
    executed.

    _register_bridge_subscriptions() is idempotent: mml.event.subscription
    .register() is a no-op if the row already exists, so running this
    migration when the subscriptions are already present is harmless.

Manual verification:
    SELECT event_type, handler_model, handler_method
    FROM mml_event_subscription
    WHERE module = 'mml_roq_freight';
    -- Expected: two rows:
    --   roq.shipment_group.confirmed / mml.roq.freight.bridge / _on_shipment_group_confirmed
    --   freight.booking.confirmed   / mml.roq.freight.bridge / _on_freight_booking_confirmed
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Re-register mml_roq_freight event subscriptions in mml.event.subscription.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. None/empty means
            fresh install -- post_init_hook already handles that case, but
            calling register() again is harmless (idempotent).
    """
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mml_roq_freight.hooks import _register_bridge_subscriptions

    env = api.Environment(cr, SUPERUSER_ID, {})
    _register_bridge_subscriptions(env)
    _logger.info(
        'mml_roq_freight 19.0.1.0.1: re-registered bridge event subscription(s)'
    )
