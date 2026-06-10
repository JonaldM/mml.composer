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
    def _on_shipment_group_confirmed(self, event) -> None:
        """
        Called when a ROQ shipment group is confirmed.
        Creates a freight tender via FreightService.
        """
        if not event.res_id:
            return
        sg = self.env['roq.shipment.group'].browse(event.res_id)
        if not sg.exists():
            return
        # Replay idempotency: this event can be re-delivered (dispatch-failure
        # retry, network re-delivery). If a freight tender is already linked,
        # do not create a second one.
        if sg.freight_tender_id:
            _logger.info(
                'ROQ bridge: shipment group %s already has freight tender %s — '
                'skipping create', event.res_id, sg.freight_tender_id.id,
            )
            return
        payload = json.loads(event.payload_json or '{}')
        # Multi-company: stamp the tender with the shipment group's own company
        # (derived from its consolidated POs) rather than letting freight.tender
        # default company_id to the dispatcher's active company.
        vals = {
            'shipment_group_ref': payload.get('group_ref', ''),
            'shipment_group_id': event.res_id,
        }
        sg_po = sg.po_ids[:1]
        if sg_po and sg_po.company_id:
            vals['company_id'] = sg_po.company_id.id
        svc = self.env['mml.registry'].service('freight')
        try:
            tender_id = svc.create_tender(vals)
            if tender_id:
                # Write back the tender link inside the same try so that a
                # write failure rolls back together with the create rather than
                # leaving an orphaned tender with no link on the shipment group.
                sg.write({'freight_tender_id': tender_id})
                _logger.info(
                    'ROQ bridge: tender %s created for shipment group %s',
                    tender_id, event.res_id,
                )
        except Exception as e:
            _logger.warning(
                'mml_roq_freight bridge: failed to create freight tender for '
                'shipment group %s: %s', event.res_id, e,
            )
            if sg.exists():
                sg.sudo().message_post(
                    body='Failed to create freight tender automatically: %s' % str(e),
                    subtype_xmlid='mail.mt_note',
                )
            return

    @api.model
    def _on_freight_booking_confirmed(self, event) -> None:
        """
        Called when a freight booking is confirmed.
        Feeds transit time back to ROQ lead-time stats.
        """
        if not event.res_id:
            return
        # No broad try/except: mml.event.subscription._dispatch_one runs this handler
        # inside its own savepoint and records any failure in mml.event.dispatch.failure.
        # Swallowing the exception here would hide the failure from that ledger.
        svc = self.env['mml.registry'].service('roq')
        svc.on_freight_booking_confirmed(event)
