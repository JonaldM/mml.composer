# Upgrade a Customised Database

> Source: https://www.odoo.com/documentation/19.0/developer/howtos/upgrade_custom_db.html
> Fetched: 2026-03-07

Upgrading to a new version of Odoo can be challenging, especially if the database contains custom modules. This page explains the technical process of upgrading a database with customised modules.

A custom module is any module that extends the standard code of Odoo and was not built with the Studio app.

While working on the **custom upgrade** of your database, keep in mind the goals of an upgrade:

1. Stay supported
2. Get the latest features
3. Enjoy the performance improvement
4. Reduce the technical debt
5. Benefit from security improvements

**Steps to follow:**

1. Stop the developments and challenge them
2. Request an upgraded database
3. Make your module installable on an empty database
4. Make your module installable on the upgraded database
5. Test extensively and do a rehearsal
6. Upgrade the production database

## Step 1: Stop the Developments

Starting an upgrade requires commitment and development resources. If developments keep being made at the same time, those features will need to be re-upgraded and tested every time they change. A complete freeze of the codebase is recommended when starting the upgrade process. Bug fixing is exempt from this recommendation.

Once development has stopped, assess the developments made and compare them with the features introduced between your current version and the version you are targeting. Challenge the developments as much as possible and find functional workarounds. Removing redundancy between your developments and the standard version of Odoo will lead to an eased upgrade process and reduce technical debt.

> Note: You can find information on the changes between versions in the Release Notes.

## Step 2: Request an Upgraded Database

Once the developments have stopped and the implemented features have been challenged to remove redundancy and unnecessary code, request an upgraded test database.

The purpose of this stage is not to start working with the custom modules in the upgraded database, but to make sure the standard upgrade process works seamlessly, and the test database is delivered properly.

## Step 3: Empty Database

Before working on an upgraded test database, make the custom developments work on an empty database in the targeted version. This ensures that the customisation is compatible with the new version, allows analysis of how it behaves with the new features, and guarantees that it will not cause issues when upgrading the database.

Working on an empty database helps avoid changes and wrong configurations that might be present in the production database (like studio customisation, customised website pages, email templates or translations).

### Make Custom Modules Installable

Install the custom modules, one by one, in an empty database of the new Odoo version and fix the tracebacks and warnings that arise.

This process helps detect issues during installation, for example:

- Invalid module dependencies
- Syntax changes: assets declaration, OWL updates, `attrs`
- References to standard fields, models, views not existing anymore or renamed
- XPath that moved or were removed from views
- Methods renamed or removed

### Test and Fixes

Once there are no more tracebacks when installing the modules, test them thoroughly. This process detects runtime issues not identified during installation, for example deprecated calls to standard Python or OWL functions, non-existing references to standard fields, etc.

Pay particular attention to:

- Views
- Email templates
- Reports
- Server actions and automated actions
- Changes in the standard workflows
- Computed fields

Write automated tests to save time during testing iterations and ensure that fixes do not break existing flows.

### Clean the Code

At this stage:

- Remove redundant and unnecessary code
- Remove features now part of Odoo standard
- Clean commented code if not needed anymore
- Refactor code (functions, fields, views, reports, etc.) if needed

### Standard Tests

Make sure all standard tests associated with the dependencies of the custom module pass. If standard tests are failing:

- **The customisation changes the standard workflow:** Adapt the standard test to your workflow.
- **The customisation did not take into account a special flow:** Adapt your customisation to ensure it works for all standard workflows.

## Step 4: Upgraded Database

Once the custom modules are installable and working properly on an empty database, make them work on an upgraded database.

### Migrate the Data

During the upgrade of the custom modules, you might have to use upgrade scripts to reflect changes from the source code to their corresponding data. Together with the upgrade scripts, you can make use of `upgrade_utils` and its helper functions.

- Any technical data that was renamed during the upgrade (models, fields, external identifiers) should be renamed using upgrade scripts to avoid data loss. See also: `rename_field`, `rename_model`, `rename_xmlid`.
- Data from standard models removed from the source code might need to be recovered from the old model table if it is still present.

**Example:** Custom fields for model `sale.subscription` are not automatically migrated from Odoo 15 to Odoo 16 (when the model was merged into `sale.order`). A SQL query can be executed in an upgrade script to move the data:

```python
def migrate(cr, version):
   cr.execute(
      """
      UPDATE sale_order so
         SET custom_field = ss.custom_field
        FROM sale_subscription ss
       WHERE ss.new_sale_order_id = so.id
      """
   )
```

Note: all columns/fields must already exist; consider doing this in a `post-` script.

Upgrade scripts can also be used to:

- Ease processing time by storing computed stored field values via SQL queries on large models
- Recompute fields where the computation has changed; see also `recompute_fields`
- Uninstall unwanted custom modules; see also `remove_module`
- Correct faulty data or wrong configurations

#### Running and Testing Upgrade Scripts

**Odoo Online**: Installation of custom modules containing Python files is not allowed on Odoo Online; it is not possible to run upgrade scripts on this platform.

**Odoo.sh**: Integrated with the upgrade platform. Once the upgrade of a staging branch is on "Update on commit" mode, each commit restores the upgraded backup and updates all custom modules including running upgrade scripts.

**On-premise**: Once you receive the upgraded dump, deploy the database and update all custom modules:

```bash
./odoo-bin -u <modules> -d <database>
```

### Test the Custom Modules

Test custom modules with your data in the upgraded database. Check:

- **Views not working**: If a view causes issues because of its content, it gets disabled. Find disabled views in the Upgrade report and re-activate or remove them using upgrade scripts.
- **Module data not updated**: Custom records with the `noupdate` flag are not updated when upgrading. For data that needs to be updated due to changes in the new version, use upgrade scripts. See also: `update_record_from_xml`.

## Step 5: Testing and Rehearsal

When the custom modules are working properly in the upgraded database, do another round of testing to assess database usability and detect any issues that might have gone unnoticed.

Frequently request new upgraded test databases to ensure the upgrade process remains successful as your codebase evolves.

Do a full rehearsal of the upgrade process the day before upgrading the production database to avoid undesired behaviour and detect any issues with the migrated data.

## Step 6: Production Upgrade

Once confident about upgrading your production database, follow the process described in the upgrade-production documentation, depending on the hosting type of your database.
