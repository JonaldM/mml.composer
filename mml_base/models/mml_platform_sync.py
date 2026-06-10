import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class MmlPlatformSync(models.AbstractModel):
    _name = 'mml.platform.sync'
    _description = 'MML Platform Sync (cron target)'

    @api.model
    def _cron_sync_events(self) -> None:
        """
        Push unsynced mml.event records to the MML Composer platform.
        Runs every 15 minutes. No-op until the platform client is wired.
        """
        from odoo.addons.mml_base.services.platform_client import PlatformClientBase
        client = PlatformClientBase()
        # The cron runs as a non-superuser; mml.event write is restricted to
        # group_system. Use sudo() so the pending fetch and the synced-flag
        # write-back below do not raise AccessError.
        pending = self.env['mml.event'].sudo().search(
            [('synced_to_platform', '=', False)], limit=500
        )
        if not pending:
            return
        success = client.sync_events(pending)
        if success:
            pending.write({'synced_to_platform': True})
            _logger.info('mml.platform.sync: marked %d events as synced', len(pending))
