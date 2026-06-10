def _register_bridge_subscriptions(env):
    """Register all mml_roq_freight event subscriptions.

    Extracted so both post_init_hook and the upgrade migration can call the
    same logic.  mml.event.subscription.register() is idempotent — calling it
    when a row already exists is a no-op, so this function is safe to run
    repeatedly.

    Args:
        env: Odoo Environment instance (any cursor/user is acceptable; the
            subscription records are company-independent).
    """
    # When a ROQ shipment group is confirmed → create a freight tender
    env['mml.event.subscription'].register(
        event_type='roq.shipment_group.confirmed',
        handler_model='mml.roq.freight.bridge',
        handler_method='_on_shipment_group_confirmed',
        module='mml_roq_freight',
    )
    # When a freight booking is confirmed → update ROQ lead-time feedback
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='mml.roq.freight.bridge',
        handler_method='_on_freight_booking_confirmed',
        module='mml_roq_freight',
    )


def post_init_hook(env):
    """Register bridge event subscriptions on install."""
    _register_bridge_subscriptions(env)


def uninstall_hook(env):
    """Remove all bridge subscriptions on uninstall."""
    env['mml.event.subscription'].deregister_module('mml_roq_freight')
