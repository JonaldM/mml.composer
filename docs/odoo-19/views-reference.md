# View Architectures

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/views.html
> Fetched: 2026-03-07

## Generic Architecture

The architecture of a view is defined by XML data interpreted by the JavaScript framework. Most views have a `.rng` file defining attributes and possible architectures.

## Python Expression

When evaluating node attributes like `readonly`, you can provide a Python expression with access to:

- All field names in the current view with record values
- Current record ID
- `parent`: the referencing record in sub-views
- `context (dict)`: the current view's context
- `uid (int)`: current user ID
- `today (str)`: current date in `YYYY-MM-DD` format
- `now (str)`: current datetime in `YYYY-MM-DD hh:mm:ss` format

Example usage:
```xml
<field name="field_b" invisible="context.get('show_me') and field_a == 4"/>
```

## Form

Form views display single record data with HTML and semantic components.

### Root Attributes

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | `''` | View title |
| `create` | bool | `True` | Enable record creation |
| `edit` | bool | `True` | Enable record editing |
| `duplicate` | bool | `True` | Enable record duplication |
| `delete` | bool | `True` | Enable record deletion |
| `js_class` | str | `''` | Custom JavaScript component |
| `disable_autofocus` | bool | `False` | Disable auto-focus on first field |

### Semantic Components

#### `field`: Display Field Values

Renders a single field for viewing/editing:

```xml
<form>
    <field name="FIELD_NAME"/>
</form>
```

**Field Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `id` | str | Field name | Node ID for multiple occurrences |
| `string` | str | Field label | Custom label |
| `help` | str | `''` | Tooltip text |
| `options` | Python expr | `{}` | Widget configuration |
| `readonly` | Python expr | `False` | Make field read-only |
| `required` | Python expr | `False` | Make field required |
| `invisible` | Python expr | `False` | Hide field |
| `groups` | str | `''` | Access groups |
| `domain` | Python expr | `[]` | Relational field filters |
| `context` | Python expr | `{}` | Relational field context |
| `nolabel` | bool | `False` | Hide label (group children only) |
| `placeholder` | str | `''` | Help message for empty fields |
| `mode` | str | `list` | Display modes (list, form, kanban, graph) |
| `class` | str | `''` | HTML classes |
| `filename` | str | `''` | Binary field file name field |
| `password` | bool | `False` | Hide password field data |
| `kanban_view_ref` | str | `''` | Mobile kanban view XMLID |
| `default_focus` | bool | `False` | Focus on view open |

#### `label`: Display Field Labels

Manual label display for fields not in groups:

```xml
<label for="FIELD_NAME" string="LABEL"/>
```

**Attributes:**

| Attribute | Type | Purpose |
|-----------|------|---------|
| `for` | str | Field name or ID (mandatory) |
| `string` | str | Custom label text |
| `class` | str | HTML classes |
| `invisible` | Python expr | Hide condition |

#### `button`: Display Action Buttons

```xml
<button type="object" name="ACTION" string="LABEL"/>
<button type="object" name="ACTION" icon="FONT_AWESOME"/>
```

**Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `type` | str | Required | Button type (object, action) |
| `name` | str | Required | Action name |
| `string` | str | `''` | Button label |
| `icon` | str | `''` | Font Awesome icon |
| `help` | str | `''` | Tooltip |
| `context` | Python expr | `{}` | Action context |
| `groups` | str | `''` | Access groups |
| `invisible` | Python expr | `False` | Hide condition |
| `class` | str | `''` | HTML classes |
| `special` | str | `''` | Dialog behaviour (save, cancel) |
| `confirm` | str | `''` | Confirmation message |
| `data-hotkey` | str | `''` | Keyboard shortcut |

#### Chatter Widget

Communication and logging tool for mail.thread models:

```xml
<div class="oe_chatter">
    <field name="message_follower_ids"/>
    <field name="activity_ids"/>
    <field name="message_ids" options="OPTIONS"/>
</div>
```

#### Attachments Preview Widget

```xml
<div class="o_attachment_preview"/>
```

### Structural Components

#### `group`: Define Column Layouts

Two-column layout by default:

```xml
<group>
    <field name="a"/>
    <field name="b"/>
</group>
```

**Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | `''` | Group title |
| `col` | int | `2` | Number of columns |
| `colspan` | int | `1` | Child column span |
| `invisible` | Python expr | `False` | Hide condition |

#### `sheet`: Responsive Layout

Narrower, centred layout with margins:

```xml
<form>
    <sheet>
        ...
    </sheet>
</form>
```

#### `notebook` and `page`: Tabbed Sections

