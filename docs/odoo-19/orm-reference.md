# ORM API

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
> Fetched: 2026-03-07

## Overview

This documentation covers Odoo's Object-Relational Mapping (ORM) system, which provides a comprehensive framework for defining, managing, and interacting with database models through Python classes.

## Models

Model fields are defined as class attributes on model classes:

```python
from odoo import models, fields

class AModel(models.Model):
    _name = 'a.model.name'
    field1 = fields.Char()
```

**Important:** Field names and method names cannot overlap; the last definition silently overwrites previous ones.

Field labels default to capitalized versions of field names but can be customized via the `string` parameter:

```python
field2 = fields.Integer(string="Field Label")
```

### Default Values

Default values can be specified as static values or computed via functions:

```python
name = fields.Char(default="a value")

def _default_name(self):
    return self.get_value()

name = fields.Char(default=lambda self: self._default_name())
```

### Model Attributes

**`_auto`**: Controls automatic table creation and updates

**`_log_access`**: Enables automatic generation of access tracking fields; defaults to `_auto` value

**`_table`**: Database table name

**`_register`**: Whether the model should be registered in the ORM registry

**`_abstract`**: Marks a model as abstract (not persisted to database)

**`_transient`**: Designates models for temporary data storage

**`_name`**: Unique identifier for the model

**`_description`**: User-friendly model description

**`_inherit`**: Specifies parent model(s) for inheritance

**`_inherits`**: Dictionary mapping parent models for delegation inheritance

**`_rec_name`**: Field used for record display names (defaults to "name")

**`_order`**: Default record ordering

**`_check_company_auto`**: Auto-validates company consistency across records

**`_parent_name`**: Field name for hierarchical record relationships

**`_parent_store`**: Optimizes parent/child queries when true

**`_fold_name`**: Field for grouping fold states in list views

### Model Types

**AbstractModel**: Base class for models not persisted to database; useful for shared functionality

**Model**: Standard persistent model stored in database

**TransientModel**: Temporary data model with automatic cleanup; provides `_transient_vacuum`, `_transient_max_count`, and `_transient_max_hours` attributes

## Fields

### Basic Field Types

- **Boolean**: True/false values
- **Char**: Short text strings
- **Float**: Decimal numbers
- **Integer**: Whole numbers

### Advanced Field Types

- **Binary**: File/binary data storage
- **Html**: Rich text with HTML formatting
- **Image**: Image file storage with thumbnails
- **Monetary**: Currency-aware numeric values
- **Selection**: Enumerated options from predefined list
- **Text**: Long text strings

### Date and Datetime Fields

Date and datetime fields accept:

- Python `date` or `datetime` objects
- Strings in server format (`YYYY-MM-DD` for Date, `YYYY-MM-DD HH:MM:SS` for Datetime)
- `False` or `None`

Helper methods available:
- `Date.to_date()`: Converts to `datetime.date`
- `Datetime.to_datetime()`: Converts to `datetime.datetime`

**Important comparison rule:** "Date fields can only be compared to date objects; datetime fields only to datetime objects."

Datetimes are stored as `timestamp without timezone` in UTC, with timezone conversion handled client-side.

Both field types provide helper methods: `today()`, `context_today()`, `now()`, `to_date()`/`to_datetime()`, `to_string()`, `start_of()`, `end_of()`, `add()`, and `subtract()`.

### Relational Fields

- **Many2one**: Many records reference one (foreign key)
- **One2many**: One record has many child records
- **Many2many**: Many-to-many bidirectional relationships
- **Command**: Helper class for modifying relational fields

### Pseudo-Relational Fields

- **Reference**: Generic reference to any model via stored model name and record ID
- **Many2oneReference**: Polymorphic many-to-one relationships

### Computed Fields

Computed fields derive values from other fields using the `compute` parameter:

```python
from odoo import api

total = fields.Float(compute='_compute_total')

@api.depends('value', 'tax')
def _compute_total(self):
    for record in self:
        record.total = record.value + record.value * record.tax
```

**Dependency specification:** Use `@api.depends()` decorator with field names; supports dotted paths for subfields:

