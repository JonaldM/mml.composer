"""Post-migration for mml_base 19.0.1.1.1.

Ensures mml_base capabilities are registered in mml.capability after a module
upgrade, and that mml.instance_ref is seeded in ir.config_parameter.

Why this is needed:
    post_init_hook only runs on fresh module install (-i), NOT on upgrade (-u).
    When upgrading an existing Odoo instance, the mml.capability rows for
    mml_base may be absent or stale if the module was previously at a lower
    version.  Dependent modules across the entire MML platform query these
    capabilities before performing service calls; a missing capability row
    causes those checks to silently return False, breaking cross-module
    feature detection.

    The folder is versioned 19.0.1.1.1 (one patch above the prior installed
    19.0.1.1.0) so Odoo's migration manager actually runs it on -u; a folder
    equal to the installed version is skipped.

    The 19.0.1.1.0 migration (partial UNIQUE index on mml_event.dedupe_key)
    is unrelated and remains untouched.

Manual verification:
    SELECT name FROM mml_capability WHERE module = 'mml_base';
    -- Expected: mml.event.emit, mml.capability.register,
    --           mml.registry.service, mml.event.subscription.register

    SELECT value FROM ir_config_parameter WHERE key = 'mml.instance_ref';
    -- Expected: a UUID string
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version: str) -> None:
    """Re-register mml_base capabilities and seed mml.instance_ref.

    Args:
        cr: Odoo cursor (psycopg2 cursor wrapper).
        version: Module version string before the upgrade. None/empty means
            fresh install -- post_init_hook already handles that case, but
            calling _register_base_platform() again is harmless (idempotent).
    """
    from odoo import api, SUPERUSER_ID
    from odoo.addons.mml_base import _register_base_platform

    env = api.Environment(cr, SUPERUSER_ID, {})
    _register_base_platform(env)
    _logger.info(
        'mml_base 19.0.1.1.1: re-registered platform capabilities in '
        'mml.capability and ensured mml.instance_ref is seeded'
    )
