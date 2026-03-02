{
    'name': 'MML Base Platform',
    'version': '19.0.1.0.0',
    'summary': 'Event bus, capability registry, service locator, and billing ledger for MML modules',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mail', 'base'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