```xml
<form>
    <notebook>
        <page string="LABEL">
            ...
        </page>
    </notebook>
</form>
```

**Page Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | `''` | Tab title |
| `invisible` | Python expr | `False` | Hide condition |

#### `newline`: Start New Group Rows

Ends current row without filling remaining columns:

```xml
<group>
    <field name="a"/>
    <newline/>
    <field name="b"/>
</group>
```

#### `separator`: Add Horizontal Spacing

```xml
<separator string="Title"/>
```

#### `header`: Display Workflow Buttons

Full-width section above sheet:

```xml
<form>
    <header>
        <button string="Reset" type="object" name="set_draft"/>
        <field name="state" widget="statusbar"/>
    </header>
    <sheet>...</sheet>
</form>
```

#### `footer`: Display Dialog Buttons

```xml
<form>
    <sheet>...</sheet>
    <footer>
        <button string="Save" special="save"/>
        <button string="Discard" special="cancel"/>
    </footer>
</form>
```

**Footer Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `replace` | bool | `True` | Replace vs. add to default buttons |

#### Buttons Container

```xml
<div name="button_box">
    <BUTTONS/>
</div>
```

#### Title Container

```xml
<div class="oe_title">
    <h1><FIELD/></h1>
</div>
```

## Settings

Settings views customise the form view with centralised display, search bar, and sidebar.

```xml
<app string="CRM" name="crm">
    <setting type="header" string="Foo">
        <field name="foo" title="Foo?."/>
        <button name="nameAction" type="object" string="Button"/>
    </setting>
    <block title="Title of group Bar">
        <setting help="this is bar">
            <field name="bar"/>
        </setting>
    </block>
</app>
```

### Components

#### `app`: Declare Application

| Attribute | Type | Requirement |
|-----------|------|-------------|
| `string` | str | Mandatory |
| `name` | str | Mandatory |
| `logo` | path | Optional |
| `groups` | str | Optional |
| `invisible` | Python expr | Optional |

#### `block`: Declare Settings Group

| Attribute | Type | Default |
|-----------|------|---------|
| `title` | str | `''` |
| `help` | str | `''` |
| `groups` | str | `''` |
| `invisible` | Python expr | `False` |

#### `setting`: Declare Setting

The first field becomes the main field. Boolean fields appear left-aligned; others appear top-right.

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `type` | str | `''` | `header` for scope modifier |
| `string` | str | First field label | Setting label |
| `title` | str | `''` | Tooltip |
| `help` | str | `''` | Description |
| `company_dependent` | str | `''` | Company-specific (value: '1') |
| `documentation` | path | `''` | Documentation link |
| `groups` | str | `''` | Access groups |
| `invisible` | Python expr | `False` | Hide condition |

## List

Lists display records as rows in a table.

### Root Attributes

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | `''` | View title |
| `create` | bool | `True` | Enable creation |
| `edit` | bool | `True` | Enable editing |
| `delete` | bool | `True` | Enable deletion |
| `import` | bool | `True` | Enable import |
| `export_xlsx` | bool | `True` | Enable export |
| `editable` | str | `''` | In-place editing (top, bottom) |
| `multi_edit` | str | `''` | Multi-editing (value: '1') |
| `open_form_view` | bool | `False` | Show open button |
| `default_group_by` | str | `''` | Default grouping field |
| `default_order` | str | `''` | Default ordering |
| `decoration-<style>` | Python expr | `False` | Row styling |
| `limit` | int | 80 | Default page size |
| `groups_limit` | int | 80 | Groups per page |
| `expand` | bool | `False` | Open groups by default |
| `sample` | str | `''` | Sample data indicator |

### Components

#### `field`: Display Field Values

Renders column for field across all records:

```xml
<list>
    <field name="FIELD_NAME"/>
</list>
```

**Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `string` | str | Field label | Column header |
| `optional` | str | Required | show/hide default |
| `readonly` | Python expr | `False` | Read-only |
| `required` | Python expr | `False` | Required |
| `invisible` | Python expr | `False` | Hide field |
| `column_invisible` | Python expr | `False` | Hide column |
| `groups` | str | `''` | Access groups |
| `decoration-<style>` | Python expr | `False` | Cell styling |
| `sum` | str | `''` | Sum aggregation label |
| `avg` | str | `''` | Average aggregation label |
| `width` | str | `''` | Column width (pixels) |
| `nolabel` | str | `''` | Empty header (value: '1') |

#### `groupby`: Define Group Headers

Used with Many2one field grouping:

```xml
<groupby name="FIELD_NAME">
    <button type="edit" name="edit" icon="fa-edit"/>
    <field name="email"/>
</groupby>
```

