from . import models


def _register_base_platform(env) -> None:
    """Register mml_base capabilities and seed mml.instance_ref.

    Shared helper called by both post_init_hook (fresh install) and the
    19.0.1.1.1 post-migration script (upgrade).  Idempotent: re-registering
    capabilities is a no-op if the entries already exist; instance_ref is
    seeded only when absent.

    Why this helper exists:
        post_init_hook only runs on fresh module install (-i), NOT on
        upgrade (-u).  Without this helper the mml.capability rows for
        mml_base would silently vanish after a production -u, causing
        capability checks across all dependent modules to return False.

    Capabilities registered:
        - mml.event.emit
        - mml.capability.register
        - mml.registry.service
        - mml.event.subscription.register
    """
    import uuid

    env['mml.capability'].register(
        [
            'mml.event.emit',
            'mml.capability.register',
            'mml.registry.service',
            'mml.event.subscription.register',
        ],
        module='mml_base',
    )
    # Seed mml.instance_ref with a stable UUID if not already set.
    # Every mml.event carries this ref for multi-instance billing attribution.
    IrParam = env['ir.config_parameter'].sudo()
    if not IrParam.get_param('mml.instance_ref'):
        IrParam.set_param('mml.instance_ref', str(uuid.uuid4()))


def post_init_hook(env) -> None:
    """Register mml_base capabilities on install."""
    _register_base_platform(env)


def uninstall_hook(env) -> None:
    """Deregister all mml_base entries on uninstall."""
    env['mml.capability'].deregister_module('mml_base')
    env['mml.event.subscription'].deregister_module('mml_base')
