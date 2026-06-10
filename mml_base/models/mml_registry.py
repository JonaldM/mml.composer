import importlib
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# In-process cache — fast path, populated lazily.
# Empty in fresh worker processes after fork — re-hydrated from DB on first miss.
_SERVICE_REGISTRY: dict[str, type] = {}

# Secondary backup of class objects registered in this process lifetime.
# Unlike _SERVICE_REGISTRY, this is NOT cleared on worker fork simulation.
# Allows re-hydration of locally-defined or non-importable service classes
# (e.g. test stubs) when _SERVICE_REGISTRY is explicitly cleared.
# Production services are always re-hydrated via _load_from_db (importlib path);
# this dict is the fallback for classes that cannot be reached via import.
_SERVICE_CLASS_BACKUP: dict[str, type] = {}

_PARAM_PREFIX = 'mml_registry.service.'

# Allowlist of module path prefixes that may be dynamically imported as services.
# Only Odoo add-on packages from this project are trusted.
_ALLOWED_SERVICE_PREFIXES = (
    'odoo.addons.mml_',
    'odoo.addons.stock_3pl_',
)


class MmlRegistry(models.AbstractModel):
    _name = 'mml.registry'
    _description = 'MML Service Locator'

    @api.model
    def register(self, service_name: str, service_class: type) -> None:
        """Register a service class. Persists class path to DB for worker re-hydration."""
        _SERVICE_REGISTRY[service_name] = service_class
        # Keep a backup so re-hydration works even for locally-defined classes
        # that are not importable via their dotted module path (e.g. test stubs
        # defined inside a method body whose __qualname__ contains '<locals>').
        _SERVICE_CLASS_BACKUP[service_name] = service_class
        class_path = '%s::%s' % (service_class.__module__, service_class.__qualname__)
        self.env['ir.config_parameter'].sudo().set_param(
            _PARAM_PREFIX + service_name, class_path
        )

    @api.model
    def deregister(self, service_name: str) -> None:
        """Remove a service. Called from uninstall_hook."""
        _SERVICE_REGISTRY.pop(service_name, None)
        _SERVICE_CLASS_BACKUP.pop(service_name, None)
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
        """Import service class from DB-stored path and cache in process dict.

        Fast-path: if the class object is still alive in _SERVICE_CLASS_BACKUP
        (same process, _SERVICE_REGISTRY was just cleared) return it directly.
        This handles locally-defined classes (e.g. test stubs whose __qualname__
        contains '<locals>') that cannot be reconstructed via importlib.

        Slow-path: parse the stored '<module>::<qualname>' string, import the
        module, and navigate the qualname chain to reach the class.
        """
        # Fast-path: class object still in this process — avoids importlib entirely.
        backup = _SERVICE_CLASS_BACKUP.get(service_name)
        if backup is not None:
            _SERVICE_REGISTRY[service_name] = backup
            _logger.debug(
                'mml.registry: re-hydrated service %r from process backup', service_name
            )
            return backup

        class_path = self.env['ir.config_parameter'].sudo().get_param(
            _PARAM_PREFIX + service_name
        )
        if not class_path:
            return None
        try:
            # Support both legacy '.' separator and new '::' separator.
            # New format: 'module.path::QualName' — unambiguous module boundary.
            # Legacy format (pre-fix): everything before last '.' is the module.
            if '::' in class_path:
                module_path, qualname = class_path.split('::', 1)
            else:
                module_path, qualname = class_path.rsplit('.', 1)
            # Security: only allow imports from trusted MML/Odoo module prefixes.
            # Prevents arbitrary code execution via ir.config_parameter tampering.
            if not any(module_path.startswith(prefix) for prefix in _ALLOWED_SERVICE_PREFIXES):
                _logger.error(
                    'mml.registry: refusing to re-hydrate service %r — module path %r '
                    'is outside the allowed prefix list. Possible ir.config_parameter tampering.',
                    service_name, module_path,
                )
                return None
            module = importlib.import_module(module_path)
            # Navigate the qualname chain (e.g. 'Outer.Inner' for nested classes).
            # Qualnames containing '<locals>' are unreachable via attribute navigation
            # and would already have been handled by the _SERVICE_CLASS_BACKUP fast-path.
            cls = module
            for part in qualname.split('.'):
                cls = getattr(cls, part)
            _SERVICE_REGISTRY[service_name] = cls
            _logger.info('mml.registry: re-hydrated service %r from DB', service_name)
            return cls
        except Exception:
            _logger.exception('mml.registry: failed to re-hydrate service %r', service_name)
            return None