#### `header`: Display Workflow Buttons

```xml
<header>
    <button type="object" name="to_draft" string="Button1" display="always"/>
</header>
```

Button `display` attribute:
- `always`: Always visible
- (default): Only with selection

#### `control`: Customise Create/Delete

For One2many and Many2many fields only:

```xml
<control>
    <create string="LABEL"/>
    <create string="Add a section" context="{'default_type': 'section'}"/>
    <delete invisible="parent.is_sent"/>
</control>
```

**Create Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | Required | Button text |
| `context` | Python expr | `{}` | Merged context |
| `invisible` | Python expr | `False` | Hide condition |

## Search

Search views filter other views' content (list, graph).

```xml
<search>
    ...
</search>
```

### Components

#### `field`: Filter on Field Values

```xml
<field name="FIELD_NAME"/>
```

**Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `string` | str | Field label | Display label |
| `operator` | str | `=` | Domain operator |
| `filter_domain` | Python expr | `[]` | Custom domain |
| `context` | Python expr | `{}` | Context |
| `domain` | Python expr | `[]` | Auto-completion filter |
| `groups` | str | `''` | Access groups |
| `invisible` | Python expr | `False` | Hide condition |

#### `filter`: Create Pre-defined Filters

```xml
<filter string="LABEL" domain="DOMAIN"/>
```

**Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Filter name |
| `string` | str | Required | Filter label |
| `help` | str | `''` | Tooltip |
| `domain` | Python expr | `[]` | Domain |
| `date` | str | `''` | Date/datetime field |
| `start_month` | int | -2 | Earliest month offset |
| `end_month` | int | 0 | Latest month offset |
| `start_year` | int | -2 | Earliest year offset |
| `end_year` | int | 0 | Latest year offset |
| `default_period` | str | month | Default time period |
| `invisible` | Python expr | `False` | Hide condition |
| `groups` | str | `''` | Access groups |
| `context` | Python expr | `{}` | Context (group_by) |

#### `searchpanel`: Display Search Panels

Left sidebar filtering:

```xml
<searchpanel>
    <field name="FIELD_NAME"/>
</searchpanel>
```

**Field Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `string` | str | Field label | Display label |
| `select` | str | `one` | one/multi selection |
| `groups` | str | `''` | Access groups |
| `icon` | str | `''` | Icon |
| `color` | str | `''` | Color |
| `hierarchize` | bool | `True` | Category nesting |
| `depth` | int | 0 | Unfold hierarchy levels |
| `enable_counters` | bool | `False` | Show record counts |
| `expand` | bool | `False` | Show empty values |
| `limit` | int | 200 | Max values to fetch |
| `domain` | Python expr | `[]` | Value conditions |
| `groupby` | str | `''` | Group field name |

### Search Defaults

Set via action context `search_default_{name}`:

```python
{
    'search_default_foo': 'search_value',
    'search_default_bar': 1
}
```

Numeric values (1-99) order groupby filters.

## Kanban

Kanban views display records as cards, optionally grouped in columns.

### Root Attributes

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `string` | str | `''` | View title |
| `create` | bool | `True` | Enable creation |
| `edit` | bool | `True` | Enable editing |
| `delete` | bool | `True` | Enable deletion |
| `default_group_by` | str | `''` | Default grouping |
| `default_order` | str | `''` | Default ordering |
| `class` | str | `''` | HTML classes |
| `examples` | str | `''` | Example registry key |
| `group_create` | bool | `True` | Show add column bar |
| `group_delete` | bool | `True` | Allow column delete |
| `group_edit` | bool | `True` | Allow column edit |
| `groups_draggable` | bool | `True` | Allow column reorder |
| `records_draggable` | bool | `True` | Allow record drag |
| `archivable` | bool | `True` | Allow archive/unarchive |
| `quick_create` | bool | True (grouped) | Enable quick create |
| `quick_create_view` | str | `''` | Quick create form view |
| `on_create` | str | `''` | Custom create action |
| `can_open` | bool | `True` | Allow card open |
| `highlight_color` | str | Optional | Color field |
| `sample` | str | `''` | Sample indicator |

### Components

#### `templates`: Define Card Structure

QWeb templates defining card layout:

```xml
<templates>
    <t t-name="card">
        <field name="name"/>
    </t>
</templates>
```

**Rendering Context Variables:**

- `record`: Object with field values (value, raw_value)
- `widget`: Object with editable/deletable flags
- `context`: Current view context
- `read_only_mode`: Boolean
- `selection_mode`: Boolean (mobile)
- `luxon`: Date/time library
- `JSON`: JSON namespace

