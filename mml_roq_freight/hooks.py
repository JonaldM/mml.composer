def post_init_hook(env):
    """Register bridge event subscriptions on install."""
    # When a ROQ shipment group is confirmed → create a freight tender
    env['mml.event.subscription'].register(
        event_type='roq.shipment_group.confirmed',
        handler_model='mml.roq.freight.bridge',
        handler_method='on_shipment_group_confirmed',
        module='mml_roq_freight',
    )
    # When a freight booking is confirmed → update ROQ lead-time feedback
    env['mml.event.subscription'].register(
        event_type='freight.booking.confirmed',
        handler_model='mml.roq.freight.bridge',
        handler_method='on_freight_booking_confirmed',
        module='mml_roq_freight',
    )


def uninstall_hook(env):
    """Remove all bridge subscriptions on uninstall."""
    env['mml.event.subscription'].deregister_module('mml_roq_freight')
