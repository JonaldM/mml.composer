import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MmlLicense(models.Model):
    _name = 'mml.license'
    _description = 'MML License Cache'
    _rec_name = 'org_ref'

    org_ref = fields.Char(help='Organisation identifier from the MML platform')
    license_key = fields.Char(
        help='Secret license key — do not share',
        password=True,
        groups='base.group_system',
    )
    tier = fields.Selection([
        ('internal', 'Internal'),
        ('starter', 'Starter'),
        ('growth', 'Growth'),
        ('enterprise', 'Enterprise'),
    ], default='internal', required=True)
    module_grants_json = fields.Text(
        default='["*"]',
        help='JSON list of permitted module names. ["*"] means all modules permitted.',
    )
    floor_amount = fields.Float(
        default=0.0,
        help='Monthly minimum commitment (NZD). Applied as billing credit.',
    )
    currency_id = fields.Many2one('res.currency')
    seat_limit = fields.Integer(default=0, help='Maximum users. 0 = unlimited.')
    valid_until = fields.Date()
    last_validated = fields.Datetime()

    @api.model
    def get_current(self) -> 'MmlLicense':
        """Return the active license record, creating a default internal license if none exists."""
        lic = self.search([], limit=1)
        if not lic:
            lic = self.create({'tier': 'internal'})
        return lic

    def module_permitted(self, module_name: str) -> bool:
        """Return True if this license grants access to the given module."""
        self.ensure_one()
        try:
            grants = json.loads(self.module_grants_json or '["*"]')
            if not isinstance(grants, list):
                raise ValueError('module_grants_json must be a JSON list')
        except (json.JSONDecodeError, ValueError):
            _logger.warning(
                'mml.license %s has invalid module_grants_json — denying access (fail-secure)',
                self.id,
            )
            return False
        if self.valid_until and self.valid_until < fields.Date.today():
            _logger.warning(
                'mml.license: license expired on %s — denying module %s',
                self.valid_until, module_name,
            )
            return False
        return '*' in grants or module_name in grants
