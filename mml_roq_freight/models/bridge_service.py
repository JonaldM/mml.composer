import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MmlRoqFreightBridge(models.AbstractModel):
    """
    Thin event handler for the ROQ ↔ Freight bridge.
    Delegates all logic to the mml.registry service locator.
    Used as handler_model in mml.event.subscription records.
    """
    _name = 'mml.roq.freight.bridge'
    _description = 'ROQ-Freight Event Bridge'

    @api.model
    def on_shipment_group_confirmed(self, event) -> None:
        """
        Called when a ROQ shipment group is confirmed.
        Creates a freight tender via FreightService.
        """
        if not event.res_id:
            return
        payload = json.loads(event.payload_json or '{}')
        svc = self.env['mml.registry'].service('freight')
        tender_id = svc.create_tender({
            'shipment_group_ref': payload.get('group_ref', ''),
            'shipment_group_id': event.res_id,
        })
        if tender_id:
            # Write back the tender link on the shipment group
            self.env['roq.shipment.group'].browse(event.res_id).write(
                {'freight_tender_id': tender_id}
            )
            _logger.info(
                'ROQ bridge: tender %s created for shipment group %s',
                tender_id, event.res_id,
            )

    @api.model
    def on_freight_booking_confirmed(self, event) -> None:
        """
        Called when a freight booking is confirmed.
        Feeds transit time back to ROQ lead-time stats.
        """
        svc = self.env['mml.registry'].service('roq')
        svc.on_freight_booking_confirmed(event)
