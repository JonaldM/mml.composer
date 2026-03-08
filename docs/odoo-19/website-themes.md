# Website Themes

> Source: https://www.odoo.com/documentation/19.0/developer/howtos/website_themes.html
> Fetched: 2026-03-07

The Odoo Website Builder enables users to create a website fully integrated with other Odoo apps. The platform allows customisation through the theme's options and building blocks while maintaining simplicity and personalisation capabilities.

This documentation guides developers through extensive customisation without modifying Odoo's core system, thereby preserving Website Builder's editing functionality.

## Table of Contents

The website themes documentation covers the following topics (each is a separate sub-page in the official docs):

1. **Setup** — Environment setup for theme development
2. **Theming** — Core theming concepts, Bootstrap variable overrides, SCSS customisation
3. **Layout** — Header, footer, and page layout customisation
4. **Navigation** — Menu and navigation structure
5. **Pages** — Creating and managing website pages
6. **Media** — Images, icons, and other media assets
7. **Building Blocks** — Creating custom snippets (building blocks) for the website editor
8. **Shapes** — Custom SVG shapes and decorative elements
9. **Gradients** — Custom gradient definitions
10. **Animations** — CSS and scroll-based animations
11. **Forms** — Custom form styling and behaviour
12. **Translations** — Translating theme content
13. **Going Live** — Deploying and publishing the theme

## Overview

A website theme in Odoo is an Odoo module that inherits from `theme` or `website` and customises the appearance and behaviour of the website. Themes are built using:

- **SCSS/CSS**: Bootstrap variable overrides and custom styles
- **QWeb XML templates**: Layout and building block templates
- **JavaScript (OWL)**: Interactive components
- **Python**: Optional server-side logic

### Minimal Theme Module Structure

```
my_theme/
├── __manifest__.py
├── __init__.py
├── static/
│   ├── description/
│   │   └── icon.png
│   ├── src/
│   │   ├── scss/
│   │   │   ├── primary_variables.scss    # Bootstrap variable overrides
│   │   │   └── theme.scss               # Custom styles
│   │   ├── js/
│   │   │   └── theme.js
│   │   └── xml/
│   │       └── snippets.xml             # Custom building blocks
│   └── img/
│       └── ...
├── views/
│   ├── layouts.xml                      # Header/footer overrides
│   ├── pages.xml                        # Custom pages
│   └── snippets.xml                     # Building block views
└── data/
    └── ir_ui_view.xml
```

### Manifest for a Website Theme

```python
{
    'name': 'My Theme',
    'description': 'A custom Odoo website theme',
    'version': '19.0.1.0.0',
    'category': 'Theme',
    'depends': ['website'],
    'data': [
        'views/layouts.xml',
        'views/pages.xml',
        'views/snippets.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'my_theme/static/src/scss/primary_variables.scss'),
        ],
        'website.assets_website': [
            'my_theme/static/src/scss/theme.scss',
            'my_theme/static/src/js/theme.js',
        ],
    },
    'application': True,
    'license': 'LGPL-3',
}
```

### Bootstrap Variable Overrides

Override Bootstrap variables in `primary_variables.scss` using the `prepend` asset loading order:

```scss
// primary_variables.scss

// Colors
$o-color-1: #3AADAA;
$o-color-2: #7C6576;
$o-color-3: #F6F3F5;
$o-color-4: #E9EDF0;
$o-color-5: #FFFFFF;

// Fonts
$o-theme-font-1: 'Roboto';
$o-theme-font-2: 'Playfair Display';

// Layout
$o-navbar-default-bg: $o-color-1;
```

### Custom Building Block (Snippet)

Define a custom snippet template:

```xml
<!-- views/snippets.xml -->
<odoo>
    <template id="s_my_snippet" name="My Snippet">
        <section class="s_my_snippet">
            <div class="container">
                <h2>My Custom Block</h2>
                <p>Content goes here.</p>
            </div>
        </section>
    </template>

    <!-- Register in the snippets list -->
    <template id="snippets" inherit_id="website.snippets" name="My Snippets">
        <xpath expr="//div[@id='snippet_content']" position="before">
            <t t-snippet="my_theme.s_my_snippet" t-thumbnail="/my_theme/static/img/snippets/s_my_snippet.png"/>
        </xpath>
    </template>
</odoo>
```

### Header Override

```xml
<!-- views/layouts.xml -->
<odoo>
    <template id="custom_header" inherit_id="website.layout" name="Custom Header">
        <xpath expr="//header" position="replace">
            <header>
                <!-- Custom header content -->
                <nav class="navbar navbar-expand-lg">
                    ...
                </nav>
            </header>
        </xpath>
    </template>
</odoo>
```

> Note: The full sub-page documentation for each of the 13 topics listed above is available at `https://www.odoo.com/documentation/19.0/developer/howtos/website_themes/<topic>.html`. This file covers the overview and common patterns. Refer to the official docs for complete coverage of each sub-topic.
