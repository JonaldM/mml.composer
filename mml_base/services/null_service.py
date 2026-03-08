class NullService:
    """
    Returned by mml.registry when the requested service module is not installed.
    All method calls return None silently — callers never need to check installation state.
    """

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def available(self):
        """Stub: NullService is never available — the real module is not installed."""
        return False

    def is_null(self):
        """Returns True — callers can use this to detect a missing service."""
        return True
