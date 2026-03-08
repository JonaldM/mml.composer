# barcodes/mml_barcode_registry/wizard/barcode_import_wizard.py
import base64
import csv
import io
import logging
from datetime import date

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.addons.mml_barcode_registry.services.gs1 import (
    compute_check_digit,
    build_gtin13,
    build_gtin14,
)

_logger = logging.getLogger(__name__)


class BarcodeImportWizard(models.TransientModel):
    _name = 'barcode.import.wizard'
    _description = 'Barcode Registry Import Wizard'

    prefix_id = fields.Many2one(
        'mml.barcode.prefix',
        string='Target Prefix',
        required=True,
    )
    file_data = fields.Binary(string='File (XLSX or CSV)', required=True)
    file_name = fields.Char(string='File Name')
    import_warnings = fields.Text(string='Warnings', readonly=True)
    preview_html = fields.Html(string='Preview', readonly=True)

    def action_preview(self):
        """Parse the uploaded file and show first 10 rows as a preview."""
        self.ensure_one()
        rows = self._parse_file()[:10]
        if not rows:
            self.preview_html = '<p>No data found in file.</p>'
            return

        html = ['<table class="table table-sm table-bordered"><thead><tr>']
        for col in rows[0].keys():
            html.append(f'<th>{col}</th>')
        html.append('</tr></thead><tbody>')
        for row in rows:
            html.append('<tr>' + ''.join(f'<td class="font-monospace">{v}</td>' for v in row.values()) + '</tr>')
        html.append('</tbody></table>')
        self.preview_html = ''.join(html)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'barcode.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        """
        Import XLSX or CSV. Idempotent — re-importing same sequence skips existing records.
        Validates check digits and matches products by barcode field, then by name.
        """
        self.ensure_one()
        rows = self._parse_file()
        if not rows:
            raise UserError('No data rows found in the uploaded file.')

        warnings = []
        created = skipped = 0

        Registry = self.env['mml.barcode.registry']
        Allocation = self.env['mml.barcode.allocation']

        for i, row in enumerate(rows, start=2):  # row 1 is header
            sequence = str(row.get('sequence', '') or '').strip()
            gtin_13_raw = str(row.get('gtin_13', '') or '').strip()
            description = str(row.get('description', '') or '').strip()

            if not sequence or len(sequence) != 12 or not sequence.isdigit():
                warnings.append(f"Row {i}: invalid sequence '{sequence}' — skipped.")
                continue

            # Validate check digit; use computed value regardless
            expected_gtin13 = build_gtin13(sequence)
            if gtin_13_raw and gtin_13_raw != expected_gtin13:
                warnings.append(
                    f"Row {i}: check digit mismatch for sequence {sequence}. "
                    f"File has {gtin_13_raw!r}, computed {expected_gtin13!r}. Using computed value."
                )

            # Idempotent: skip if sequence already exists
            existing = Registry.search([
                ('sequence', '=', sequence),
                ('company_id', '=', self.env.company.id),
            ], limit=1)

            if existing:
                skipped += 1
                registry = existing
            else:
                registry = Registry.create({
                    'sequence': sequence,
                    'prefix_id': self.prefix_id.id,
                    'status': 'unallocated',
                    'company_id': self.env.company.id,
                })
                created += 1

            # Try to match and allocate to a product
            if description and registry.status == 'unallocated':
                product = self.env['product.product'].search([
                    ('barcode', '=', expected_gtin13),
                ], limit=1)
                if not product:
                    product = self.env['product.product'].search([
                        ('name', 'ilike', description),
                    ], limit=1)

                if product:
                    alloc = Allocation.search([
                        ('registry_id', '=', registry.id),
                        ('product_id', '=', product.id),
                        ('status', '=', 'active'),
                    ], limit=1)
                    if not alloc:
                        with self.env.cr.savepoint():
                            alloc = Allocation.create({
                                'registry_id': registry.id,
                                'product_id': product.id,
                                'status': 'active',
                                'allocation_date': date.today(),
                                'company_id': self.env.company.id,
                            })
                            registry.write({
                                'status': 'in_use',
                                'current_allocation_id': alloc.id,
                            })
                            if not product.barcode:
                                product.write({'barcode': expected_gtin13})

        self.import_warnings = '\n'.join(warnings) if warnings else False

        _logger.info(
            'Barcode import complete: %d created, %d skipped, %d warning(s)',
            created, skipped, len(warnings),
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': (
                    f'{created} new records created, {skipped} existing skipped. '
                    f'{len(warnings)} warning(s).'
                ),
                'type': 'success' if not warnings else 'warning',
                'sticky': bool(warnings),
            },
        }

    def _parse_file(self) -> list[dict]:
        """Parse uploaded XLSX or CSV file. Returns list of row dicts."""
        if not self.file_data:
            return []

        raw = base64.b64decode(self.file_data)
        name = (self.file_name or '').lower()

        if name.endswith('.xlsx') or name.endswith('.xls'):
            return self._parse_xlsx(raw)
        return self._parse_csv(raw)

    def _parse_xlsx(self, raw: bytes) -> list[dict]:
        """Parse XLSX using openpyxl if available, else raise helpful error."""
        try:
            import openpyxl
        except ImportError:
            raise UserError(
                'openpyxl is not installed on this server. '
                'Please export your spreadsheet as CSV and upload that instead.'
            )
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip().lower() if h else '' for h in rows[0]]
        return [
            {headers[i]: (str(cell).strip() if cell is not None else '')
             for i, cell in enumerate(row)}
            for row in rows[1:]
            if any(cell is not None for cell in row)
        ]

    def _parse_csv(self, raw: bytes) -> list[dict]:
        """Parse CSV using stdlib csv module. Handles Excel BOM."""
        try:
            text = raw.decode('utf-8-sig')  # handles BOM from Excel CSV exports
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(text))
        return [
            {k.strip().lower(): v.strip() for k, v in row.items()}
            for row in reader
        ]