```python
@api.depends('line_ids.value')
def _compute_total(self):
    for record in self:
        record.total = sum(line.value for line in record.line_ids)
```

**Storage:** By default not stored; set `store=True` to persist to database and enable searching

**Search:** Enable searching via `search` parameter with a method returning a domain

**Inverse:** Allow writing to computed fields via `inverse` parameter:

```python
document = fields.Char(compute='_get_document', inverse='_set_document')

def _get_document(self):
    for record in self:
        with open(record.get_document_path) as f:
            record.document = f.read()

def _set_document(self):
    for record in self:
        if not record.document:
            continue
        with open(record.get_document_path()) as f:
            f.write(record.document)
```

**Warning:** Using a single inverse method for multiple fields is not recommended due to field protection during inverse computation.

### Related Fields

Related fields provide proxy access to subfield values:

```python
nickname = fields.Char(related='user_id.partner_id.name', store=True)
```

Related fields automatically copy attributes (`string`, `help`, `required`, `groups`, `digits`, `size`, `translate`, `sanitize`, `selection`, `comodel_name`, `domain`, `context`) from source fields.

**Characteristics:**
- Not stored by default
- Not copied
- Readonly
- Computed in superuser mode

Add `store=True` to persist related fields. Use `depends` parameter to specify precise dependencies:

```python
nickname = fields.Char(
    related='partner_id.name', store=True,
    depends=['partner_id'])
```

**Limitations:** Cannot chain Many2many or One2many fields in related dependencies.

### Automatic Fields

**`id`**: Integer identifier field; returns record ID if recordset contains single record, otherwise raises error

**`display_name`**: Name field displayed by default in web client; equals `_rec_name` value by default but customizable via `_compute_display_name` override

### Access Log Fields

Automatically maintained when `_log_access` is enabled (defaults to `_auto` value):

**`create_date`**: Datetime when record was created

**`create_uid`**: Many2one to `res.users` identifying creator

**`write_date`**: Datetime of last update

**`write_uid`**: Many2one to `res.users` identifying last updater

**Warning:** `_log_access` must be enabled on TransientModel

### Reserved Field Names

**`name`**: Default `_rec_name` value; Char field

**`active`**: Boolean field toggling record visibility; when false, record hidden from most searches. Special methods: `action_archive()`, `action_unarchive()`

**`state`**: Selection field for lifecycle stages; used by `states` attribute on other fields

**`parent_id`**: Many2one field for hierarchical tree structures; default `_parent_name` value; enables `child_of` and `parent_of` domain operators

**`parent_path`**: Char field storing tree structure when `_parent_store=True`; must be declared with `index=True`

**`company_id`**: Many2one to `res.company` implementing multi-company behavior; used by `_check_company()` validation

## Constraints and Indexes

```python
class AModel(models.Model):
    _name = 'a.model'
    _my_check = models.Constraint("CHECK (x > y)", "x > y is not true")
    _name_idx = models.Index("(last_name, first_name)")
```

Error messages can be strings (automatically translated) or functions accepting `(env, diag)` parameters.

## Recordsets

Recordsets are ordered collections of records from a single model. Methods execute on recordsets with `self` as a recordset:

```python
class AModel(models.Model):
    _name = 'a.model'

    def a_method(self):
        # self can contain 0 to all records
        self.do_operation()
```

Iterating yields single-record "singleton" recordsets:

```python
def do_operation(self):
    print(self)  # => a.model(1, 2, 3, 4, 5)
    for record in self:
        print(record)  # => a.model(1), then a.model(2), etc.
```

### Field Access

Model fields provide "Active Record" interface:

```python
record.name
record.company_id.name
record.name = "Bob"
field = "name"
record[field]  # => "Bob"
```

For non-relational fields on multi-record sets, use `mapped()`:

```python
total_qty = sum(self.mapped('qty'))
```

Relational fields always return recordsets, empty if unset.

**Warning:** Reading non-relational fields on multi-record sets raises error

### Record Cache and Prefetching

Odoo caches field values to avoid repeated database queries. When reading one field on one record, the ORM actually reads that field on a larger recordset. All simple stored fields fetch together in one query.

