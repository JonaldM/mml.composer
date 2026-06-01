"""Structural tests for the storefront record rules (ir.rule).

Pure-Python — no Odoo runtime needed. The ACL CSV grants the storefront
group row-level access to transactional models (sale.order, res.partner,
account.move, payment.transaction, ...). Without ``ir.rule`` record rules
those grants are *company-wide*: the least-privilege storefront RPC user
could read every customer's orders and invoices.

These tests assert that:
  * a record-rules XML file exists and is well-formed,
  * it is declared in the manifest ``data`` list,
  * every transactional model that the storefront can read/write is covered
    by at least one rule scoped to the storefront group,
  * each such rule carries a non-trivial ``domain_force`` (not the global
    ``[(1, '=', 1)]`` no-op), so the rule actually restricts rows.
"""
import ast
import pathlib
import xml.etree.ElementTree as ET

import pytest

_MODULE_ROOT = pathlib.Path(__file__).resolve().parent.parent
_RULES_XML = _MODULE_ROOT / "security" / "petpro_storefront_record_rules.xml"
_MANIFEST = _MODULE_ROOT / "__manifest__.py"
_GROUP_REF = "mml_petpro_storefront_user.group_petpro_storefront"

# Models that MUST be row-scoped because the ACL grants the storefront access
# to them and they hold per-customer data.
_MODELS_REQUIRING_RULES = {
    "sale.order",
    "sale.order.line",
    "res.partner",
    "account.move",
    "account.move.line",
    "payment.transaction",
}

# model technical name -> the model_id:id ref used in the rule XML
_MODEL_REF = {
    "sale.order": "sale.model_sale_order",
    "sale.order.line": "sale.model_sale_order_line",
    "res.partner": "base.model_res_partner",
    "account.move": "account.model_account_move",
    "account.move.line": "account.model_account_move_line",
    "payment.transaction": "payment.model_payment_transaction",
}

# A global rule that does not restrict anything.
_NOOP_DOMAINS = {"[(1, '=', 1)]", "[(1,=,1)]", "[]"}


def _load_manifest():
    return ast.literal_eval(_MANIFEST.read_text(encoding="utf-8"))


def _rule_records():
    tree = ET.parse(_RULES_XML)
    root = tree.getroot()
    return [r for r in root.iter("record") if r.attrib.get("model") == "ir.rule"]


def _field(record, name):
    for f in record.findall("field"):
        if f.attrib.get("name") == name:
            return f
    return None


def test_record_rules_file_exists():
    assert _RULES_XML.is_file(), (
        "mml_petpro_storefront_user must ship security/"
        "petpro_storefront_record_rules.xml to scope per-customer data"
    )


def test_record_rules_declared_in_manifest():
    manifest = _load_manifest()
    rel = "security/petpro_storefront_record_rules.xml"
    assert rel in manifest["data"], (
        f"{rel} must be listed in the manifest 'data' so it loads on install"
    )
    # And it must load AFTER the group + ACL it depends on.
    data = manifest["data"]
    assert data.index("security/petpro_storefront_groups.xml") < data.index(rel)
    assert data.index("security/ir.model.access.csv") < data.index(rel)


def test_record_rules_xml_is_well_formed():
    records = _rule_records()
    assert records, "no ir.rule records found"


def test_every_transactional_model_has_a_scoped_rule():
    records = _rule_records()
    covered = set()
    for rec in records:
        model_f = _field(rec, "model_id")
        if model_f is None:
            continue
        ref = model_f.attrib.get("ref")
        for model_name, model_ref in _MODEL_REF.items():
            if ref == model_ref:
                covered.add(model_name)
    missing = _MODELS_REQUIRING_RULES - covered
    assert not missing, (
        f"these per-customer models are granted by the ACL but have NO "
        f"record rule scoping them (company-wide data leak): {sorted(missing)}"
    )


def test_rules_target_only_the_storefront_group():
    """Every storefront rule must be group-scoped (not a global rule).

    A global rule (no groups) would apply to ALL users including admins and
    could break unrelated flows. These rules must apply ONLY to the
    storefront group.
    """
    for rec in _rule_records():
        groups_f = _field(rec, "groups")
        assert groups_f is not None, (
            f"rule {rec.attrib.get('id')!r} has no 'groups' — a global rule "
            "must not be shipped by this module"
        )
        ev = groups_f.attrib.get("eval", "")
        assert _GROUP_REF in ev, (
            f"rule {rec.attrib.get('id')!r} groups eval {ev!r} must reference "
            f"{_GROUP_REF!r}"
        )


def test_rules_have_non_trivial_domain():
    """Each rule must actually restrict rows (no global [(1,=,1)] no-op)."""
    for rec in _rule_records():
        dom_f = _field(rec, "domain_force")
        assert dom_f is not None, (
            f"rule {rec.attrib.get('id')!r} has no domain_force"
        )
        raw = (dom_f.text or "").strip()
        normalised = raw.replace(" ", "")
        assert normalised not in _NOOP_DOMAINS, (
            f"rule {rec.attrib.get('id')!r} domain {raw!r} is a no-op; it must "
            "restrict rows (e.g. by create_uid / partner_id)"
        )
        # The domain must reference an ownership/partner anchor so it is a real
        # row restriction, not an arbitrary always-true predicate.
        assert ("create_uid" in raw) or ("partner_id" in raw) or (
            "user.partner_id" in raw
        ), (
            f"rule {rec.attrib.get('id')!r} domain {raw!r} must scope by "
            "create_uid or partner_id"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
