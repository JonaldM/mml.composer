"""Structural tests for mml_petpro_storefront_user.

Pure-Python — no Odoo runtime needed. Validates the static module
artifacts: manifest is parseable, ACL CSV is well-formed, XML files are
well-formed, and the user template does NOT contain a password.
"""
import ast
import csv
import pathlib
import xml.etree.ElementTree as ET

import pytest

_MODULE_ROOT = pathlib.Path(__file__).resolve().parent.parent

_ACL_CSV = _MODULE_ROOT / "security" / "ir.model.access.csv"
_GROUPS_XML = _MODULE_ROOT / "security" / "petpro_storefront_groups.xml"
_USER_XML = _MODULE_ROOT / "data" / "petpro_storefront_user.xml"
_MANIFEST = _MODULE_ROOT / "__manifest__.py"

_EXPECTED_HEADER = [
    "id",
    "name",
    "model_id:id",
    "group_id:id",
    "perm_read",
    "perm_write",
    "perm_create",
    "perm_unlink",
]
_EXPECTED_COLS = len(_EXPECTED_HEADER)
_PETPRO_GROUP_REF = (
    "mml_petpro_storefront_user.group_petpro_storefront"
)


def _read_csv_rows():
    with _ACL_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_manifest_is_parseable_python():
    """The manifest must be a literal-only Python expression."""
    src = _MANIFEST.read_text(encoding="utf-8")
    tree = ast.parse(src, mode="exec")
    # The manifest is a single Expression statement holding a dict literal.
    assert tree.body, "manifest is empty"
    assert isinstance(tree.body[0], ast.Expr)
    assert isinstance(tree.body[0].value, ast.Dict)
    # ast.literal_eval guarantees no callables / no side effects.
    manifest = ast.literal_eval(src)
    assert manifest["name"] == "MML PetPro Storefront User"
    assert manifest["version"].startswith("19.")
    assert manifest["application"] is False
    assert manifest["auto_install"] is False
    assert manifest["license"] == "LGPL-3"
    # All declared data files must exist on disk.
    for rel in manifest["data"]:
        assert (_MODULE_ROOT / rel).is_file(), f"manifest references missing data file: {rel}"


def test_groups_xml_is_well_formed():
    tree = ET.parse(_GROUPS_XML)
    root = tree.getroot()
    assert root.tag == "odoo"
    records = root.findall("record")
    assert len(records) >= 1
    grp = records[0]
    assert grp.attrib["model"] == "res.groups"
    assert grp.attrib["id"] == "group_petpro_storefront"


def test_user_xml_is_well_formed_and_has_no_password():
    """The user template must NEVER ship with a password field."""
    tree = ET.parse(_USER_XML)
    root = tree.getroot()
    assert root.tag == "odoo"
    user_records = [
        r for r in root.findall("record") if r.attrib.get("model") == "res.users"
    ]
    assert len(user_records) == 1
    user = user_records[0]
    assert user.attrib.get("forcecreate") == "1"
    field_names = {f.attrib.get("name") for f in user.findall("field")}
    # Hard requirement from the sprint task — must be set out-of-band.
    assert "password" not in field_names, "res.users template MUST NOT hardcode a password"
    # And the public template must wire group membership.
    assert "groups_id" in field_names
    # Login should be set so the operator knows what email to use in the UI.
    assert "login" in field_names


def test_acl_csv_header_is_canonical():
    rows = _read_csv_rows()
    assert rows, "ACL csv is empty"
    assert rows[0] == _EXPECTED_HEADER


def test_acl_csv_every_row_has_eight_cells():
    rows = _read_csv_rows()
    # Skip the header.
    data_rows = rows[1:]
    assert data_rows, "no ACL data rows"
    for idx, row in enumerate(data_rows, start=2):  # row 2 is the first data row
        assert len(row) == _EXPECTED_COLS, (
            f"line {idx} has {len(row)} cells, expected {_EXPECTED_COLS}: {row}"
        )


def test_acl_csv_rows_target_petpro_group_only():
    """Every ACL row must be scoped to the petpro storefront group.

    This is the structural guarantee that this module never accidentally
    loosens permissions on some *other* group.
    """
    rows = _read_csv_rows()[1:]
    for row in rows:
        group_ref = row[3]
        assert group_ref == _PETPRO_GROUP_REF, (
            f"ACL row {row[0]!r} targets {group_ref!r}, expected {_PETPRO_GROUP_REF!r}"
        )


def test_acl_csv_perm_columns_are_zero_or_one():
    rows = _read_csv_rows()[1:]
    for row in rows:
        for col_idx in range(4, 8):
            cell = row[col_idx]
            assert cell in {"0", "1"}, (
                f"ACL row {row[0]!r} column {_EXPECTED_HEADER[col_idx]} = "
                f"{cell!r}; must be '0' or '1'"
            )


def test_acl_csv_no_unlink_on_business_writes():
    """Storefront must never delete sale.order / sale.order.line / res.partner."""
    rows = _read_csv_rows()[1:]
    write_models_no_unlink = {
        "sale.model_sale_order",
        "sale.model_sale_order_line",
        "base.model_res_partner",
    }
    for row in rows:
        model_ref = row[2]
        perm_unlink = row[7]
        if model_ref in write_models_no_unlink:
            assert perm_unlink == "0", (
                f"row {row[0]!r} on {model_ref!r} has perm_unlink={perm_unlink!r}; "
                "storefront must never have delete rights on order/partner data"
            )


def test_acl_csv_catalogue_is_read_only():
    """Catalogue, stock, invoice, delivery, payment must be read-only."""
    rows = _read_csv_rows()[1:]
    read_only_models = {
        "product.model_product_template",
        "product.model_product_product",
        "product.model_product_category",
        "product.model_product_pricelist",
        "product.model_product_pricelist_item",
        "product.model_product_attribute",
        "product.model_product_attribute_value",
        "product.model_product_template_attribute_line",
        "stock.model_stock_quant",
        "account.model_account_move",
        "account.model_account_move_line",
        "delivery.model_delivery_carrier",
        "payment.model_payment_transaction",
    }
    for row in rows:
        model_ref = row[2]
        if model_ref in read_only_models:
            perm_read, perm_write, perm_create, perm_unlink = row[4:8]
            assert perm_read == "1", f"row {row[0]!r} should be readable"
            assert perm_write == "0", f"row {row[0]!r} on {model_ref!r} must not be writable"
            assert perm_create == "0", f"row {row[0]!r} on {model_ref!r} must not allow create"
            assert perm_unlink == "0", f"row {row[0]!r} on {model_ref!r} must not allow unlink"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