Example with 1000 partners:

```python
for partner in partners:
    print partner.name  # Prefetches 'name' on all partners
    print partner.lang
```

Methods `search_fetch()` and `fetch()` can populate caches in cases where prefetching doesn't work optimally.

## Method Decorators

### `@api.depends(*args)`

Declares field dependencies for computed fields; supports dotted paths for subfield dependencies

### `@api.depends_context(*keys)`

Declares context key dependencies

### `@api.constrains(*fields)`

Marks method as constraint validator; executed when specified fields change

### `@api.onchange(*fields)`

Marks method as view-side handler; triggers on field changes in forms

### `@api.autovacuum`

Marks method for automatic invocation by vacuum mechanism

### `@api.model`

Marks method as model-level (not record-level)

### `@api.model_create_multi`

Marks method for batch creation

### `@api.private`

Restricts method to internal use

### `@api.ondelete`

Marks method as deletion handler; invoked before record deletion

## Environment

The Environment object provides access to contextual data and utilities:

```python
records.env  # => <Environment object ...>
records.env.uid  # => 3
records.env.user  # => res.user(3)
records.env.cr  # => <Cursor object ...>
```

Access empty recordsets and query models:

```python
self.env['res.partner']
self.env['res.partner'].search([('is_company', '=', True)])
```

### Environment Properties

**`lang`**: Current language code

**`user`**: Current user record

**`company`**: Current company record

**`companies`**: All companies accessible to current user

### Useful Methods

**`Environment.ref(xml_id)`**: Retrieve record by XML ID

**`Environment.is_superuser()`**: Check superuser status

**`Environment.is_admin()`**: Check admin status

**`Environment.is_system()`**: Check system status

**`Environment.execute_query(query, params, *, tuple_=False, debug=False)`**: Execute raw SQL with result processing

### Altering the Environment

**`Model.with_context(**kwargs)`**: Return recordset copy with modified context

**`Model.with_user(user)`**: Return recordset copy with different user

**`Model.with_company(company)`**: Return recordset copy with different company

**`Model.with_env(env)`**: Return recordset copy with different environment

**`Model.sudo(user=None)`**: Return recordset with superuser privileges (or specified user)

## SQL Execution

Execute SQL via the environment cursor for complex queries or performance reasons:

```python
self.env.cr.execute("some_sql", params)
```

**Warning:** Raw SQL bypasses ORM security rules; sanitize user input and prefer ORM utilities when possible

Build SQL safely using the `SQL` wrapper:

```python
from odoo.tools import SQL

SQL.join(items, separator=', ')
SQL.identifier('table_name')
```

### Flushing

Before querying, flush relevant data to ensure database consistency.

**`Environment.flush_all()`**: Flush all pending updates

**`Model.flush_model(fnames)`**: Flush specific fields on all records of model

**`Model.flush_recordset(fnames)`**: Flush specific fields on specific records

Example:

```python
self.env['model'].flush_model(['partner_id'])
self.env.cr.execute(SQL("SELECT id FROM model WHERE partner_id IN %s", ids))
```

### Cache Invalidation

After raw SQL `CREATE`, `UPDATE`, or `DELETE`, invalidate caches:

**`Environment.invalidate_all()`**: Clear all caches

**`Model.invalidate_model(fnames)`**: Invalidate fields on all records of model

**`Model.invalidate_recordset(fnames)`**: Invalidate fields on specific records

### Notifying Field Changes

Use `modified()` to notify framework of computed field dependency updates:

```python
self.env['model'].flush_model(['state'])
self.env.cr.execute("UPDATE model SET state=%s WHERE state=%s RETURNING id",
                    ['new', 'old'])
ids = [row[0] for row in self.env.cr.fetchall()]

records = self.env['model'].browse(ids)
records.invalidate_recordset(['state'])
records.modified(['state'])
```

## Common ORM Methods

### Create/Update

**`Model.create(vals_list)`**: Create new records from list of field value dictionaries

**`Model.copy(default=None)`**: Duplicate record with optional field value overrides

**`Model.default_get(fields_list)`**: Get default values for specified fields

