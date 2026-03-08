# Server Framework 101

> Source: https://www.odoo.com/documentation/19.0/developer/tutorials/server_framework_101.html
> Fetched: 2026-03-07

This tutorial introduces key aspects of Odoo development through building a real estate asset management module. The goal is to get an insight of the most important parts of the Odoo development framework while developing your own Odoo module.

The chapters are designed as a sequential, incremental progression where each builds on the previous content.

## Prerequisites

Ensure your development environment is properly configured using the setup guide. You'll need basic HTML knowledge and intermediate Python skills.

## Tutorial Chapters

1. Architecture Overview
2. A New Application
3. Models and Basic Fields
4. Security Introduction
5. First UI
6. Basic Views
7. Relations Between Models
8. Computed Fields and Onchanges
9. Actions and Constraints
10. Sprinkles (UI Polish)
11. Inheritance
12. Interact with Other Modules
13. Introduction to QWeb
14. Final Word

---

## Chapter 1: Architecture Overview

### Multitier Application

Odoo implements a multitier architecture separating presentation, business logic, and data storage using a three-tier architecture:

- **Presentation tier**: HTML5, JavaScript, and CSS
- **Logic tier**: Python exclusively
- **Data tier**: PostgreSQL as the RDBMS

> "Since version 15.0, Odoo is actively transitioning to using its own in-house developed OWL framework as part of its presentation tier."

The legacy JavaScript framework remains supported but faces eventual deprecation.

### Odoo Modules

Both server and client extensions are packaged as modules that load optionally into a database. A module groups functions and data toward a single purpose.

Modules can introduce new business logic or modify existing logic. They are organised in directories specified by the `addons_path`. User-facing modules are designated as *Apps*, though most modules are not.

#### Module Composition

An Odoo module may contain:

- **Business objects**: Python classes mapped to database columns via ORM
- **Object views**: Define UI display
- **Data files**: XML or CSV files for views, reports, configuration, and demonstration data
- **Web controllers**: Handle browser requests
- **Static web data**: Images, CSS, or JavaScript files

#### Module Structure

```
module/
├── models/
│   ├── *.py
│   └── __init__.py
├── data/
│   └── *.xml
├── __init__.py
└── __manifest__.py
```

### Odoo Editions

Odoo comes in two versions: Odoo Enterprise (licensed, shared sources) and Odoo Community (open-source). The Enterprise version provides extra functionalities as additional modules built on the Community version.

---

## Chapter 2: A New Application

### Directory Structure Requirements

Create a directory named `estate` within the `tutorials` folder. Every module requires two essential files:

1. `__init__.py` — may remain empty initially
2. `__manifest__.py` — requires at least a `name` field

### Manifest File Contents

Examine the CRM module manifest as a reference. The manifest should include:

- Module description (name, category, summary, website)
- Dependencies listing via the `depends` key

"A dependency means that the Odoo framework will ensure that these modules are installed before our module is installed."

For a new module, only the `base` framework module is initially necessary.

Configure the module as an App by setting `'application': True` in `__manifest__.py`.

---

## Chapter 3: Models and Basic Fields

### Object-Relational Mapping

Business objects are Python classes extending `Model`, integrating them into the automated persistence system.

Models are configured through attributes. The required `_name` attribute defines the model's identifier in Odoo:

```python
from odoo import models

class TestModel(models.Model):
    _name = "test_model"
```

This generates a database table named `test_model`. By convention, models reside in a `models` directory, with each model in its own Python file.

Module structure for the `crm_recurring_plan` example:
1. Model defined in `crm/models/crm_recurring_plan.py`
2. File imported in `crm/models/__init__.py`
3. Folder imported in `crm/__init__.py`

After modifying Python files, restart the Odoo server with:

```console
./odoo-bin --addons-path=addons,../enterprise/,../tutorials/ -d rd-demo -u estate
```

The `-u estate` flag upgrades the module (applying database schema changes and creating tables).

### Model Fields

Fields are defined as class attributes:

```python
from odoo import fields, models

class TestModel(models.Model):
    _name = "test_model"
    _description = "Test Model"

    name = fields.Char()
```

**Simple field types:** Boolean, Float, Char, Text, Date, Selection, Integer

**Relational field types:** Many2one, One2many, Many2many

#### Common Field Attributes

