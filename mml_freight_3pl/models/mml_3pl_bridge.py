import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class Mml3plBridge(models.AbstractModel):
    """
    Thin event handler for the Freight ↔ 3PL bridge.
    Delegates all logic to the mml.registry service locator.
    Used as handler_model in mml.event.subscription records.
    """
    _name = 'mml.3pl.bridge'
    _description = 'Freight-3PL Event Bridge'

    @api.model
    def on_freight_booking_confirmed(self, event) -> None:
        """
        Queue a 3PL inward order for each purchase order linked to the confirmed booking.
        freight.booking.po_ids is Many2many — one inward order message per PO.
        """
        if not event.res_id:
            return

        booking = self.env['freight.booking'].browse(event.res_id)
        if not booking.exists():
            return
        if not booking.po_ids:
            return

        svc = self.env['mml.registry'].service('3pl')
        for po in booking.po_ids:
            msg_id = svc.queue_inward_order(po.id)
            if msg_id:
                _logger.info(
                    '3PL bridge: queued inward order for PO id=%s, msg_id=%s', po.id, msg_id
                )
                self.env['mml.event'].emit(
                    '3pl.inbound.queued',
                    quantity=1,
                    billable_unit='3pl_receipt',
                    res_model='purchase.order',
                    res_id=po.id,
                    source_module='mml_freight_3pl',
                )
            else:
                _logger.warning(
                    '3PL bridge: queue_inward_order returned no message ID for PO id=%s — '
                    'billing event NOT emitted', po.id,
                )