**`Model.name_create(name)`**: Create record with just name field; returns tuple of ID and name

**`Model.write(vals)`**: Update multiple records with field value dictionary

### Search/Read

**`Model.browse(ids)`**: Get recordset of specified record IDs

**`Model.search(domain, offset=0, limit=None, order=None, count=False)`**: Find records matching domain

**`Model.search_count(domain)`**: Count records matching domain without fetching

**`Model.search_fetch(domain, fields, offset=0, limit=None, order=None)`**: Search and read in single operation

**`Model.name_search(name='', args=None, operator='ilike', limit=100)`**: Search by name field

**`Model.fetch(fnames)`**: Fetch specified fields on recordset from database

**`Model.read(fields=None)`**: Return list of dictionaries with field values

**`Model.fields_get(allfields=None, attributes=None)`**: Get field definitions

### Unlink

**`Model.unlink()`**: Delete records in recordset

### Recordset Information

**`Model.ids`**: List of record IDs in recordset

**`Model.env`**: Environment of recordset

**`Model.exists()`**: Return recordset of records still in database

**`Model.ensure_one()`**: Verify recordset contains exactly one record; raise error otherwise

**`Model.get_metadata()`**: Get metadata dictionary with access information

## Recordset Operations

Recordsets are immutable but support set operations:

- `record in set`: Check membership
- `set1 <= set2`: Subset check
- `set1 < set2`: Strict subset check
- `set1 >= set2`: Superset check
- `set1 > set2`: Strict superset check
- `set1 | set2`: Union (all records from both)
- `set1 & set2`: Intersection (records in both)
- `set1 - set2`: Difference (records in first but not second)

### Filter

**`Model.filtered(func)`**: Return recordset with records matching predicate function

**`Model.filtered_domain(domain)`**: Return recordset matching domain

### Map

**`Model.mapped(func_or_field)`**: Transform recordset via function or field name; returns list or recordset

```python
records.partner_id  # == records.mapped('partner_id')
records.partner_id.bank_ids  # == records.mapped('partner_id.bank_ids')
records.partner_id.mapped('name')  # == records.mapped('partner_id.name')
```

### Sort

**`Model.sorted(key=None, reverse=False)`**: Return recordset sorted by key or field

### Grouping

**`Model.grouped(key)`**: Return dictionary grouping records by key

## Search Domains

Use `Domain` class for construction:

```python
from odoo.fields import Domain

d1 = Domain('name', '=', 'abc')
d2 = Domain('phone', 'like', '7620')

d3 = d1 & d2  # AND
d4 = d1 | d2  # OR
d5 = ~d1      # NOT

Domain.AND([d1, d2, d3, ...])
Domain.OR([d4, d5, ...])
Domain.TRUE
Domain.FALSE
```

### Domain Conditions

A simple condition is `(field_expr, operator, value)`:

**`field_expr`**: Field name, relationship traversal via dot notation (e.g., `partner_id.country`), or date granularity (e.g., `field_name.month_number`). Supported granularities: `year_number`, `quarter_number`, `month_number`, `iso_week_number`, `day_of_week`, `day_of_month`, `day_of_year`, `hour_number`, `minute_number`, `second_number`.

**Operators:**

- `=`: Equals
- `!=`: Not equals
- `>`, `>=`, `<`, `<=`: Comparisons
- `=?`: Unset or equals (true if None/False, else like `=`)
- `=like`, `not =like`: Pattern match with _ (any char) and % (zero+ chars)
- `like`, `not like`: Wraps value with % for substring match
- `ilike`, `not ilike`: Case-insensitive like
- `=ilike`, `not =ilike`: Case-insensitive =like
- `in`, `not in`: Equals any item in collection
- `child_of`: Child (descendant) of value (follows `_parent_name`)
- `parent_of`: Parent (ascendant) of value (follows `_parent_name`)
- `any`, `not any`: Matches if any related record satisfies subdomain
- `any!`, `not any!`: Like `any` but bypasses access checks

### Domain Examples

