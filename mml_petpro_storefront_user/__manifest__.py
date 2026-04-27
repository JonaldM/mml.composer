{
    'name': 'MML PetPro Storefront User',
    'version': '19.0.1.0.0',
    'summary': 'Dedicated, minimum-privilege Odoo user for the headless PetPro Next.js storefront',
    'description': """
MML PetPro Storefront User
==========================

Defines a dedicated ``res.users`` account, ``res.groups`` membership, and
``ir.model.access.csv`` ACLs that grant the headless petpro.co.nz Next.js
storefront the *minimum* privileges it needs to render the catalogue, manage
carts, and process checkouts.

Defense-in-depth: the storefront historically connects to Odoo using an
admin account (``ODOO_ADMIN_EMAIL`` / ``ODOO_ADMIN_PASSWORD``), so any user
input that reaches ``client.call()`` runs at admin scope. Switching the
storefront to this dedicated user closes that lateral-movement gap.

Manual operator steps after install: see
``docs/operations/2026-04-27-petpro-storefront-user-runbook.md``.
""",
    'author': 'MML Consumer Products Ltd',
    'website': 'https://www.mmlconsumerproducts.co.nz',
    'category': 'Hidden',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'product',
        'account',
        'delivery',
        'payment',
    ],
    'data': [
        'security/petpro_storefront_groups.xml',
        'security/ir.model.access.csv',
        'data/petpro_storefront_user.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
