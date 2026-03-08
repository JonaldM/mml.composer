# Actions

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html
> Fetched: 2026-03-07

Actions define the system's behavior in response to user interactions such as login, button clicks, or invoice selection.

Actions can be stored in the database or returned as dictionaries in methods. All actions require two mandatory attributes:

- `type`: Determines the action category and which fields may be used
- `name`: A short user-readable description

## Client Action Forms

A client can receive actions in four formats:

- `False`: Close any open action dialog
- String: Interpreted as a client action tag or number
- Number: Read the corresponding action record from the database
- Dictionary: Treat as a client action descriptor and execute

## Bindings

Beyond the two mandatory attributes, actions include optional attributes for presenting actions in contextual menus:

- `binding_model_id`: Specifies which model the action binds to
- `binding_type`: Specifies the contextual menu location
  - `action` (default): Appears in the Action menu
  - `report`: Appears in the Print menu
- `binding_view_types`: Comma-separated list of view types (defaults to "list,form")

## Window Actions (`ir.actions.act_window`)

The most common action type, presenting model visualizations through views.

**Fields:**

- `res_model`: The model to present views for
- `views`: List of `(view_id, view_type)` pairs
- `res_id` (optional): Record to load if default view is form
- `search_view_id` (optional): Specific search view to load
- `target` (optional): Opening mode — `current`, `fullscreen`, `new`, or `main`
- `context` (optional): Additional context data
- `domain` (optional): Filtering domain for searches
- `limit` (optional): Records to display per page (defaults to 80)

**Example — opening customers:**

```python
{
    "type": "ir.actions.act_window",
    "res_model": "res.partner",
    "views": [[False, "list"], [False, "form"]],
    "domain": [["customer", "=", true]],
}
```

**Example — opening a product form in a dialog:**

```python
{
    "type": "ir.actions.act_window",
    "res_model": "product.product",
    "views": [[False, "form"]],
    "res_id": a_product_id,
    "target": "new",
}
```

### In-Database Window Actions

Database-stored window actions include additional fields for composing the `views` list:

- `view_mode`: Comma-separated string of view types (no spaces)
- `view_ids`: M2M to view objects defining initial `views` content
- `view_id`: Specific view added to `views` if its type is in `view_mode`

**XML example:**

```xml
<record model="ir.actions.act_window" id="test_action">
    <field name="name">A Test Action</field>
    <field name="res_model">some.model</field>
    <field name="view_mode">graph</field>
    <field name="view_id" ref="my_specific_view"/>
</record>
```

The server-side composition process:

1. Get each `(id, type)` from `view_ids` (ordered by sequence)
2. If `view_id` is defined and its type isn't filled, append it
3. For each unfilled type in `view_mode`, append `(False, type)`

## URL Actions (`ir.actions.act_url`)

Opens a URL via an Odoo action.

**Fields:**

- `url`: The address to open
- `target` (default=`new`): Opening behaviour
  - `new`: Opens in a new window/page
  - `self`: Opens in the current window/page
  - `download`: Redirects to a download URL

**Example:**

```python
{
    "type": "ir.actions.act_url",
    "url": "https://odoo.com",
    "target": "self",
}
```

## Server Actions (`ir.actions.server`)

Trigger complex server code from valid action locations.

**Client-relevant fields:**

- `id`: In-database identifier of the server action
- `context` (optional): Context data when running the action

### Server Action States

The `state` field defines behaviour:

- `code`: Executes Python code from the `code` field
- `object_create`: Creates a new record per `fields_lines` specifications
- `object_write`: Updates current record(s) per `fields_lines`
- `multi`: Executes multiple actions from `child_ids`

### Code State Example

```xml
<record model="ir.actions.server" id="print_instance">
    <field name="name">Res Partner Server Action</field>
    <field name="model_id" ref="model_res_partner"/>
    <field name="state">code</field>
    <field name="code">
        raise Warning(record.name)
    </field>
</record>
```

