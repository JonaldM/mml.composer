"""
End-to-end integration test: ROQ shipment group -> Freight tender -> 3PL message.

Verifies the full cross-module event chain:
  1. roq.shipment.group confirmed event fires
  2. mml_roq_freight bridge creates a freight.tender linked to the shipment group
  3. A freight.booking is confirmed on that tender
  4. mml_freight_3pl bridge queues a 3pl.message (inward_order) for that booking

IMPORTANT: This test requires a live Odoo database with mml_roq_freight,
mml_freight_3pl, and mml_freight installed.

Run with:
  python odoo-bin --test-enable -u mml_roq_freight,mml_freight_3pl \\
      -d <db> --test-tags mml_roq_freight:TestROQFreight3PLE2E --stop-after-init

DO NOT run with plain pytest -- it will be skipped automatically.
"""
import unittest
from odoo.tests.common import TransactionCase

_ODOO_AVAILABLE = hasattr(TransactionCase, "env")


@unittest.skipUnless(_ODOO_AVAILABLE, "Requires Odoo runtime -- run with odoo-bin --test-enable")
class TestROQFreight3PLE2E(TransactionCase):
    """
    End-to-end integration test for the ROQ -> Freight -> 3PL event chain.

    Requires mml_roq_freight, mml_freight_3pl, and mml_freight to be installed.
    Each test skips gracefully if a required module is absent.
    """

    def setUp(self):
        super().setUp()
        self._check_modules_installed(
            "mml_roq_freight", "mml_freight_3pl", "mml_freight"
        )

    def _check_modules_installed(self, *module_names):
        """Skip test if any required module is not installed."""
        for module_name in module_names:
            mod = self.env["ir.module.module"].search(
                [("name", "=", module_name), ("state", "=", "installed")]
            )
            if not mod:
                self.skipTest(
                    "%s is not installed in this database" % module_name
                )

    def _make_shipment_group(self):
        """
        Create a minimal roq.shipment.group in draft state.

        Adjust required field values to match your actual model constraints.
        Check roq_shipment_group.py for required fields before running.
        """
        return self.env["roq.shipment.group"].create({
            "name": "E2E-TEST-SG-001",
            "state": "draft",
        })

    def test_confirmed_shipment_group_creates_freight_tender(self):
        """
        Confirming a roq.shipment.group must create a freight.tender
        linked back via freight_tender_id.

        Failure here means the mml_roq_freight bridge event subscription
        is not registered or FreightService.create_tender() is returning None.
        """
        sg = self._make_shipment_group()
        self.assertFalse(
            sg.freight_tender_id,
            "No freight tender should exist before shipment group is confirmed",
        )

        sg.action_confirm()  # fires roq.shipment_group.confirmed event

        sg.invalidate_recordset()
        self.assertTrue(
            sg.freight_tender_id,
            "freight_tender_id must be set after shipment group confirmation -- "
            "check mml_roq_freight bridge event subscription is registered",
        )
        tender = sg.freight_tender_id
        self.assertEqual(
            tender.shipment_group_id.id,
            sg.id,
            "freight.tender must link back to the shipment group via shipment_group_id",
        )

    def test_confirmed_freight_booking_queues_3pl_message(self):
        """
        Confirming a freight.booking must cause the mml_freight_3pl bridge
        to queue a 3pl.message of type 'inward_order'.

        Failure here means the mml_freight_3pl bridge event subscription
        is not registered or the 3pl.service is not available (NullService).
        """
        sg = self._make_shipment_group()
        sg.action_confirm()
        sg.invalidate_recordset()
        tender = sg.freight_tender_id
        self.assertTrue(
            tender,
            "Prerequisite failed: shipment group confirmation must produce a freight tender",
        )

        booking = self.env["freight.booking"].create({
            "tender_id": tender.id,
            "state": "draft",
        })

        messages_before = self.env["3pl.message"].search_count([
            ("booking_id", "=", booking.id),
            ("message_type", "=", "inward_order"),
        ])
        self.assertEqual(messages_before, 0, "No 3PL messages should exist before booking confirmation")

        booking.action_confirm()  # fires freight.booking.confirmed event

        messages_after = self.env["3pl.message"].search_count([
            ("booking_id", "=", booking.id),
            ("message_type", "=", "inward_order"),
        ])
        self.assertGreater(
            messages_after,
            0,
            "Confirming freight.booking must queue a 3pl.message of type 'inward_order' -- "
            "check mml_freight_3pl bridge event subscription and 3pl.service registration",
        )