**Button/Link Types:**

- `open`: Open record form
- `delete`: Delete record
- `archive`: Archive record
- `unarchive`: Unarchive record
- `set_cover`: Select cover image
- `action`: Execute action
- `object`: Call method

**Card Layouts:**

Default flexbox column layout. Use Bootstrap utility classes for styling:

- `footer`: Sticks to bottom, flexbox row
- `aside` + `main`: Side-by-side layout
- `o_kanban_aside_full`: Remove aside padding

#### `progressbar`: Show Column Progress Bars

```xml
<progressbar field="FIELD_NAME"
             colors="{'value1': 'success', 'value2': 'danger'}"
             sum_field="amount"/>
```

**Attributes:**

| Attribute | Type | Purpose |
|-----------|------|---------|
| `field` | str | Progress field name (mandatory) |
| `colors` | JSON | Value-to-color mapping (mandatory) |
| `sum_field` | str | Sum field for progress (optional) |

## QWeb

QWeb views are standard QWeb templates inside a view's `arch`. The type must be specified explicitly.

Used for frontend templates or custom views. Adds items to rendering context:

- `model`: View's model
- `domain`: Search domain
- `context`: Search context
- `records`: Lazy search proxy
- `luxon`: Date library
- `JSON`: JSON namespace

## Graph

Aggregation visualisation with bar/pie/line charts.

```xml
<graph type="bar" stacked="1">
    <field name="amount" type="measure"/>
</graph>
```

**Root Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `type` | str | `bar` | Chart type (bar, pie, line) |
| `stacked` | bool | `True` | Stack bars |
| `disable_linking` | bool | `False` | Prevent list redirect |
| `order` | str | Optional | X-axis sort (asc, desc) |
| `string` | str | Optional | Breadcrumb text |
| `sample` | str | `''` | Sample indicator |

**Field Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `invisible` | bool | `False` | Hide field |
| `type` | str | Optional | `measure` for aggregation |
| `interval` | str | month | Date grouping (day, week, month, quarter, year) |
| `string` | str | Field label | Measure label |
| `widget` | str | Optional | Format widget (float_time, monetary) |

## Pivot

Pivot table aggregation view.

```xml
<pivot string="Timesheet" disable_linking="0">
    <field name="employee_id" type="row"/>
    <field name="date" interval="month" type="col"/>
    <field name="unit_amount" type="measure" widget="float_time"/>
</pivot>
```

**Root Attributes:**

| Attribute | Type | Default |
|-----------|------|---------|
| `disable_linking` | bool | `False` |
| `display_quantity` | bool | `False` |
| `default_order` | str | Optional |
| `sample` | str | `''` |

**Field Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `string` | str | Field label | Display label |
| `type` | str | `row` | row/col/measure/interval |
| `invisible` | bool | `False` | Hide field |
| `widget` | str | Optional | Format widget |

## Calendar

Calendar event visualisation (daily/weekly/monthly/yearly).

```xml
<calendar date_start="start_date"
          date_stop="end_date"
          color="status">
    <field name="name"/>
</calendar>
```

**Root Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `date_start` | str | Required | Start date field |
| `date_stop` | str | Optional | End date field |
| `date_delay` | str | Optional | Duration (hours) |
| `scales` | str | all | Available scales (day, week, month, year) |
| `mode` | str | `week` | Default scale |
| `color` | str | Optional | Color segmentation field |
| `all_day` | str | Optional | All-day boolean field |
| `aggregate` | str | Optional | Aggregation field |
| `event_limit` | int | 5 | Max events per cell |
| `show_unusual_days` | bool | `False` | Grey weekends/holidays |
| `hide_date` | bool | `False` | Hide date in popover |
| `hide_time` | bool | `False` | Hide time in popover |
| `month_overflow` | bool | `True` | Show prev/next month days |
| `show_date_picker` | bool | `True` | Show mini calendar |
| `event_open_popup` | bool | `False` | Open dialog (vs. form) |
| `form_view_id` | int | Optional | Edit form view ID |
| `quick_create` | bool | `True` | Quick event creation |
| `create_name_field` | str | `name` | Display name field |
| `quick_create_view_id` | int | Optional | Quick create form ID |
| `multi_create_view` | str | Optional | Batch create form ref |
| `create` | bool | `True` | Enable creation |
| `edit` | bool | `True` | Enable editing |
| `delete` | bool | `True` | Enable deletion |
| `string` | str | `''` | View title |

**Field Attributes:**

| Attribute | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | str | Required | Field name |
| `invisible` | Python expr | `False` | Hide in popover |
