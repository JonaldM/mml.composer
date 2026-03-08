# Testing Odoo

> Source: https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html
> Fetched: 2026-03-07

Odoo provides three primary testing approaches:

- **Python unit tests**: Test model business logic
- **JS unit tests**: Test JavaScript code in isolation
- **Tours**: Integration testing that simulates real scenarios and validates Python/JavaScript interaction

## Testing Python Code

Odoo leverages Python's `unittest` library to support module testing. To implement tests, create a `tests` sub-package within your module with test modules named starting with `test_` and imported in `tests/__init__.py`.

### Test Structure Example

```
your_module
├── ...
├── tests
|   ├── __init__.py
|   ├── test_bar.py
|   └── test_foo.py
```

Where `__init__.py` contains:

```python
from . import test_foo, test_bar
```

**Important**: Test modules not imported from `tests/__init__.py` will not execute.

### Available Test Classes

- `odoo.tests.TransactionCase`: For testing model properties with `browse_ref` and `ref` methods
- `odoo.tests.SingleTransactionCase`: Single transaction testing utilities
- `odoo.tests.HttpCase`: Browser-based testing with `url_open` and `browser_js` methods
- `odoo.tests.tagged`: Decorator for test organisation

### Basic Test Example

```python
class TestModelA(TransactionCase):
    def test_some_action(self):
        record = self.env['model.a'].create({'field': 'value'})
        record.some_action()
        self.assertEqual(record.field, expected_field_value)
```

**Note**: Test methods must start with `test_`

### Running Tests

Tests execute automatically when installing/updating modules with `--test-enable` flag enabled.

### Test Selection with Tags

Tests can be tagged using the `@tagged` decorator for filtering:

```python
@tagged('-standard', 'nice')
class NiceTest(TransactionCase):
    ...
```

**Special tags**:
- `standard`: Default tag for all BaseCase tests
- `at_install`: Executes immediately after module installation
- `post_install`: Executes after all modules install

Run tests with: `odoo-bin --test-tags nice,standard`

### Test Utilities

- `odoo.tests.Form`: Form testing helper
- `odoo.tests.M2MProxy`: Many-to-many field utilities with `add`, `remove`, `clear` methods
- `odoo.tests.O2MProxy`: One-to-many field utilities with `new`, `edit`, `remove` methods

## Testing JS Code

For JavaScript testing details, see the dedicated frontend unit testing documentation covering Hoot, web test helpers, and mock server implementations.

## Integration Testing

Tours simulate user workflows by automating browser interactions. They validate that Python and JavaScript components work together correctly.

### Test Tour Structure

```
your_module
├── ...
├── static
|   └── tests
|       └── tours
|           └── your_tour.js
├── tests
|   ├── __init__.py
|   └── test_calling_the_tour.py
└── __manifest__.py
```

### JavaScript Tour Registration

```javascript
import tour from 'web_tour.tour';
tour.register('rental_product_configurator_tour', {
    url: '/web',
}, [
    // sequence of steps
]);
```

### Tour Step Properties

- **trigger** (required): CSS selector for the target element
- **run**: Action to perform (`click`, `fill`, `check`, `hover`, etc.)
- **isActive**: Conditional activation based on browser/edition/mode
- **tooltipPosition**: Tooltip placement (top/right/bottom/left)
- **content**: Tooltip message for interactive tours
- **timeout**: Maximum wait time in milliseconds (default 10000)

### Available Run Actions

- `check/uncheck`: Checkbox operations
- `clear`: Input/textarea clearing
- `click/dblclick`: Mouse operations
- `drag_and_drop {target}`: Drag simulation
- `edit {content}`: Clear and fill
- `fill {content}`: Focus and type
- `hover`: Hover sequence
- `press {content}`: Keyboard events
- `range {content}`: Range input operations
- `select {value}`: Dropdown selection
- `selectByIndex {index}`: Index-based selection
- `selectByLabel {label}`: Label-based selection

### Python Test Tour Integration

```python
def test_your_test(self):
    self.start_tour("/web", "your_tour_name", login="admin")
```

### Onboarding Tours

Onboarding tours provide interactive user guidance. They require both JavaScript registration and XML data records:

```xml
<record id="your_tour" model="web_tour.tour">
    <field name="name">your_tour</field>
    <field name="sequence">10</field>
    <field name="rainbow_man_message">Congrats!</field>
</record>
```

**XML record fields**:
- `name`: Must match JavaScript registry name
- `sequence`: Execution order
- `url`: Starting URL
- `rainbow_man_message`: Completion message

Tours are launched via Settings > Technical > User Interface > Tours.

### Tour Debugging Methods

**watch=True**: Automatically open a Chrome window with the tour being run inside it

**debug=True**: Opens Chrome with devtools and debugger breakpoint at tour start

**Browser console**: Call `odoo.startTour("tour_name")` or enable test mode with `?debug=tests`

### Step Debugging

- `break: true` property for debugger pause
- `pause: true` property to pause tour (resume with `play()`)
- Custom `run() { debugger; }` action

## Performance Testing

### Query Count Assertions

```python
with self.assertQueryCount(11):
    do_something()
```

Use `assertQueryCount` to establish maximum database query limits for operations, measured via the `--log-sql` CLI parameter.
