# Owl Components

> Source: https://www.odoo.com/documentation/19.0/developer/reference/frontend/owl_components.html
> Fetched: 2026-03-07

The Odoo JavaScript framework employs a custom component framework called Owl, which is a declarative component system inspired by Vue and React. Components are defined using QWeb templates with Owl-specific directives.

## Using Owl Components

### Basic Component Structure

```javascript
import { Component, useState } from "@odoo/owl";

class MyComponent extends Component {
    static template = 'myaddon.MyComponent';

    setup() {
        this.state = useState({ value: 1 });
    }

    increment() {
        this.state.value++;
    }
}
```

The corresponding XML template:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<templates xml:space="preserve">

<t t-name="myaddon.MyComponent">
  <div t-on-click="increment">
    <t t-esc="state.value"/>
  </div>
</t>

</templates>
```

## Best Practices

Components should use the `setup` method for initialisation rather than constructors, as constructors cannot be overridden. Template names should follow the convention `addon_name.ComponentName` to prevent naming collisions between addons.

## Reference Components

Odoo provides several reusable generic components for common UI patterns.

### ActionSwiper

Location: `@web/core/action_swiper/action_swiper`

A component that can perform actions when an element is swiped horizontally. The swiper wraps a target element and executes actions once the user releases the swiper past a portion of its width.

**Key Props:**
- `onLeftSwipe`: Object defining left swipe action
- `onRightSwipe`: Object defining right swipe action
- `swipeDistanceRatio`: Minimum width ratio to trigger action
- `animationOnMove`: Boolean for translate effect during swipe
- `animationType`: Animation after swipe ('bounce' or 'forwards')

### CheckBox

Location: `@web/core/checkbox/checkbox`

A simple checkbox component with an associated label. The checkbox toggles when the label is clicked.

**Props:**
- `value`: Boolean indicating checked state
- `disabled`: Boolean to disable the checkbox

### ColorList

Location: `@web/core/colorlist/colorlist`

The ColorList lets you choose a color from a predefined list. The component displays the selected color and can expand to show available options.

**Props:**
- `canToggle`: Whether colorlist expands on click
- `colors`: Array of color objects
- `forceExpanded`: Always expand the list
- `isExpanded`: Expand by default
- `onColorSelected`: Selection callback
- `selectedColor`: Currently selected color ID

Color IDs range from 0 (No color) to 12 (Green), including Red, Orange, Yellow, Light blue, Dark purple, Salmon pink, Medium blue, Dark blue, Fuchsia, and Purple.

### Dropdown

Location: `@web/core/dropdown/dropdown` and `@web/core/dropdown/dropdown_item`

The Dropdown lets you show a menu with a list of items when a toggle is clicked on. Dropdowns support nested structures, keyboard navigation, and automatic repositioning.

**Dropdown Props:**
- `menuClass`: Classname for dropdown menu
- `disabled`: Disable dropdown interaction
- `items`: Array of items to display
- `position`: Menu opening position
- `beforeOpen`: Function called before opening
- `onOpened`: Function called after opening
- `onStateChanged`: Function called on state change
- `state`: Object to manually control open/close
- `manual`: Prevent automatic click listeners
- `navigationOptions`: Override navigation behaviour
- `holdOnHover`: Keep menu position while hovering
- `menuRef`: Reference to dropdown menu

**DropdownItem Props:**
- `class`: CSS classes for item
- `onSelected`: Selection callback
- `closingMode`: Control which dropdown closes ('none', 'closest', 'all')
- `attrs`: HTML attributes for the element

### Notebook

Location: `@web/core/notebook/notebook`

The Notebook is made to display multiple pages in a tabbed interface. Tabs can be positioned horizontally or vertically, and pages can be disabled.

**Props:**
- `anchors`: Allow anchor navigation in non-visible tabs
- `className`: Root element classname
- `defaultPage`: Page ID to display initially
- `icons`: Array of icons for tabs
- `orientation`: 'horizontal' or 'vertical'
- `onPageUpdate`: Page change callback
- `pages`: Array of page objects

### Pager

Location: `@web/core/pager/pager`

The Pager is a small component to handle pagination. It displays current page information and provides navigation buttons.

**Props:**
- `offset`: Index of first page element
- `limit`: Page size
- `total`: Total number of elements
- `onUpdate`: Callback when page changes
- `isEditable`: Allow editing current page
- `withAccessKey`: Bind access keys 'p' and 'n'

### SelectMenu

Location: `@web/core/select_menu/select_menu`

This component can be used when you want to do more than using the native select element. Supports custom option templates, searching, and grouping.

**Props:**
- `choices`: Array of choice objects
- `class`: Root classname
- `groups`: Array of grouped choices
- `multiSelect`: Enable multiple selections
- `togglerClass`: Toggler button classname
- `required`: Prevent unselecting value
- `searchable`: Show search box
- `searchPlaceholder`: Search box placeholder text
- `value`: Currently selected value
- `onSelect`: Selection callback

### TagsList

Location: `@web/core/tags_list/tags_list`

This component can display a list of tags in rounded pills. Tags can be editable with removal capability and support visibility limiting.

**Props:**
- `displayBadge`: Display tag as badge
- `displayText`: Display tag text
- `itemsVisible`: Limit visible tags
- `tags`: Array of tag objects

Tag objects contain: `colorIndex`, `icon`, `id`, `img`, `onClick`, `onDelete`, and `text` properties.