Code can define an `action` variable returned to the client:

```xml
<record model="ir.actions.server" id="print_instance">
    <field name="name">Res Partner Server Action</field>
    <field name="model_id" ref="model_res_partner"/>
    <field name="state">code</field>
    <field name="code">
        if record.some_condition():
            action = {
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": record._name,
                "res_id": record.id,
            }
    </field>
</record>
```

### State Fields

- `code` (code): Python code to execute
- `crud_model_id` (create, required): Model for record creation
- `link_field_id` (create): M2O field linking new record to current record
- `fields_lines` (create/write): Fields to override with `col1`, `value`, and `type` subfields
- `child_ids` (multi): Sub-actions to execute

### Evaluation Context

Available context keys:

- `model`: Model object linked via `model_id`
- `record`/`records`: Record/recordset triggering the action
- `env`: Odoo Environment
- `datetime`, `dateutil`, `time`, `timezone`: Corresponding Python modules
- `log`: Logging function for debug information
- `Warning`: Warning exception constructor

## Report Actions (`ir.actions.report`)

Triggers report printing.

**Fields:**

- `name` (mandatory): File name if `print_report_name` is unspecified
- `model` (mandatory): Report subject model
- `report_type` (default=qweb-pdf): `qweb-pdf` or `qweb-html`
- `report_name` (mandatory): External id of the qweb template
- `print_report_name`: Python expression defining the report name
- `groups_id`: Many2many field restricting access
- `multi`: If True, not displayed on form views
- `paperformat_id`: Paper format to use
- `attachment_use`: If True, report generated once then re-printed
- `attachment`: Python expression defining the report name

## Client Actions (`ir.actions.client`)

Triggers client-implemented actions.

**Fields:**

- `tag`: Client-side action identifier string
- `params` (optional): Python dictionary of additional data
- `target` (optional): Opening mode — `current`, `fullscreen`, `new`, or `main`

**Example:**

```python
{
    "type": "ir.actions.client",
    "tag": "pos.ui"
}
```

## Scheduled Actions (`ir.cron`)

Actions triggered automatically at predefined frequencies.

**Fields:**

- `name`: Scheduled action name
- `interval_number`: Number of interval units between executions
- `interval_type`: Unit of frequency (minutes, hours, days, weeks, months)
- `model_id`: Model for the action
- `code`: Python code content, such as model method calls
- `nextcall`: Next planned execution date/time
- `priority`: Execution priority when multiple actions run

### Writing Cron Functions

Batch processing is recommended to avoid blocking workers:

```python
def _cron_do_something(self, *, limit=300):
    domain = [('state', '=', 'ready')]
    records = self.search(domain, limit=limit)
    records.do_something()
    remaining = 0 if len(records) == limit else self.search_count(domain)
    self.env['ir.cron']._commit_progress(len(records), remaining=remaining)
```

For managing loops with exceptions:

```python
def _cron_do_something(self):
    assert self.env.context.get('cron_id'), "Run only inside cron jobs"
    domain = [('state', '=', 'ready')]
    records = self.search(domain)
    self.env['ir.cron']._commit_progress(remaining=len(records))

    with open_some_connection() as conn:
        for record in records:
            record = record.try_lock_for_update().filtered_domain(domain)
            if not record:
                continue
            try:
                record.do_something(conn)
                if not self.env['ir.cron']._commit_progress(1):
                    break
            except Exception:
                self.env.cr.rollback()
                _logger.warning(...)
```

### Running Cron Functions

Do not call cron functions directly. Use:

- `IrCron.method_direct_trigger`: For direct execution
- `IrCron._trigger`: For framework execution

Testing should use `method_direct_trigger` in registry test mode.

### Security Measures

- Three consecutive errors/timeouts cause the action to skip execution and be marked failed
- Five failures over at least seven days cause deactivation with admin notification
- Hard database-level execution limits prevent process timeout
