from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_MAX_GENERATE_RANGE = 100_000


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

    # Reverse relation — used to declare computed field dependencies
    registry_ids = fields.One2many('mml.barcode.registry', 'prefix_id', string='Registry Records')

    capacity = fields.Integer(
        compute='_compute_capacity',
        store=True,
        help='Total number of sequence slots in this prefix block',
    )
    allocated_count = fields.Integer(
        compute='_compute_live_stats',
        store=False,
        help='Number of registry records that are not unallocated',
    )
    utilisation_pct = fields.Float(
        compute='_compute_live_stats',
        store=False,
        digits=(5, 1),
    )
    next_sequence = fields.Integer(
        compute='_compute_live_stats',
        store=False,
        help='Next sequence number with no registry record',
    )

    _sql_constraints = [
        ('prefix_company_uniq', 'UNIQUE(prefix, company_id)', 'Prefix must be unique per company.'),
    ]

    @api.constrains('prefix')
    def _check_prefix_format(self):
        for rec in self:
            if rec.prefix and (len(rec.prefix) != 7 or not rec.prefix.isdigit()):
                raise ValidationError(
                    f"GS1 prefix must be exactly 7 digits, got: {rec.prefix!r}"
                )

    @api.depends('sequence_start', 'sequence_end')
    def _compute_capacity(self):
        for rec in self:
            if rec.sequence_start is not None and rec.sequence_end is not None:
                rec.capacity = max(0, rec.sequence_end - rec.sequence_start + 1)
            else:
                rec.capacity = 0

    @api.depends('registry_ids.status', 'registry_ids.sequence', 'sequence_start', 'sequence_end')
    def _compute_live_stats(self):
        for rec in self:
            capacity = (
                max(0, rec.sequence_end - rec.sequence_start + 1)
                if rec.sequence_start is not None and rec.sequence_end is not None
                else 0
            )
            all_records = rec.registry_ids
            rec.allocated_count = sum(1 for r in all_records if r.status != 'unallocated')
            rec.utilisation_pct = (rec.allocated_count / capacity * 100.0) if capacity else 0.0
            unallocated_seqs = [r.sequence for r in all_records if r.status == 'unallocated']
            if unallocated_seqs:
                rec.next_sequence = int(min(unallocated_seqs)[-5:])
            else:
                rec.next_sequence = rec.sequence_end + 1 if rec.sequence_end is not None else 0

    def action_generate_sequences(self):
        """Bulk-create unallocated registry slots for the full prefix range. Idempotent."""
        self.ensure_one()
        total = self.sequence_end - self.sequence_start + 1
        if total > _MAX_GENERATE_RANGE:
            raise UserError(
                f"Range of {total:,} sequences exceeds the maximum of "
                f"{_MAX_GENERATE_RANGE:,} allowed per operation. "
                f"Split your prefix block into smaller ranges."
            )
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
