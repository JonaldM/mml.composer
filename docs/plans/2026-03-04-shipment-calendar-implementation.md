# Shipment Planning Calendar — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a calendar view to `mml_roq_forecast` that shows planned and confirmed shipments by warehouse delivery date, supports drag-and-drop rescheduling with OOS re-check and consolidation suggestions, and includes a warehouse receiving-load coverage map.

**Architecture:** Standard Odoo calendar view on `roq.shipment.group`. No custom OWL. `write()` override detects date changes and triggers recalculation via existing `push_pull.py` service. Coverage map is a separate list view on a new `roq.warehouse.week.load` computed model. Freight status degrades gracefully via `mml.registry.service('freight')`.

**Tech Stack:** Odoo 19, Python, standard Odoo XML views, existing `push_pull.py` + `consolidation_engine.py` services.

**Design doc:** `docs/plans/2026-03-04-shipment-calendar-design.md`

---

## Task 1: Warehouse receiving capacity fields

Add configurable weekly capacity to `stock.warehouse`.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/stock_warehouse_ext.py`
- Test: `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py` (create this file)

**Step 1: Create the test file and write failing tests**

Create `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py`:

```python
from odoo.tests.common import TransactionCase


class TestWarehouseCapacity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse = self.env['stock.warehouse'].create({
            'name': 'Hamilton DC',
            'code': 'HLZ',
        })

    def test_default_capacity_unit_is_cbm(self):
        self.assertEqual(self.warehouse.roq_capacity_unit, 'cbm')

    def test_set_cbm_capacity(self):
        self.warehouse.roq_weekly_capacity_cbm = 120.0
        self.assertEqual(self.warehouse.roq_weekly_capacity_cbm, 120.0)

    def test_set_teu_capacity(self):
        self.warehouse.roq_weekly_capacity_teu = 4.0
        self.warehouse.roq_capacity_unit = 'teu'
        self.assertEqual(self.warehouse.roq_weekly_capacity_teu, 4.0)
        self.assertEqual(self.warehouse.roq_capacity_unit, 'teu')
```

**Step 2: Run tests to confirm they fail**

```
cd roq.model
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestWarehouseCapacity -v
```
Expected: `AttributeError: 'stock.warehouse' has no attribute 'roq_weekly_capacity_cbm'`

**Step 3: Read the existing warehouse extension**

Read `roq.model/mml_roq_forecast/models/stock_warehouse_ext.py` first to understand current fields before adding.

**Step 4: Add capacity fields**

In `stock_warehouse_ext.py`, add to the `StockWarehouseExt` class:

```python
roq_weekly_capacity_cbm = fields.Float(
    string='Weekly Capacity (CBM)',
    default=0.0,
    help='Maximum CBM arriving per week. 0 = no limit configured.',
)
roq_weekly_capacity_teu = fields.Float(
    string='Weekly Capacity (TEU)',
    default=0.0,
    help='Maximum TEU arriving per week. 1 TEU = 1×20GP; 40GP/40HQ = 2 TEU. 0 = no limit.',
)
roq_capacity_unit = fields.Selection(
    selection=[('cbm', 'CBM'), ('teu', 'TEU')],
    string='Capacity Unit',
    default='cbm',
    required=True,
)
```

**Step 5: Run tests to confirm they pass**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestWarehouseCapacity -v
```
Expected: 3 PASS

**Step 6: Commit**

```bash
git add roq.model/mml_roq_forecast/models/stock_warehouse_ext.py \
        roq.model/mml_roq_forecast/tests/test_shipment_calendar.py
git commit -m "feat(roq-calendar): add weekly receiving capacity fields to stock.warehouse"
```

---

## Task 2: Freight status computed fields on `roq.shipment.group`

Add `freight_eta`, `freight_status`, `freight_last_update` via service locator. Degrades gracefully.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_shipment_group.py`
- Test: `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py`

**Step 1: Write failing tests**

Add to `test_shipment_calendar.py`:

```python
from unittest.mock import MagicMock, patch


