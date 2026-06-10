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
    def _on_freight_booking_confirmed(self, event) -> None:
        """
        Queue a 3PL inward order for each purchase order linked to the confirmed booking.
        freight.booking.po_ids is Many2many — one inward order message per PO.
        """
        if not event.res_id:
            return

        # No broad try/except here: mml.event.subscription._dispatch_one wraps each
        # handler in its own Postgres savepoint and records any exception in the
        # mml.event.dispatch.failure ledger. Swallowing the failure here would hide
        # it from that ledger, so let it propagate to the dispatcher's isolation.
        booking = self.env['freight.booking'].browse(event.res_id)
        if not booking.exists():
            return
        if not booking.po_ids:
            return

        svc = self.env['mml.registry'].service('3pl')
        has_message_model = '3pl.message' in self.env
        for po in booking.po_ids:
            # Dedup guard mirroring the direct path in
            # mml_freight.freight_booking._queue_3pl_inward_order(): that path
            # also queues a create-type inward_order per PO on action_confirm().
            # If one already exists for this PO, skip so the bridge does not
            # create a second 3pl.message for the same inbound.
            if has_message_model:
                existing = self.env['3pl.message'].search([
                    ('ref_model', '=', 'purchase.order'),
                    ('ref_id', '=', po.id),
                    ('document_type', '=', 'inward_order'),
                    ('action', '=', 'create'),
                ], limit=1)
                if existing:
                    _logger.info(
                        '3PL bridge: inward_order already queued for PO id=%s '
                        '(msg %s) — skipping', po.id, existing.id,
                    )
                    continue
            msg_id = svc.queue_inward_order(po.id)
            if msg_id:
                _logger.info(
                    '3PL bridge: queued inward order for PO id=%s, msg_id=%s', po.id, msg_id
                )
                # Idempotent emit: this billable meter event may fire more
                # than once if the freight.booking.confirmed event is
                # replayed (dispatch-failure retry, network re-delivery).
                # A stable (booking, PO) key prevents double-billing.
                self.env['mml.event'].emit_idempotent(
                    '3pl.inbound.queued',
                    dedupe_key='mml_freight_3pl:freight.booking:%s:po:%s:queued' % (
                        booking.id, po.id,
                    ),
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