```python
Domain('name', '=', 'ABC') & (
    Domain('phone', 'ilike', '7620') | Domain('mobile', 'ilike', '7620')
)

Domain('invoice_status', '=', 'to invoice') \
    & Domain('order_line', 'any', Domain('product_id.qty_available', '<=', 0))

Domain('birthday.month_number', '=', 2)
```

### Domain Serialization

```python
domain = Domain([('name', '=', 'abc'), ('phone', 'like', '7620')])
domain_list = list(domain)
# ['&', ('name', '=', 'abc'), ('phone', 'like', '7620')]
```

### Domain Methods

**`Domain.iter_conditions()`**: Iterate over simple conditions

**`Domain.map_conditions(func)`**: Transform conditions via function

**`Domain.optimize()`**: Simplify domain structure

**`Domain.validate(domain_list)`**: Validate domain format

### Dynamic Time Values

For date/datetime field values in domains, use relative time specifications:

Optional first term: "today" (midnight) or "now"

Following terms: "+"/"-"/"=" followed by integer and unit or weekday

Units: "d" (days), "w" (weeks), "m" (months), "y" (years), "H" (hours), "M" (minutes), "S" (seconds)

Weekdays: "+" = next, "-" = previous, "=" = in current week (Monday start)

```python
Domain('some_date', '<', 'now')             # Now
Domain('some_date', '<', 'today')           # Today at midnight
Domain('some_date', '<', '-3d +1H')         # Now - 3 days + 1 hour
Domain('some_date', '<', '=3H')             # Today at 3:00:00
Domain('some_date', '<', '=5d')             # 5th of month at midnight
Domain('some_date', '<', '=1m')             # January, same day at midnight
Domain('some_date', '>=', '=monday -1w')    # Previous Monday
```

## Model Inheritance

Odoo provides three inheritance mechanisms for modular extension.

### Classical Inheritance

Using `_inherit` and `_name` together creates a new model based on existing one:

```python
class Inheritance0(models.Model):
    _name = 'inheritance.0'
    _description = 'Inheritance Zero'

    name = fields.Char()

    def call(self):
        return self.check("model 0")

    def check(self, s):
        return "This is {} record {}".format(s, self.name)

class Inheritance1(models.Model):
    _name = 'inheritance.1'
    _inherit = ['inheritance.0']
    _description = 'Inheritance One'

    def call(self):
        return self.check("model 1")
```

### Extension

Using `_inherit` without `_name` extends existing model in-place:

```python
class Extension0(models.Model):
    _name = 'extension.0'
    _description = 'Extension zero'

    name = fields.Char(default="A")

class Extension0(models.Model):
    _inherit = 'extension.0'
    description = fields.Char(default="Extended")
```

**Note:** When `_inherit` is string, `_name` defaults to same value unless explicitly set

### Delegation

Using `_inherits` dictionary delegates field lookup to child models via automatically-created Reference fields. Implements composition ("has one") rather than inheritance ("is one"):

```python
class Laptop(models.Model):
    _name = 'delegation.laptop'
    _description = 'Laptop'

    _inherits = {
        'delegation.screen': 'screen_id',
        'delegation.keyboard': 'keyboard_id',
    }

    name = fields.Char(string='Name')
    maker = fields.Char(string='Maker')

    screen_id = fields.Many2one('delegation.screen', required=True, ondelete="cascade")
    keyboard_id = fields.Many2one('delegation.keyboard', required=True, ondelete="cascade")
```

**Warning:** Methods not inherited with delegation, only fields

**Warning:** `_inherits` poorly implemented; avoid when possible.

### Fields Incremental Definition

Redefine fields in subclasses to override attributes while preserving parent definitions:

```python
class FirstFoo(models.Model):
    _inherit = ['first.foo']
    state = fields.Selection(help="Blah blah blah")
```

## Error Management

**`AccessDenied`**: Access violation exception

**`AccessError`**: User lacks permissions for operation

**`CacheMiss`**: Requested data not in cache

**`MissingError`**: Referenced record doesn't exist

**`RedirectWarning`**: Warning directing user to alternative action

**`UserError`**: User-facing validation or operational error

**`ValidationError`**: Record validation failure
