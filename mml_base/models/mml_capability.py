from odoo import fields, models, api


class MmlCapability(models.Model):
    _name = 'mml.capability'
    _description = 'MML Capability Registry'

    name = fields.Char(required=True, index=True)
    module = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_name_module', 'UNIQUE(name, module)', 'Capability already registered for this module'),
    ]

    @api.model
    def register(self, capabilities: list[str], module: str) -> None:
        """Register a list of capability names for a module. Idempotent."""
        existing = self.search([('module', '=', module)]).mapped('name')
        to_create = [
            {'name': cap, 'module': module}
            for cap in capabilities
            if cap not in existing
        ]
        if to_create:
            self.create(to_create)

    @api.model
    def deregister_module(self, module: str) -> None:
        """Remove all capabilities registered by a module."""
        self.search([('module', '=', module)]).unlink()

    @api.model
    def has(self, capability: str) -> bool:
        """Return True if the capability is registered by any installed module."""
        return bool(self.search_count([('name', '=', capability)]))
