"""Verify brand_id has tracking=True for audit trail."""
import ast
import pathlib


def test_brand_id_has_tracking_true():
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/barcode_allocation.py'
    ).read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'brand_id':
                    dumped = ast.dump(node.value)
                    assert 'tracking' in dumped, (
                        "brand_id field must have tracking=True for audit trail. "
                        "This requires mail.thread inheritance on the model."
                    )
                    return
    raise AssertionError("brand_id field not found in barcode_allocation.py")


def test_model_inherits_mail_thread():
    src = pathlib.Path(
        'mml.barcodes/mml_barcode_registry/models/barcode_allocation.py'
    ).read_text()
    assert 'mail.thread' in src, (
        "BarcodeAllocation must inherit mail.thread for tracking=True to work"
    )
