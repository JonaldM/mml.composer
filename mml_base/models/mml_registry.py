from odoo import api, models

# In-process service registry — survives within a worker process lifetime.
# Populated via register() calls in each module's post_init_hook.
_SERVICE_REGISTRY: dict[str, type] = {}


class MmlRegistry(models.AbstractModel):
    _name = 'mml.registry'
    _description = 'MML Service Locator'

    @api.model
    def register(self, service_name: str, service_class: type) -> None:
        """Register a service class under a name. Called from post_init_hook."""
        _SERVICE_REGISTRY[service_name] = service_class

    @api.model
    def deregister(self, service_name: str) -> None:
        """Remove a service. Called from uninstall_hook."""
        _SERVICE_REGISTRY.pop(service_name, None)

    @api.model
    def service(self, service_name: str):
        """
        Return an instance of the registered service, or a NullService.
        The returned object is always safe to call — no existence check needed.
        """
        from odoo.addons.mml_base.services.null_service import NullService
        cls = _SERVICE_REGISTRY.get(service_name)
        if cls is None:
            return NullService()
        return cls(self.env)
