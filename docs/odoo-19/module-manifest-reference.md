# Module Manifests

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html
> Fetched: 2026-03-07

## Manifest

The manifest file declares a Python package as an Odoo module and specifies module metadata. Named `__manifest__.py`, it contains a single Python dictionary where each key specifies module metadatum.

```python
{
    'name': "A Module",
    'version': '1.0',
    'depends': ['base'],
    'author': "Author Name",
    'category': 'Category',
    'description': """
    Description text
    """,
    # data files always loaded at installation
    'data': [
        'views/mymodule_view.xml',
    ],
    # data files containing optionally loaded demonstration data
    'demo': [
        'demo/demo_data.xml',
    ],
}
```

## Available Manifest Fields

**name** (str, required)
The human-readable name of the module.

**version** (str)
This module's version; should follow semantic versioning rules.

**description** (str)
Extended description for the module, in reStructuredText.

**author** (str)
Name of the module author.

**website** (str)
Website URL for the module author.

**license** (str, default: LGPL-3)
Distribution license for the module. Possible values:
- GPL-2
- GPL-2 or any later version
- GPL-3
- GPL-3 or any later version
- AGPL-3
- LGPL-3
- Other OSI approved licence
- OEEL-1 (Odoo Enterprise Edition License v1.0)
- OPL-1 (Odoo Proprietary License v1.0)
- Other proprietary

**category** (str, default: Uncategorized)
Classification category within Odoo for the module's business domain. Using existing categories is recommended, though the field is freeform. Hierarchies can be created using "/" as a separator (e.g., "Foo / Bar").

**depends** (list(str))
Odoo modules which must be loaded before this one. When a module is installed, all dependencies are installed first.

> "Module base is always installed in any Odoo instance. But you still need to specify it as dependency to make sure your module is updated when base is updated."

**data** (list(str))
List of data files which must always be installed or updated with the module.

**demo** (list(str))
List of data files which are only installed or updated in demonstration mode.

**auto_install** (bool or list(str), default: False)
If True, the module automatically installs when all dependencies are met. Generally used for "link modules" implementing integration between independent modules. If a list, it must contain a subset of dependencies, and the module installs when that subset is satisfied.

**external_dependencies** (dict(key=list(str)))
A dictionary containing Python and/or binary dependencies. The "python" key maps to Python modules to import; the "bin" key maps to binary executables. Installation fails if dependencies are missing.

**application** (bool, default: False)
Whether the module is a fully-fledged application (`True`) or a technical module (`False`) providing extra functionality.

**assets** (dict)
Defines how static files load in various asset bundles.

**installable** (bool, default: True)
Whether users can install the module from the Web UI.

**maintainer** (str)
Person or entity maintaining this module; defaults to the author.

**{pre_init, post_init, uninstall}_hook** (str)
Hooks for module installation/uninstallation, as function names in the module's `__init__.py`. These execute before, after, or following uninstallation respectively, taking only an env argument.

**active** (bool)
Deprecated. Replaced by `auto_install`.