class TestFreightStatusFields(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group = self.env['roq.shipment.group'].create({
            'origin_port': 'CNSHA',
            'destination_port': 'NZAKL',
            'container_type': '40HQ',
            'target_ship_date': '2026-06-01',
            'target_delivery_date': '2026-07-01',
        })

    def test_freight_fields_empty_when_freight_not_installed(self):
        """NullService returns None — fields stay empty."""
        null_svc = MagicMock()
        null_svc.get_booking_status.return_value = None
        with patch.object(
            self.group.env['mml.registry'], 'service', return_value=null_svc
        ):
            self.group._compute_freight_status()
        self.assertFalse(self.group.freight_eta)
        self.assertFalse(self.group.freight_status)

    def test_freight_fields_populated_when_booking_exists(self):
        """Real FreightService returns booking data."""
        from datetime import datetime
        eta = datetime(2026, 7, 1, 10, 0, 0)
        mock_svc = MagicMock()
        mock_svc.get_booking_status.return_value = {
            'eta': eta,
            'status': 'in_transit',
            'last_update': eta,
        }
        with patch.object(
            self.group.env['mml.registry'], 'service', return_value=mock_svc
        ):
            self.group._compute_freight_status()
        self.assertEqual(self.group.freight_eta, eta)
        self.assertEqual(self.group.freight_status, 'in_transit')
```

**Step 2: Run tests to confirm they fail**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestFreightStatusFields -v
```
Expected: `AttributeError: 'roq.shipment.group' has no attribute 'freight_eta'`

**Step 3: Read `roq_shipment_group.py` lines 1-90**

Understand existing field declarations before adding.

**Step 4: Add freight computed fields**

In `RoqShipmentGroup` class, add after the `lead_time_variance_days` field:

```python
# --- Freight status (populated by mml_freight via service locator) ---
freight_eta = fields.Datetime(
    string='Freight ETA',
    compute='_compute_freight_status',
    store=False,
)
freight_status = fields.Char(
    string='Freight Status',
    compute='_compute_freight_status',
    store=False,
)
freight_last_update = fields.Datetime(
    string='Last Freight Update',
    compute='_compute_freight_status',
    store=False,
)
```

**Step 5: Add the compute method**

Add after the field declarations, before `action_confirm()`:

```python
@api.depends('state')
def _compute_freight_status(self):
    svc = self.env['mml.registry'].service('freight')
    for rec in self:
        result = svc.get_booking_status(rec.id)
        if result:
            rec.freight_eta = result.get('eta')
            rec.freight_status = result.get('status')
            rec.freight_last_update = result.get('last_update')
        else:
            rec.freight_eta = False
            rec.freight_status = False
            rec.freight_last_update = False
```

**Step 6: Add `get_booking_status` stub to NullService in `mml_base`**

Read `mml_base/services/null_service.py` (or wherever NullService is defined). Add:

```python
def get_booking_status(self, shipment_group_id):
    return None
```

**Step 7: Run tests to confirm they pass**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestFreightStatusFields -v
```
Expected: 2 PASS

**Step 8: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_shipment_group.py \
        roq.model/mml_roq_forecast/tests/test_shipment_calendar.py
git commit -m "feat(roq-calendar): add freight status computed fields to roq.shipment.group"
```

---

## Task 3: `write()` override — date-change detection and OOS re-check

When `target_delivery_date` or `target_ship_date` changes on a `draft`/`confirmed` group, run the push/pull OOS re-check silently and post a chatter message.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_shipment_group.py`
- Test: `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py`

**Step 1: Write failing tests**

```python
from datetime import date, timedelta


class TestRescheduleWrite(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group = self.env['roq.shipment.group'].create({
            'origin_port': 'CNSHA',
            'destination_port': 'NZAKL',
            'container_type': '40HQ',
            'target_ship_date': date(2026, 6, 1),
            'target_delivery_date': date(2026, 7, 1),
            'state': 'draft',
        })

    def test_ship_date_shifts_proportionally_when_delivery_changes(self):
        """Shifting delivery by 7 days shifts ship date by 7 days too."""
        original_ship = self.group.target_ship_date
        self.group.write({'target_delivery_date': date(2026, 7, 8)})
        self.assertEqual(
            self.group.target_ship_date,
            original_ship + timedelta(days=7),
        )

    def test_chatter_message_posted_on_date_change(self):
        """A mail.message is posted recording the date change."""
        msg_count_before = len(self.group.message_ids)
        self.group.write({'target_delivery_date': date(2026, 7, 8)})
        self.assertGreater(len(self.group.message_ids), msg_count_before)

    def test_no_chatter_when_non_date_field_changes(self):
        """No date-change message when only notes change."""
        msg_count_before = len(self.group.message_ids)
        self.group.write({'notes': 'updated'})
        self.assertEqual(len(self.group.message_ids), msg_count_before)

    def test_locked_states_ignore_date_shift_logic(self):
        """Tendered/booked groups: write succeeds but no shift logic runs."""
        self.group.state = 'tendered'
        original_ship = self.group.target_ship_date
        # Should not raise; should not shift target_ship_date
        self.group.write({'target_delivery_date': date(2026, 7, 15)})
        self.assertEqual(self.group.target_ship_date, original_ship)
```

**Step 2: Run tests to confirm they fail**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestRescheduleWrite -v
```
Expected: 4 FAIL

**Step 3: Add `write()` override to `RoqShipmentGroup`**

```python
DRAGGABLE_STATES = {'draft', 'confirmed'}

def write(self, vals):
    # Capture old delivery dates before write for draggable groups only
    date_changing = 'target_delivery_date' in vals
    old_dates = {}
    if date_changing:
        for rec in self:
            if rec.state in DRAGGABLE_STATES:
                old_dates[rec.id] = rec.target_delivery_date

    result = super().write(vals)

    if date_changing and old_dates:
        new_delivery = vals['target_delivery_date']
        # new_delivery may be a date string or date object
        if isinstance(new_delivery, str):
            from odoo.fields import Date
            new_delivery = Date.from_string(new_delivery)

        for rec in self:
            if rec.id not in old_dates:
                continue
            old_delivery = old_dates[rec.id]
            if old_delivery == new_delivery:
                continue

            delta = new_delivery - old_delivery

            # Shift ship date by same delta
            if rec.target_ship_date:
                rec.target_ship_date = rec.target_ship_date + delta

            # OOS re-check via push_pull service
            from ..services.push_pull import has_oos_risk
            lines_data = [
                {
                    'projected_inventory_at_delivery': line.oos_risk_flag,
                    'weeks_of_cover_at_delivery': 0,
                }
                for line in rec.line_ids
            ]
            # Re-evaluate oos_risk_flag on each line
            for line in rec.line_ids:
                line.oos_risk_flag = (
                    line.projected_inventory_at_delivery is not None
                    and line.projected_inventory_at_delivery < 0
                )

            # Chatter audit trail
            delta_days = delta.days
            direction = 'pushed out' if delta_days > 0 else 'pulled forward'
            rec.message_post(
                body=(
                    f'Shipment rescheduled: delivery {direction} by '
                    f'{abs(delta_days)} days '
                    f'({old_delivery} → {new_delivery}).'
                ),
                message_type='notification',
            )

    return result
```

> **Note on OOS re-check:** The full push_pull recalculation requires `roq.forecast.line` records (weeks_of_cover_at_delivery). In the initial implementation, `write()` re-evaluates the existing `oos_risk_flag` based on `projected_inventory_at_delivery` already stored on the line. A full re-projection (adjusting for the delta in lead time) is a follow-up enhancement noted at the bottom of this plan.

**Step 4: Run tests to confirm they pass**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestRescheduleWrite -v
```
Expected: 4 PASS

**Step 5: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_shipment_group.py \
        roq.model/mml_roq_forecast/tests/test_shipment_calendar.py
git commit -m "feat(roq-calendar): write() override for date-shift propagation and OOS re-check"
```

---

## Task 4: Consolidation suggestion field + wizard model

After a significant date shift (> N days), surface nearby same-supplier groups as a suggestion. Stored computed field on `roq.shipment.group`. Lightweight TransientModel wizard.

**Files:**
- Modify: `roq.model/mml_roq_forecast/models/roq_shipment_group.py`
- Create: `roq.model/mml_roq_forecast/models/roq_reschedule_wizard.py`
- Test: `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py`

**Step 1: Write failing tests**

```python
class TestConsolidationSuggestion(TransactionCase):

    def setUp(self):
        super().setUp()
        self.group_a = self.env['roq.shipment.group'].create({
            'origin_port': 'CNSHA',
            'destination_port': 'NZAKL',
            'container_type': '40HQ',
            'target_ship_date': '2026-06-01',
            'target_delivery_date': '2026-07-01',
            'state': 'draft',
        })
        self.group_b = self.env['roq.shipment.group'].create({
            'origin_port': 'CNSHA',
            'destination_port': 'NZAKL',
            'container_type': '40HQ',
            'target_ship_date': '2026-06-10',
            'target_delivery_date': '2026-07-10',
            'state': 'draft',
        })

    def test_no_suggestion_when_same_port_but_far_apart(self):
        """Groups 60 days apart — no suggestion."""
        self.assertFalse(self.group_a._find_consolidation_candidates())

    def test_suggestion_when_groups_within_window(self):
        """Move group_a so it's within 21 days of group_b (same origin port)."""
        self.group_a.write({'target_delivery_date': '2026-07-08'})
        candidates = self.group_a._find_consolidation_candidates()
        self.assertIn(self.group_b, candidates)

    def test_no_suggestion_for_different_origin_port(self):
        """Groups near in time but different FOB port — no suggestion."""
        self.group_b.origin_port = 'CNNGB'
        self.group_a.write({'target_delivery_date': '2026-07-08'})
        candidates = self.group_a._find_consolidation_candidates()
        self.assertFalse(candidates)

    def test_no_suggestion_for_locked_states(self):
        """Booked groups are not consolidation candidates."""
        self.group_b.state = 'booked'
        self.group_a.write({'target_delivery_date': '2026-07-08'})
        candidates = self.group_a._find_consolidation_candidates()
        self.assertFalse(candidates)
```

**Step 2: Run tests to confirm they fail**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestConsolidationSuggestion -v
```

**Step 3: Add `_find_consolidation_candidates()` to `RoqShipmentGroup`**

```python
def _find_consolidation_candidates(self):
    """Return nearby draft/confirmed groups from same FOB port within config window."""
    self.ensure_one()
    if self.state not in DRAGGABLE_STATES:
        return self.env['roq.shipment.group']

    window = int(
        self.env['ir.config_parameter'].sudo().get_param(
            'roq.calendar.consolidation_window_days', default=21
        )
    )
    from datetime import timedelta
    date_from = self.target_delivery_date - timedelta(days=window)
    date_to = self.target_delivery_date + timedelta(days=window)

    return self.search([
        ('id', '!=', self.id),
        ('origin_port', '=', self.origin_port),
        ('state', 'in', list(DRAGGABLE_STATES)),
        ('target_delivery_date', '>=', date_from),
        ('target_delivery_date', '<=', date_to),
    ])
```

**Step 4: Run tests to confirm they pass**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestConsolidationSuggestion -v
```
Expected: 4 PASS

**Step 5: Create the wizard model**

Create `roq.model/mml_roq_forecast/models/roq_reschedule_wizard.py`:

```python
from odoo import fields, models


class RoqRescheduleWizard(models.TransientModel):
    """
    Consolidation suggestion wizard.
    Opened after a large date-shift detects nearby same-origin groups.
    """
    _name = 'roq.reschedule.wizard'
    _description = 'Shipment Consolidation Suggestion'

    source_group_id = fields.Many2one(
        'roq.shipment.group',
        string='Moved Shipment',
        readonly=True,
        required=True,
    )
    candidate_group_ids = fields.Many2many(
        'roq.shipment.group',
        string='Nearby Shipments',
        readonly=True,
    )
    summary = fields.Char(
        string='Summary',
        compute='_compute_summary',
    )

    def _compute_summary(self):
        for rec in self:
            names = ', '.join(rec.candidate_group_ids.mapped('name'))
            rec.summary = (
                f'{names} could be consolidated with '
                f'{rec.source_group_id.name} (same origin port, nearby dates).'
            )

    def action_consolidate(self):
        """Run consolidation engine on source + candidates."""
        all_groups = self.source_group_id | self.candidate_group_ids
        # Delegate to consolidation engine service
        svc = self.env['mml.registry'].service('roq_consolidation')
        svc.consolidate(all_groups.ids)
        return {'type': 'ir.actions.act_window_close'}

    def action_dismiss(self):
        return {'type': 'ir.actions.act_window_close'}
```

**Step 6: Wire consolidation check into `write()` override**

In the `write()` override (Task 3), after the chatter message, add:

```python
# Consolidation proximity check for large shifts
threshold = int(
    self.env['ir.config_parameter'].sudo().get_param(
        'roq.calendar.reschedule_threshold_days', default=5
    )
)
if abs(delta.days) > threshold:
    candidates = rec._find_consolidation_candidates()
    if candidates:
        # Store suggestion on record for calendar card badge
        rec.consolidation_suggestion = ', '.join(candidates.mapped('name'))
    else:
        rec.consolidation_suggestion = False
```

Add `consolidation_suggestion` as a stored Char field on `RoqShipmentGroup`:

```python
consolidation_suggestion = fields.Char(
    string='Consolidation Suggestion',
    help='Set when a nearby same-origin group is found after rescheduling.',
)
```

**Step 7: Update `__init__.py` to import the new wizard model**

In `roq.model/mml_roq_forecast/models/__init__.py`, add:
```python
from . import roq_reschedule_wizard
```

**Step 8: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_shipment_group.py \
        roq.model/mml_roq_forecast/models/roq_reschedule_wizard.py \
        roq.model/mml_roq_forecast/models/__init__.py \
        roq.model/mml_roq_forecast/tests/test_shipment_calendar.py
git commit -m "feat(roq-calendar): consolidation suggestion field and reschedule wizard model"
```

---

## Task 5: Warehouse week load model (coverage map data)

Computes arriving CBM/TEU per warehouse per week from `roq.shipment.group` records.

**Files:**
- Create: `roq.model/mml_roq_forecast/models/roq_warehouse_week_load.py`
- Test: `roq.model/mml_roq_forecast/tests/test_shipment_calendar.py`

**Step 1: Write failing tests**

```python
from datetime import date


class TestWarehouseWeekLoad(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.warehouse.roq_weekly_capacity_cbm = 100.0
        self.warehouse.roq_capacity_unit = 'cbm'

        # A group arriving in week 2026-W28 (delivery 2026-07-06)
        self.group = self.env['roq.shipment.group'].create({
            'origin_port': 'CNSHA',
            'destination_port': 'NZAKL',
            'container_type': '40HQ',
            'total_cbm': 60.0,
            'target_ship_date': '2026-06-01',
            'target_delivery_date': '2026-07-06',
            'state': 'confirmed',
            'destination_warehouse_ids': [(4, self.warehouse.id)],
        })

    def test_load_computed_for_warehouse_week(self):
        load = self.env['roq.warehouse.week.load'].get_load(
            self.warehouse.id,
            date(2026, 7, 6),
        )
        self.assertAlmostEqual(load['cbm'], 60.0)

    def test_load_pct_calculated_against_capacity(self):
        load = self.env['roq.warehouse.week.load'].get_load(
            self.warehouse.id,
            date(2026, 7, 6),
        )
        self.assertAlmostEqual(load['pct'], 60.0)  # 60/100 = 60%

    def test_load_status_green_below_70(self):
        load = self.env['roq.warehouse.week.load'].get_load(
            self.warehouse.id,
            date(2026, 7, 6),
        )
        self.assertEqual(load['status'], 'green')

    def test_load_status_amber_70_to_90(self):
        self.group.total_cbm = 80.0
        load = self.env['roq.warehouse.week.load'].get_load(
            self.warehouse.id,
            date(2026, 7, 6),
        )
        self.assertEqual(load['status'], 'amber')

    def test_load_status_red_over_90(self):
        self.group.total_cbm = 95.0
        load = self.env['roq.warehouse.week.load'].get_load(
            self.warehouse.id,
            date(2026, 7, 6),
        )
        self.assertEqual(load['status'], 'red')
```

**Step 2: Run tests to confirm they fail**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestWarehouseWeekLoad -v
```

**Step 3: Create the model**

Create `roq.model/mml_roq_forecast/models/roq_warehouse_week_load.py`:

```python
from datetime import timedelta
from odoo import api, fields, models


CONTAINER_TEU = {
    '20GP': 1.0,
    '40GP': 2.0,
    '40HQ': 2.0,
    'LCL': 0.0,  # LCL excluded from TEU load (weight-based)
}


class RoqWarehouseWeekLoad(models.AbstractModel):
    """
    Utility model for computing warehouse receiving load per week.
    Not a stored model — use get_load() as a service method.
    """
    _name = 'roq.warehouse.week.load'
    _description = 'Warehouse Weekly Receiving Load (computed)'

    @api.model
    def get_load(self, warehouse_id, week_date):
        """
        Return load dict for warehouse_id in the ISO week containing week_date.

        Returns:
            dict with keys: cbm, teu, pct, status ('green'|'amber'|'red'|'none')
        """
        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        week_start = week_date - timedelta(days=week_date.weekday())
        week_end = week_start + timedelta(days=6)

        groups = self.env['roq.shipment.group'].search([
            ('destination_warehouse_ids', 'in', [warehouse_id]),
            ('target_delivery_date', '>=', week_start),
            ('target_delivery_date', '<=', week_end),
            ('state', 'not in', ['cancelled']),
        ])

        total_cbm = sum(g.total_cbm for g in groups)
        total_teu = sum(
            CONTAINER_TEU.get(g.container_type, 0.0) for g in groups
        )

        unit = warehouse.roq_capacity_unit
        capacity = (
            warehouse.roq_weekly_capacity_cbm
            if unit == 'cbm'
            else warehouse.roq_weekly_capacity_teu
        )
        load_value = total_cbm if unit == 'cbm' else total_teu

        if not capacity:
            pct = 0.0
            status = 'none'
        else:
            pct = (load_value / capacity) * 100
            if pct < 70:
                status = 'green'
            elif pct < 90:
                status = 'amber'
            else:
                status = 'red'

        return {
            'cbm': total_cbm,
            'teu': total_teu,
            'pct': pct,
            'status': status,
        }

    @api.model
    def get_rolling_load(self, warehouse_id, weeks=8):
        """
        Return load for a rolling N-week window from today.
        Used to populate the coverage map view.
        """
        from datetime import date
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        return [
            {
                'week': week_start + timedelta(weeks=i),
                **self.get_load(warehouse_id, week_start + timedelta(weeks=i)),
            }
            for i in range(weeks)
        ]
```

**Step 4: Add to `__init__.py`**

```python
from . import roq_warehouse_week_load
```

**Step 5: Run tests to confirm they pass**

```
pytest mml_roq_forecast/tests/test_shipment_calendar.py::TestWarehouseWeekLoad -v
```
Expected: 5 PASS

**Step 6: Commit**

```bash
git add roq.model/mml_roq_forecast/models/roq_warehouse_week_load.py \
        roq.model/mml_roq_forecast/models/__init__.py \
        roq.model/mml_roq_forecast/tests/test_shipment_calendar.py
git commit -m "feat(roq-calendar): roq.warehouse.week.load utility model for coverage map"
```

---

## Task 6: Calendar view XML

Standard Odoo `<calendar>` view on `roq.shipment.group`.

**Files:**
- Create: `roq.model/mml_roq_forecast/views/roq_shipment_calendar_views.xml`

**Step 1: Read the existing shipment group views**

Read `roq.model/mml_roq_forecast/views/roq_shipment_group_views.xml` to understand existing action IDs and colour fields before writing.

**Step 2: Create the calendar view XML**

Create `roq.model/mml_roq_forecast/views/roq_shipment_calendar_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

  <!-- ────────────────────────────────────────────────
       Calendar view — roq.shipment.group
       Date range: target_ship_date → target_delivery_date
       Colour by state
       Draggable: draft, confirmed only
  ──────────────────────────────────────────────── -->
  <record id="roq_shipment_group_calendar_view" model="ir.ui.view">
    <field name="name">roq.shipment.group.calendar</field>
    <field name="model">roq.shipment.group</field>
    <field name="arch" type="xml">
      <calendar
        string="Shipment Calendar"
        date_start="target_ship_date"
        date_stop="target_delivery_date"
        color="state"
        mode="month"
        quick_create="false"
        event_open_popup="true"
      >
        <!-- Fields loaded for each event card -->
        <field name="name"/>
        <field name="state"/>
        <field name="origin_port"/>
        <field name="container_type"/>
        <field name="fill_percentage"/>
        <field name="destination_warehouse_ids"/>
        <field name="freight_eta"/>
        <field name="freight_status"/>
        <field name="oos_risk_flag" invisible="1"/>
        <field name="consolidation_suggestion" invisible="1"/>

        <!-- Popover content -->
        <field name="name"/>
        <field name="destination_warehouse_ids" widget="many2many_tags"/>
        <field name="container_type"/>
        <field name="fill_percentage" string="Fill"/>
        <field name="freight_eta" invisible="not freight_eta"/>
        <field name="freight_status" invisible="not freight_eta"/>
        <field name="consolidation_suggestion"
               invisible="not consolidation_suggestion"
               string="⚠ Consolidation opportunity"/>
      </calendar>
    </field>
  </record>

  <!-- ────────────────────────────────────────────────
       Action — Shipment Calendar
       Includes calendar + list views; defaults to calendar
  ──────────────────────────────────────────────── -->
  <record id="action_roq_shipment_calendar" model="ir.actions.act_window">
    <field name="name">Shipment Calendar</field>
    <field name="res_model">roq.shipment.group</field>
    <field name="view_mode">calendar,list,form</field>
    <field name="view_id" ref="roq_shipment_group_calendar_view"/>
    <field name="context">{
      'search_default_filter_active_states': 1
    }</field>
    <field name="help" type="html">
      <p class="o_view_nocontent_smiling_face">
        No shipments to display.
      </p>
      <p>
        Shipment groups appear here once created from a ROQ run.
        Use month view to plan arrivals; week view for near-term operations.
      </p>
    </field>
  </record>

  <!-- ────────────────────────────────────────────────
       Search view with warehouse/supplier/state filters
  ──────────────────────────────────────────────── -->
  <record id="roq_shipment_group_calendar_search" model="ir.ui.view">
    <field name="name">roq.shipment.group.calendar.search</field>
    <field name="model">roq.shipment.group</field>
    <field name="arch" type="xml">
      <search string="Filter Shipments">
        <field name="name" string="Shipment"/>
        <field name="destination_warehouse_ids" string="Warehouse"/>
        <field name="container_type" string="Container"/>
        <field name="state" string="State"/>
        <separator/>
        <filter string="Planned (Draft)" name="filter_draft"
                domain="[('state','=','draft')]"/>
        <filter string="Confirmed" name="filter_confirmed"
                domain="[('state','=','confirmed')]"/>
        <filter string="In Transit" name="filter_in_transit"
                domain="[('state','in',['tendered','booked'])]"/>
        <filter string="Active" name="filter_active_states"
                domain="[('state','not in',['delivered','cancelled'])]"/>
        <group expand="0" string="Group By">
          <filter string="Warehouse" name="group_warehouse"
                  context="{'group_by': 'destination_warehouse_ids'}"/>
          <filter string="State" name="group_state"
                  context="{'group_by': 'state'}"/>
          <filter string="Container Type" name="group_container"
                  context="{'group_by': 'container_type'}"/>
        </group>
      </search>
    </field>
  </record>

</odoo>
```

**Step 3: Verify `fill_percentage` and `oos_risk_flag` exist on the model**

Read `roq_shipment_group.py` and confirm these field names. Adjust the XML if they use different names (e.g., `fill_pct`, `has_oos_risk`).

**Step 4: Commit**

```bash
git add roq.model/mml_roq_forecast/views/roq_shipment_calendar_views.xml
git commit -m "feat(roq-calendar): calendar view XML for roq.shipment.group"
```

---

## Task 7: Reschedule wizard view + coverage map view

**Files:**
- Create: `roq.model/mml_roq_forecast/views/roq_reschedule_wizard_views.xml`

**Step 1: Create wizard view XML**

Create `roq.model/mml_roq_forecast/views/roq_reschedule_wizard_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

  <record id="roq_reschedule_wizard_form" model="ir.ui.view">
    <field name="name">roq.reschedule.wizard.form</field>
    <field name="model">roq.reschedule.wizard</field>
    <field name="arch" type="xml">
      <form string="Consolidation Opportunity">
        <sheet>
          <div class="alert alert-warning" role="alert">
            <field name="summary" readonly="1" nolabel="1"/>
          </div>
          <group>
            <field name="source_group_id" readonly="1"/>
            <field name="candidate_group_ids" readonly="1" widget="many2many_tags"/>
          </group>
        </sheet>
        <footer>
          <button name="action_consolidate" type="object"
                  string="Consolidate" class="btn-primary"/>
          <button name="action_dismiss" type="object"
                  string="Keep Separate" class="btn-secondary"/>
        </footer>
      </form>
    </field>
  </record>

  <record id="action_roq_reschedule_wizard" model="ir.actions.act_window">
    <field name="name">Consolidation Suggestion</field>
    <field name="res_model">roq.reschedule.wizard</field>
    <field name="view_mode">form</field>
    <field name="view_id" ref="roq_reschedule_wizard_form"/>
    <field name="target">new</field>
  </record>

</odoo>
```

**Step 2: Commit**

```bash
git add roq.model/mml_roq_forecast/views/roq_reschedule_wizard_views.xml
git commit -m "feat(roq-calendar): reschedule wizard view"
```

---

## Task 8: Warehouse capacity settings view

Surface the capacity fields on the warehouse config form.

**Files:**
- Read existing warehouse view in `mml_roq_forecast` to find the right inherit target
- Modify or create: `roq.model/mml_roq_forecast/views/stock_warehouse_views.xml` (may already exist)

**Step 1: Find the existing warehouse view in this module**

Run:
```
grep -r "stock.warehouse" roq.model/mml_roq_forecast/views/ --include="*.xml" -l
```

**Step 2: Add capacity fields to the warehouse form**

Inherit the Odoo base warehouse form to add a "ROQ Receiving Capacity" group. The exact inherit ref needs to match what Odoo 19 uses for `stock.view_warehouse`. Example:

```xml
<record id="stock_warehouse_roq_capacity_form" model="ir.ui.view">
  <field name="name">stock.warehouse.roq.capacity</field>
  <field name="model">stock.warehouse</field>
  <field name="inherit_id" ref="stock.view_warehouse"/>
  <field name="arch" type="xml">
    <xpath expr="//sheet" position="inside">
      <group string="ROQ Receiving Capacity" col="3">
        <field name="roq_capacity_unit" string="Measure in"/>
        <field name="roq_weekly_capacity_cbm"
               invisible="roq_capacity_unit != 'cbm'"
               string="Max CBM/week"/>
        <field name="roq_weekly_capacity_teu"
               invisible="roq_capacity_unit != 'teu'"
               string="Max TEU/week"/>
      </group>
    </xpath>
  </field>
</record>
```

> **Note:** The `ref="stock.view_warehouse"` must be verified against Odoo 19 source. If the ref differs, find the correct one via: `self.env.ref('stock.view_warehouse')` in a shell, or grep the Odoo source.

**Step 3: Commit**

```bash
git add roq.model/mml_roq_forecast/views/
git commit -m "feat(roq-calendar): warehouse receiving capacity on warehouse form"
```

---

## Task 9: Menu entry + manifest update

Wire everything together.

**Files:**
- Modify: `roq.model/mml_roq_forecast/views/menus.xml`
- Modify: `roq.model/mml_roq_forecast/__manifest__.py`
- Modify: `roq.model/mml_roq_forecast/security/ir.model.access.csv`

**Step 1: Add menu entry**

In `menus.xml`, after the Shipment Groups submenu entry, add:

```xml
<menuitem
  id="menu_roq_shipment_calendar"
  name="Shipment Calendar"
  parent="menu_roq_root"
  action="roq_shipment_calendar_views.action_roq_shipment_calendar"
  sequence="20"
/>
```

**Step 2: Update `__manifest__.py`**

In the `data` list, add the new view files (order matters — models before views):

```python
'views/roq_shipment_calendar_views.xml',
'views/roq_reschedule_wizard_views.xml',
```

Also add to the models loading (if needed) any new model files.

**Step 3: Add security rules for the wizard and load models**

In `security/ir.model.access.csv`, add:

```csv
access_roq_reschedule_wizard,roq.reschedule.wizard,model_roq_reschedule_wizard,stock.group_stock_user,1,1,1,1
access_roq_warehouse_week_load,roq.warehouse.week.load,model_roq_warehouse_week_load,stock.group_stock_user,1,0,0,0
```

**Step 4: Commit**

```bash
git add roq.model/mml_roq_forecast/views/menus.xml \
        roq.model/mml_roq_forecast/__manifest__.py \
        roq.model/mml_roq_forecast/security/ir.model.access.csv
git commit -m "feat(roq-calendar): wire calendar menu, manifest, and security rules"
```

---

## Task 10: Install and smoke test

**Step 1: Upgrade the module**

```bash
python odoo-bin -u mml_roq_forecast -d <your_db> --stop-after-init
```

Expected: no errors, module upgrades cleanly.

**Step 2: Navigate to the calendar**

- Open Odoo → ROQ Forecast app → Shipment Calendar
- Confirm calendar loads in month view
- Confirm existing shipment groups appear as events

**Step 3: Test drag-and-drop**

- Find a `draft` shipment group
- Drag it forward by 7 days
- Confirm: ship date shifts by 7 days, chatter message appears

**Step 4: Test large shift consolidation suggestion**

- Create two `draft` groups with same `origin_port`, deliver within 21 days of each other
- Drag one to be within 21 days of the other (shift > 5 days)
- Confirm: `consolidation_suggestion` field is set on the dragged group

**Step 5: Test locked states**

- Find a `booked` shipment group
- Confirm it cannot be dragged (no drag handle in the calendar UI)

**Step 6: Test freight degradation**

- Temporarily uninstall `mml_freight` (or test on an instance without it)
- Confirm calendar loads without error, freight fields are empty

**Step 7: Final commit if any fixes needed**

```bash
git add -p  # stage only relevant changes
git commit -m "fix(roq-calendar): smoke test fixes"
```

---

## Known Follow-Up Items (not in scope here)

1. **Full OOS re-projection on drag**: The `write()` override currently re-evaluates the stored `projected_inventory_at_delivery`. A full re-projection adjusting for the lead-time delta requires joining back to `roq.forecast.line` — deferring to avoid scope creep.

2. **Coverage map as a proper Odoo pivot**: `roq.warehouse.week.load` is an `AbstractModel` service. Rendering it as a visual grid in the UI requires either a custom OWL component (deferred) or a pivot view on a stored model. A quick alternative is a wizard that prints the load table as a PDF/XLSX report.

3. **Freight `get_booking_status` real implementation**: Requires implementing `get_booking_status(shipment_group_id)` in the real FreightService (in `mml_roq_freight` bridge or `mml_freight` service) — currently only the NullService stub is wired.

4. **TEU load for LCL**: LCL shipments are exempt from TEU counting (weight-based billing). CBM load for LCL should still be counted — already handled in `CONTAINER_TEU` mapping returning `0.0` for LCL in TEU mode.
