from . import models


def post_init_hook(env):
    """Register mml_base capabilities on install."""
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


def uninstall_hook(env):
    """Deregister all mml_base entries on uninstall."""
    env['mml.capability'].deregister_module('mml_base')
    env['mml.event.subscription'].deregister_module('mml_base')
