"""Verify GTIN reuse error message includes GS1 guidance."""
import pathlib


def test_reuse_error_message_includes_gs1_url():
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/barcode_registry.py'
    ).read_text()
    assert 'gs1nz.org' in src or 'gs1.org' in src, (
        "Reuse eligibility error must include a GS1 contact URL"
    )


def test_reuse_error_message_mentions_48_months():
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/barcode_registry.py'
    ).read_text()
    assert '48' in src, (
        "Error message must mention the 48-month cool-down period"
    )


def test_reuse_error_message_explains_reason():
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/barcode_registry.py'
    ).read_text()
    # Must explain WHY — retailer systems, scanners, etc.
    assert any(word in src.lower() for word in ['scanner', 'retailer', 'pos', 'reassign']), (
        "Error message must explain why reuse is restricted (retail scanners, etc.)"
    )
