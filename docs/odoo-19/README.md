# Odoo 19 Developer Documentation (local cache)

Fetched: 2026-03-07

Content sourced from the Odoo 19.0 documentation site and the `odoo/documentation` GitHub repository (branch `19.0`). The official docs site renders content via JavaScript, so most pages were fetched from the raw RST source at `https://raw.githubusercontent.com/odoo/documentation/19.0/content/...` and converted to markdown.

| File | Source URL | Description |
|------|-----------|-------------|
| [orm-reference.md](orm-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html | Complete ORM API reference: models, fields, recordsets, search domains, environment, SQL execution, common CRUD/search methods, and inheritance patterns. |
| [views-reference.md](views-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/views.html | View architecture reference for all view types: form, list, search, kanban, graph, pivot, calendar, QWeb — including all XML attributes with types and defaults. |
| [actions-reference.md](actions-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html | Reference for all action types: window actions (`ir.actions.act_window`), URL actions, server actions, report actions, client actions, and scheduled actions (`ir.cron`). |
| [module-manifest-reference.md](module-manifest-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html | Complete reference for `__manifest__.py` fields: name, version, depends, data, auto_install, assets, application, hooks, and all other manifest keys. |
| [security-reference.md](security-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html | Security reference covering access rights (`ir.model.access`), record rules (`ir.rule`), field access groups, and security pitfalls (SQL injection, ORM bypass, XSS, unsafe eval). |
| [testing-reference.md](testing-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html | Testing reference covering Python unit tests (`TransactionCase`, `HttpCase`), test tags, tour-based integration testing, onboarding tours, debugging, and query count assertions. |
| [server-framework-101.md](server-framework-101.md) | https://www.odoo.com/documentation/19.0/developer/tutorials/server_framework_101.html | Tutorial covering the full module development lifecycle: architecture overview, creating apps, models and fields, security, views, relations, computed fields, constraints, and inheritance. |
| [owl-components-reference.md](owl-components-reference.md) | https://www.odoo.com/documentation/19.0/developer/reference/frontend/owl_components.html | Reference for Odoo's built-in Owl UI components: ActionSwiper, CheckBox, ColorList, Dropdown, Notebook, Pager, SelectMenu, and TagsList — with all props documented. |
| [website-themes.md](website-themes.md) | https://www.odoo.com/documentation/19.0/developer/howtos/website_themes.html | Overview of website theme development: module structure, Bootstrap variable overrides, custom building blocks (snippets), header/footer customisation, and asset bundle configuration. |
| [upgrade-module-howto.md](upgrade-module-howto.md) | https://www.odoo.com/documentation/19.0/developer/howtos/upgrade_custom_db.html | Six-step guide for upgrading a customised Odoo database: stopping development, requesting an upgraded DB, making modules installable on empty and upgraded databases, writing migration scripts, and production upgrade. |

## Full RST Source — `developer-rst/`

The `developer-rst/` directory contains the complete RST source for the Odoo 19 developer documentation, sparse-cloned directly from the `odoo/documentation` GitHub repository.

- **Source:** `https://github.com/odoo/documentation.git`
- **Branch:** `19.0`
- **Cloned:** 2026-03-07
- **Method:** `git clone --depth=1 --filter=blob:none --sparse`, then `git sparse-checkout set content/developer`
- **Content path in repo:** `content/developer/`
- **Files:** 366 RST files, ~16 MB
- **Also included:** `conf.py` from the repo root (Sphinx build configuration)

### Directory structure

```
developer-rst/
├── glossary.rst
├── howtos/                        ← How-to guides
│   ├── accounting_localization/
│   ├── translations/
│   ├── website_themes/
│   ├── company.rst
│   ├── connect_device.rst
│   ├── create_reports.rst
│   ├── frontend_owl_components.rst
│   ├── javascript_*.rst
│   ├── scss_tips.rst
│   └── upgrade_custom_db.rst
├── reference/
│   ├── backend/                   ← Core backend reference
│   │   ├── orm/                   ← Full ORM reference (multi-file)
│   │   ├── testing/
│   │   ├── performance/
│   │   ├── data/
│   │   ├── actions.rst
│   │   ├── http.rst
│   │   ├── mixins.rst
│   │   ├── module.rst
│   │   ├── reports.rst
│   │   └── security.rst
│   ├── external_api/
│   ├── extract_api/
│   ├── frontend/                  ← JS/OWL frontend reference
│   │   ├── owl_components/
│   │   ├── services/
│   │   ├── unit_testing/
│   │   ├── mobile/
│   │   ├── odoo_editor/
│   │   └── *.rst
│   ├── standard_modules/
│   ├── upgrades/
│   └── user_interface/            ← View architectures, SCSS
│       └── view_architectures/
└── tutorials/
    ├── server_framework_101/
    ├── discover_js_framework/
    ├── master_odoo_web_framework/
    ├── importable_modules/
    ├── pdf_reports/
    ├── restrict_data_access/
    ├── web/
    └── website_theme/
```

## Notes

- The `views-reference.md` source was `content/developer/reference/user_interface/view_architectures.rst` (the views doc lives under `user_interface/`, not `backend/`, in the 19.0 docs repo).
- The `upgrade-module-howto.md` source is `upgrade_custom_db.html`, not `upgrade_a_module.html` (the URL in the original request 404s in Odoo 19).
- The `website-themes.md` covers the overview only; the full theme documentation is split across 13 sub-pages in the official docs.
- The `server-framework-101.md` includes synthesised code examples from chapters 1–3 of the tutorial plus a comprehensive model/view/action example to make the file practically useful for reference.
