import importlib
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# In-process cache — fast path, populated lazily.
# Empty in fresh worker processes after fork — re-hydrated from DB on first miss.
_SERVICE_REGISTRY: dict[str, type] = {}

_PARAM_PREFIX = 'mml_registry.service.'


class MmlRegistry(models.AbstractModel):
    _name = 'mml.registry'
    _description = 'MML Service Locator'

    @api.model
    def register(self, service_name: str, service_class: type) -> None:
        """Register a service class. Persists class path to DB for worker re-hydration."""
        _SERVICE_REGISTRY[service_name] = service_class
        class_path = '%s.%s' % (service_class.__module__, service_class.__qualname__)
        self.env['ir.config_parameter'].sudo().set_param(
            _PARAM_PREFIX + service_name, class_path
        )

    @api.model
    def deregister(self, service_name: str) -> None:
        """Remove a service. Called from uninstall_hook."""
        _SERVICE_REGISTRY.pop(service_name, None)
        self.env['ir.config_parameter'].sudo().set_param(
            _PARAM_PREFIX + service_name, False
        )

    @api.model
    def service(self, service_name: str):
        """
        Return an instance of the registered service, or a NullService.
        Fast path: in-process dict. Slow path: DB lookup + dynamic import.
        """
        from odoo.addons.mml_base.services.null_service import NullService

        cls = _SERVICE_REGISTRY.get(service_name)
        if cls is None:
            cls = self._load_from_db(service_name)
        if cls is None:
            return NullService()
        return cls(self.env)

    @api.model
    def _load_from_db(self, service_name: str):
        """Import service class from DB-stored path and cache in process dict."""
        class_path = self.env['ir.config_parameter'].sudo().get_param(
            _PARAM_PREFIX + service_name
        )
        if not class_path:
            return None
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            _SERVICE_REGISTRY[service_name] = cls
            _logger.info('mml.registry: re-hydrated service %r from DB', service_name)
            return cls
        except Exception:
            _logger.exception('mml.registry: failed to re-hydrate service %r', service_name)
            return None
