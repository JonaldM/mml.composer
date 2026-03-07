from . import models


def post_init_hook(env):
    """Register mml_base capabilities on install."""
    env['mml.capability'].register(
        [
            'mml.event.emit',
            'mml.capability.register',
            'mml.registry.service',
            'mml.event.subscription.register',
        ],
        module='mml_base',
    )


def uninstall_hook(env):
    """Deregister all mml_base entries on uninstall."""
    env['mml.capability'].deregister_module('mml_base')
    env['mml.event.subscription'].deregister_module('mml_base')
