def _register_bridge_subscriptions(env):
    """Register all mml_freight_3pl event subscriptions.

    Extracted so both post_init_hook and the upgrade migration can call the
    same logic.  mml.event.subscription.register() is idempotent — calling it
    when a row already exists is a no-op, so this function is safe to run
    repeatedly.

    Args:
        env: Odoo Environment instance (any cursor/user is acceptable; the
            subscription records are company-independent).
    """
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='mml.3pl.bridge',
        handler_method='_on_freight_booking_confirmed',
        module='mml_freight_3pl',
    )


def post_init_hook(env):
    """Register bridge event subscription on install."""
    _register_bridge_subscriptions(env)


def uninstall_hook(env):
    """Remove bridge subscription on uninstall."""
    env['mml.event.subscription'].deregister_module('mml_freight_3pl')
