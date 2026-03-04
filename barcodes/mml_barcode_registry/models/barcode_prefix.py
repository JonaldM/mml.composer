from odoo import api, fields, models


class BarcodePrefix(models.Model):
    _name = 'mml.barcode.prefix'
    _description = 'GS1 Barcode Prefix'
    _order = 'priority asc, name'

    name = fields.Char(required=True)
    prefix = fields.Char(
        string='GS1 Prefix',
        size=7,
        required=True,
        help='7-digit GS1 company prefix, e.g. 9419416',
    )
    sequence_start = fields.Integer(required=True)
    sequence_end = fields.Integer(required=True)
    active = fields.Boolean(default=True)
    priority = fields.Integer(
        default=10,
        help='Lower value = used first when multiple prefixes are active',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )

    capacity = fields.Integer(
        compute='_compute_stats',
        store=True,
        depends=['sequence_start', 'sequence_end'],
    )
    allocated_count = fields.Integer(
        compute='_compute_stats',
        store=False,
    )
    utilisation_pct = fields.Float(
        compute='_compute_stats',
        store=False,
        digits=(5, 1),
    )
    next_sequence = fields.Integer(
        compute='_compute_stats',
        store=False,
    )

    _sql_constraints = [
        ('prefix_company_uniq', 'UNIQUE(prefix, company_id)', 'Prefix must be unique per company.'),
    ]

    @api.depends('sequence_start', 'sequence_end')
    def _compute_stats(self):
        for rec in self:
            if rec.sequence_start and rec.sequence_end:
                rec.capacity = max(0, rec.sequence_end - rec.sequence_start + 1)
            else:
                rec.capacity = 0
            registry = self.env['mml.barcode.registry']
            all_records = registry.search([('prefix_id', '=', rec.id)])
            rec.allocated_count = sum(1 for r in all_records if r.status != 'unallocated')
            rec.utilisation_pct = (rec.allocated_count / rec.capacity * 100.0) if rec.capacity else 0.0
            unallocated_seqs = [r.sequence for r in all_records if r.status == 'unallocated']
            if unallocated_seqs:
                rec.next_sequence = int(min(unallocated_seqs)[-5:])
            else:
                rec.next_sequence = rec.sequence_end + 1 if rec.sequence_end else 0

    def action_generate_sequences(self):
        """Bulk-create unallocated registry slots for the full prefix range. Idempotent."""
        self.ensure_one()
        Registry = self.env['mml.barcode.registry']

        existing_sequences = set(
            Registry.search([('prefix_id', '=', self.id)]).mapped('sequence')
        )

        vals_list = []
        for seq_num in range(self.sequence_start, self.sequence_end + 1):
            sequence = self.prefix + str(seq_num).zfill(5)
            if sequence not in existing_sequences:
                vals_list.append({
                    'sequence': sequence,
                    'prefix_id': self.id,
                    'status': 'unallocated',
                    'company_id': self.company_id.id,
                })

        if vals_list:
            chunk_size = 1000
            for i in range(0, len(vals_list), chunk_size):
                Registry.create(vals_list[i:i + chunk_size])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sequences Generated',
                'message': f'{len(vals_list)} unallocated barcodes created.',
                'type': 'success',
            },
        }
