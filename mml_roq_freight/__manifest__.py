{
    'name': 'MML ROQ ↔ Freight Bridge',
    'version': '19.0.1.0.0',
    'summary': 'Connects mml_roq_forecast and mml_freight when both are installed',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mml_roq_forecast', 'mml_freight'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': True,
    'application': False,
}