**`string`** (str, default: field's name): The field label in the UI.

**`required`** (bool, default: `False`): If `True`, the field cannot be empty.

**`help`** (str, default: `''`): Provides long-form help tooltips for users in the UI.

**`index`** (bool, default: `False`): Requests that Odoo create a database index on the column.

```python
name = fields.Char(required=True)
expected_price = fields.Float(required=True, digits=(16, 2))
garden_orientation = fields.Selection(
    selection=[('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West')]
)
```

#### Automatic Fields

Odoo creates a few fields in all models (readable but not directly writable):

- **`id`** (Id): The unique record identifier
- **`create_date`** (Datetime): Record creation date
- **`create_uid`** (Many2one): User who created the record
- **`write_date`** (Datetime): Last modification date
- **`write_uid`** (Many2one): User who last modified the record

> "Do not use mutable global variables. A single Odoo instance can run several databases in parallel within the same python process."

---

## Key Concepts Summary

### Model Definition Pattern

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class EstateProperty(models.Model):
    _name = "estate.property"
    _description = "Real Estate Property"
    _order = "name"

    name = fields.Char(required=True)
    description = fields.Text()
    postcode = fields.Char()
    date_availability = fields.Date(copy=False)
    expected_price = fields.Float(required=True)
    selling_price = fields.Float(readonly=True, copy=False)
    bedrooms = fields.Integer(default=2)
    living_area = fields.Integer()
    facades = fields.Integer()
    garage = fields.Boolean()
    garden = fields.Boolean()
    garden_area = fields.Integer()
    garden_orientation = fields.Selection(
        selection=[('N', 'North'), ('S', 'South'), ('E', 'East'), ('W', 'West')]
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('offer_received', 'Offer Received'),
            ('offer_accepted', 'Offer Accepted'),
            ('sold', 'Sold'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        copy=False,
        default='new',
    )
    # Relational
    property_type_id = fields.Many2one("estate.property.type", string="Property Type")
    buyer_id = fields.Many2one("res.partner", string="Buyer", copy=False)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user)
    tag_ids = fields.Many2many("estate.property.tag", string="Tags")
    offer_ids = fields.One2many("estate.property.offer", "property_id", string="Offers")
    # Computed
    total_area = fields.Integer(compute="_compute_total_area")
    best_price = fields.Float(compute="_compute_best_price")

    @api.depends("living_area", "garden_area")
    def _compute_total_area(self):
        for prop in self:
            prop.total_area = prop.living_area + prop.garden_area

    @api.depends("offer_ids.price")
    def _compute_best_price(self):
        for prop in self:
            prop.best_price = max(prop.offer_ids.mapped("price"), default=0)

    @api.onchange("garden")
    def _onchange_garden(self):
        if self.garden:
            self.garden_area = 10
            self.garden_orientation = "N"
        else:
            self.garden_area = 0
            self.garden_orientation = False

    @api.constrains("selling_price", "expected_price")
    def _check_selling_price(self):
        for prop in self:
            if prop.selling_price > 0 and prop.selling_price < 0.9 * prop.expected_price:
                raise ValidationError(
                    "The selling price cannot be lower than 90% of the expected price."
                )
```

### Security File (`ir.model.access.csv`)

```csv
id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink
access_estate_property,access_estate_property,model_estate_property,base.group_user,1,1,1,1
```

### View Examples

**List view:**

```xml
<record id="estate_property_view_list" model="ir.ui.view">
    <field name="name">estate.property.list</field>
    <field name="model">estate.property</field>
    <field name="arch" type="xml">
        <list>
            <field name="name"/>
            <field name="property_type_id"/>
            <field name="postcode"/>
            <field name="bedrooms"/>
            <field name="living_area"/>
            <field name="expected_price"/>
            <field name="selling_price"/>
            <field name="state"/>
        </list>
    </field>
</record>
```

**Form view:**

```xml
<record id="estate_property_view_form" model="ir.ui.view">
    <field name="name">estate.property.form</field>
    <field name="model">estate.property</field>
    <field name="arch" type="xml">
        <form>
            <header>
                <button name="action_sold" type="object" string="Sold"/>
                <button name="action_cancel" type="object" string="Cancel"/>
                <field name="state" widget="statusbar"/>
            </header>
            <sheet>
                <div class="oe_title">
                    <h1><field name="name"/></h1>
                </div>
                <group>
                    <group>
                        <field name="property_type_id"/>
                        <field name="postcode"/>
                        <field name="date_availability"/>
                    </group>
                    <group>
                        <field name="expected_price"/>
                        <field name="best_price"/>
                        <field name="selling_price"/>
                    </group>
                </group>
                <notebook>
                    <page string="Description">
                        <group>
                            <field name="description"/>
                            <field name="bedrooms"/>
                            <field name="living_area"/>
                            <field name="facades"/>
                            <field name="garage"/>
                            <field name="garden"/>
                            <field name="garden_area" invisible="not garden"/>
                            <field name="garden_orientation" invisible="not garden"/>
                            <field name="total_area"/>
                        </group>
                    </page>
                    <page string="Offers">
                        <field name="offer_ids"/>
                    </page>
                    <page string="Other Info">
                        <group>
                            <field name="salesperson_id"/>
                            <field name="buyer_id"/>
                            <field name="tag_ids" widget="many2many_tags"/>
                        </group>
                    </page>
                </notebook>
            </sheet>
        </form>
    </field>
</record>
```

### Action and Menu

```xml
<record id="estate_property_action" model="ir.actions.act_window">
    <field name="name">Properties</field>
    <field name="res_model">estate.property</field>
    <field name="view_mode">list,form</field>
    <field name="context">{"search_default_available": True}</field>
</record>

<menuitem id="estate_menu_root" name="Real Estate" sequence="10"/>
<menuitem id="estate_menu_properties" name="Properties"
          parent="estate_menu_root"
          action="estate_property_action"/>
```
