def post_init_hook(env):
    """Register bridge event subscription on install."""
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='mml.3pl.bridge',
        handler_method='on_freight_booking_confirmed',
        module='mml_freight_3pl',
    )


def uninstall_hook(env):
    """Remove bridge subscription on uninstall."""
    env['mml.event.subscription'].deregister_module('mml_freight_3pl')
