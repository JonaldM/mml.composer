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
        pending = self.env['mml.event'].search(
            [('synced_to_platform', '=', False)], limit=500
        )
        if not pending:
            return
        success = client.sync_events(pending)
        if success:
            pending.write({'synced_to_platform': True})
            _logger.info('mml.platform.sync: marked %d events as synced', len(pending))
