import logging

_logger = logging.getLogger(__name__)


class PlatformClientBase:
    """
    No-op stub for the MML Composer platform client.

    When mml.composer (https://github.com/JonaldM/mml.composer) is live,
    replace this with ComposerAPIClient that POSTs events and GETs license
    grants. No other files need to change — the cron target and callers
    reference this class by name via the registry.
    """

    def sync_events(self, events) -> bool:
        """Push unsynced mml.event records to the platform. Returns True on success."""
        _logger.debug(
            'PlatformClientBase.sync_events() — stub no-op, %d events not transmitted',
            len(events) if events else 0,
        )
        return False

    def validate_license(self, license_key: str) -> dict:
        """Validate license key against the platform. Returns grant dict."""
        return {'valid': True, 'tier': 'internal', 'modules': ['*']}
