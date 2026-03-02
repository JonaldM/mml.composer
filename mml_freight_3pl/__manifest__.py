{
    'name': 'MML Freight ↔ 3PL Bridge',
    'version': '19.0.1.0.0',
    'summary': 'Connects mml_freight and stock_3pl_core when both are installed',
    'author': 'MML Consumer Products',
    'category': 'Technical',
    'license': 'OPL-1',
    'depends': ['mml_freight', 'stock_3pl_core'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': True,
    'application': False,
}
