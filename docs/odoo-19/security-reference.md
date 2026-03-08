# Security in Odoo

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html
> Fetched: 2026-03-07

Aside from custom code management, Odoo provides two primary data-driven mechanisms for managing access restrictions.

## Groups and Security

Both mechanisms connect to specific users through *groups*. Users belong to any number of groups, and security mechanisms associate with groups, thereby applying restrictions to users.

### res.groups attributes

- **name**: User-readable identification for the group
- **category_id**: Module category that associates groups with Odoo Apps and converts them into exclusive selections in user forms
- **implied_ids**: Other groups automatically set on the user alongside this one
- **comment**: Additional notes about the group

## Access Rights

Access rights grant access to entire models for specific operations. If no matching access rights exist for a user's operation, they cannot proceed.

Access rights are additive — a user's total access is the union of accesses from all their groups.

### ir.model.access attributes

- **name**: Purpose or role of the group
- **model_id**: Model whose access the ACL controls
- **group_id**: res.groups receiving access; empty means access for every user
- **perm_create**, **perm_read**, **perm_write**, **perm_unlink**: CRUD permissions (all unset by default)

## Record Rules

Record rules are conditions that must be satisfied for operations to proceed. They evaluate record-by-record after access rights verification.

Record rules are default-allow: if access rights permit access and no applicable rule exists, access is granted.

### ir.rule attributes

- **name**: Rule description
- **model_id**: Model to which the rule applies
- **groups**: res.groups receiving access; multiple groups allowed; empty means global rule
- **global**: Computed status indicating if the rule is global
- **domain_force**: Domain predicate allowing operations when matched
- **perm_create**, **perm_read**, **perm_write**, **perm_unlink**: Specify which operations the rule applies to (all selected by default)

### Domain Variables

Domain expressions can use:

- `time`: Python's time module
- `user`: Current user as singleton recordset
- `company_id`: Current user's selected company (single id, not recordset)
- `company_ids`: All companies accessible to user (list of ids, not recordset)

### Global Rules vs. Group Rules

**Global rules intersect**: both must be satisfied if multiple apply; adding global rules restricts access further.

**Group rules unify**: either can be satisfied if multiple apply; adding group rules can expand access.

**Combined behavior**: global and group rulesets intersect, meaning the first group rule added to a global ruleset will restrict access.

> "Creating multiple global rules is risky as it's possible to create non-overlapping rulesets, which will remove all access."

## Field Access

An ORM Field can have a `groups` attribute listing authorized groups as comma-separated external identifiers.

When a user lacks membership in listed groups, they cannot access that field:

- Restricted fields are automatically removed from requested views
- Restricted fields are removed from fields_get responses
- Explicit read/write attempts on restricted fields result in access errors

## Security Pitfalls

### Unsafe Public Methods

Any public method is callable via RPC with chosen parameters. Methods starting with `_` are not callable from action buttons or external APIs.

```python
# Public method — arguments cannot be trusted
def action_done(self):
    if self.state == "draft" and self.env.user.has_group('base.manager'):
        self._set_state("done")

# Private method — only callable from other Python methods
def _set_state(self, new_state):
    self.sudo().write({"state": new_state})
```

### Bypassing the ORM

Never use the database cursor directly when ORM can handle the same operation. This bypasses automated behaviors like translations, field invalidation, `active` filtering, and access rights.

```python
# Very wrong
self.env.cr.execute('SELECT id FROM auction_lots WHERE auction_id in (' + ','.join(map(str, ids))+') AND state=%s AND obj_price > 0', ('draft',))
auction_lots_ids = [x[0] for x in self.env.cr.fetchall()]

# Better
auction_lots_ids = self.search([('auction_id','in',ids), ('state','=','draft'), ('obj_price','>',0)])
```

### SQL Injections

Never use Python string concatenation or interpolation for SQL query variables. Use psycopg2 parameterisation or the `SQL` wrapper.

```python
# Very bad — SQL injection vulnerability
self.env.cr.execute('SELECT distinct child_id FROM account_account_consol_rel ' +
           'WHERE parent_id IN ('+','.join(map(str, ids))+')')

# Better
self.env.cr.execute('SELECT DISTINCT child_id FROM account_account_consol_rel WHERE parent_id IN %s', (tuple(ids),))

# More readable with SQL wrapper
self.env.cr.execute(SQL("""
    SELECT DISTINCT child_id
    FROM account_account_consol_rel
    WHERE parent_id IN %s
""", tuple(ids)))
```

### Building Domains

Domains are serializable lists. Direct manipulation can introduce vulnerabilities through user injection. Use `Domain` class for safe manipulation.

```python
# Bad — user can inject ['|', ('id', '>', 0)] to access all
domain = ...
security_domain = [('user_id', '=', self.env.uid)]
domain += security_domain
self.search(domain)

# Better
domain = Domain(...)
domain &= Domain('user_id', '=', self.env.uid)
self.search(domain)
```

### Unescaped Field Content

Avoid `t-raw` for displaying rich-text content due to XSS vulnerabilities.

```xml
<!-- Unsafe template -->
<div t-name="insecure_template">
    <div id="information-bar"><t t-raw="info_message" /></div>
</div>

<!-- Safe template -->
<div t-name="secure_template">
    <div id="information-bar">
        <div class="info"><t t-esc="message" /></div>
        <div class="subject"><t t-esc="subject" /></div>
    </div>
</div>
```

### Creating Safe Content with Markup

`Markup` automatically escapes parameters when combining strings:

```python
>>> from markupsafe import Markup
>>> Markup('<em>Hello</em> ') + '<foo>'
Markup('<em>Hello</em> &lt;foo&gt;')
>>> Markup('<em>Hello</em> %s') % '<foo>'
Markup('<em>Hello</em> &lt;foo&gt;')

def get_name(self, to_html=False):
    if to_html:
        return Markup("<strong>%s</strong>") % self.name
    else:
        return self.name
```

### Escaping vs. Sanitizing

**Escaping** converts TEXT to CODE and is mandatory when mixing data with code. It never breaks features when developers correctly identify TEXT versus CODE variables.

```python
>>> from odoo.tools import html_escape, html_sanitize
>>> data = "<R&D>"
>>> code = html_escape(data)
>>> code
Markup('&lt;R&amp;D&gt;')
```

**Sanitizing** converts CODE to SAFER CODE. Sanitizing untrusted CODE is necessary, but sanitizing unescaped TEXT will fail:

```python
# Sanitizing without escaping is broken
>>> html_sanitize(data)
Markup('')

# Sanitizing after escaping is OK
>>> html_sanitize(code)
Markup('<p>&lt;R&amp;D&gt;</p>')
```

### Evaluating Content

Avoid `eval` entirely. `safe_eval` is safer but still grants tremendous capabilities.

```python
# Very bad
domain = eval(self.filter_domain)
return self.search(domain)

# Good
from ast import literal_eval
domain = literal_eval(self.filter_domain)
return self.search(domain)
```

### Accessing Object Attributes

Using `getattr` to dynamically retrieve field values is unsafe — it allows access to private attributes and methods.

```python
# Unsafe
def _get_state_value(self, res_id, state_field):
    record = self.sudo().browse(res_id)
    return getattr(record, state_field, False)

# Better
def _get_state_value(self, res_id, state_field):
    record = self.sudo().browse(res_id)
    return record[state_field]
```

The `__getitem__` method of recordsets safely accesses dynamic field values without accessing private attributes.
