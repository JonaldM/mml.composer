class NullService:
    """
    Returned by mml.registry when the requested service module is not installed.
    All method calls return None silently — callers never need to check installation state.
    """

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def get_booking_status(self, shipment_group_id):
        """Stub: mml_freight not installed — no booking status available."""
        return None
