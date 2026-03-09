import paramiko
import time
import sys

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('10.0.0.35', username='jono', password='***REMOVED***', timeout=30)
    c.get_transport().set_keepalive(30)
    return c

def run(client, cmd, timeout=120):
    if not client.get_transport() or not client.get_transport().is_active():
        raise RuntimeError("SSH session dropped")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    out_clean = '\n'.join(l for l in out.splitlines() if not l.startswith('[sudo]'))
    err_clean = '\n'.join(l for l in err.splitlines() if not l.startswith('[sudo]'))
    return rc, out_clean, err_clean

def write_remote(client, path, content):
    sftp = client.open_sftp()
    with sftp.file(path, 'w') as f:
        f.write(content)
    sftp.close()


# ----------------------------------------------------------------
# Patched forecast_config.py: remove the 5 forward-ref One2many fields
# ----------------------------------------------------------------
PATCHED_FORECAST_CONFIG = (
    "from odoo import models, fields, api, _\n"
    "from odoo.exceptions import UserError\n"
    "from dateutil.relativedelta import relativedelta\n"
    "\n"
    "\n"
    "class ForecastConfig(models.Model):\n"
    "    _name = 'forecast.config'\n"
    "    _inherit = ['mail.thread', 'mail.activity.mixin']\n"
    "    _description = 'Financial Forecast Configuration'\n"
    "    _order = 'create_date desc'\n"
    "\n"
    "    name = fields.Char(string='Forecast Name', required=True)\n"
    "    state = fields.Selection([\n"
    "        ('draft', 'Draft'),\n"
    "        ('generated', 'Generated'),\n"
    "        ('locked', 'Locked'),\n"
    "    ], default='draft', string='Status', tracking=True)\n"
    "\n"
    "    # --- Period ---\n"
    "    date_start = fields.Date(string='Forecast Start', required=True)\n"
    "    horizon_months = fields.Integer(string='Horizon (months)', default=12, required=True)\n"
    "    date_end = fields.Date(\n"
    "        string='Forecast End',\n"
    "        compute='_compute_date_end',\n"
    "        store=True,\n"
    "    )\n"
    "\n"
    "    # --- Scenario ---\n"
    "    scenario = fields.Selection([\n"
    "        ('base', 'Base Case'),\n"
    "        ('optimistic', 'Optimistic'),\n"
    "        ('pessimistic', 'Pessimistic'),\n"
    "        ('custom', 'Custom'),\n"
    "    ], default='base', required=True, string='Scenario')\n"
    "    volume_adjustment_pct = fields.Float(\n"
    "        string='Volume Adjustment %',\n"
    "        default=0.0,\n"
    "        help='Percentage adjustment to unit forecast. E.g. -20 for pessimistic.',\n"
    "    )\n"
    "    freight_rate_cbm = fields.Float(\n"
    "        string='Freight Rate ($/CBM)',\n"
    "        default=100.0,\n"
    "        required=True,\n"
    "    )\n"
    "\n"
    "    # --- Import tax ---\n"
    "    tax_id = fields.Many2one(\n"
    "        'account.tax',\n"
    "        string='Import Tax',\n"
    "        domain=\"[('type_tax_use', '=', 'purchase')]\",\n"
    "        help=(\n"
    "            'Purchase tax applied on import (GST/VAT). '\n"
    "            'NZ = 15% GST, AU = 10% GST, UK = 20% VAT. '\n"
    "            'Used in cash flow duty calculations.'\n"
    "        ),\n"
    "    )\n"
    "\n"
    "    # --- Relational (core reference data only) ---\n"
    "    fx_rate_ids = fields.One2many('forecast.fx.rate', 'config_id', string='FX Rates')\n"
    "    customer_term_ids = fields.One2many(\n"
    "        'forecast.customer.term', 'config_id', string='Customer Payment Terms',\n"
    "    )\n"
    "    supplier_term_ids = fields.One2many(\n"
    "        'forecast.supplier.term', 'config_id', string='Supplier Payment Terms',\n"
    "    )\n"
    "    # NOTE: opex_line_ids, revenue_line_ids, cogs_line_ids, pnl_line_ids, cashflow_line_ids\n"
    "    # are declared in mml_forecast_financial via _inherit = 'forecast.config'.\n"
    "    # Those comodels live in mml_forecast_financial and cannot be forward-referenced here.\n"
    "\n"
    "    # --- Totals (overridden by mml_forecast_financial) ---\n"
    "    total_revenue = fields.Float(\n"
    "        string='Total Revenue', compute='_compute_totals', store=True,\n"
    "    )\n"
    "    total_cogs = fields.Float(\n"
    "        string='Total COGS', compute='_compute_totals', store=True,\n"
    "    )\n"
    "    total_gross_margin = fields.Float(\n"
    "        string='Total Gross Margin', compute='_compute_totals', store=True,\n"
    "    )\n"
    "    gross_margin_pct = fields.Float(\n"
    "        string='GM %', compute='_compute_totals', store=True,\n"
    "    )\n"
    "\n"
    "    notes = fields.Html(string='Notes')\n"
    "\n"
    "    @api.depends('date_start', 'horizon_months')\n"
    "    def _compute_date_end(self):\n"
    "        for rec in self:\n"
    "            if rec.date_start and rec.horizon_months:\n"
    "                rec.date_end = rec.date_start + relativedelta(months=rec.horizon_months, days=-1)\n"
    "            else:\n"
    "                rec.date_end = False\n"
    "\n"
    "    @api.depends()\n"
    "    def _compute_totals(self):\n"
    "        # Base no-op. mml_forecast_financial overrides with pnl_line_ids dependency.\n"
    "        for rec in self:\n"
    "            rec.total_revenue = 0.0\n"
    "            rec.total_cogs = 0.0\n"
    "            rec.total_gross_margin = 0.0\n"
    "            rec.gross_margin_pct = 0.0\n"
    "\n"
    "    def action_generate_forecast(self):\n"
    "        self.ensure_one()\n"
    "        Wizard = self.env.get('forecast.generate.wizard')\n"
    "        if Wizard is None:\n"
    "            raise UserError(\n"
    "                _('The MML Forecast Financial module must be installed to generate forecasts.')\n"
    "            )\n"
    "        Wizard.with_context(active_id=self.id).generate(self)\n"
    "        self.state = 'generated'\n"
    "\n"
    "    def action_reset_draft(self):\n"
    "        self.ensure_one()\n"
    "        # Financial line cleanup is handled by mml_forecast_financial override.\n"
    "        self.state = 'draft'\n"
    "\n"
    "    def action_lock(self):\n"
    "        self.ensure_one()\n"
    "        self.state = 'locked'\n"
    "\n"
    "    def action_duplicate_scenario(self):\n"
    "        self.ensure_one()\n"
    "        new = self.copy(default={'name': f'{self.name} (Copy)', 'state': 'draft'})\n"
    "        return {\n"
    "            'type': 'ir.actions.act_window',\n"
    "            'res_model': 'forecast.config',\n"
    "            'res_id': new.id,\n"
    "            'view_mode': 'form',\n"
    "            'target': 'current',\n"
    "        }\n"
)

# ----------------------------------------------------------------
# New file: mml_forecast_financial/models/forecast_config_ext.py
# Adds the 5 One2many fields + proper compute override
# ----------------------------------------------------------------
FORECAST_CONFIG_EXT = (
    "from odoo import models, fields, api\n"
    "\n"
    "\n"
    "class ForecastConfigFinancial(models.Model):\n"
    "    # Extends forecast.config (mml_forecast_core) with financial line models\n"
    "    # that live in this module. These One2many fields cannot be declared in\n"
    "    # mml_forecast_core because the comodels are defined here.\n"
    "    _inherit = 'forecast.config'\n"
    "\n"
    "    opex_line_ids = fields.One2many('forecast.opex.line', 'config_id', string='Operating Expenses')\n"
    "    revenue_line_ids = fields.One2many('forecast.revenue.line', 'config_id', string='Revenue Lines')\n"
    "    cogs_line_ids = fields.One2many('forecast.cogs.line', 'config_id', string='COGS Lines')\n"
    "    pnl_line_ids = fields.One2many('forecast.pnl.line', 'config_id', string='P&L Summary')\n"
    "    cashflow_line_ids = fields.One2many(\n"
    "        'forecast.cashflow.line', 'config_id', string='Cash Flow Lines',\n"
    "    )\n"
    "\n"
    "    @api.depends('pnl_line_ids.revenue', 'pnl_line_ids.total_cogs', 'pnl_line_ids.gross_margin')\n"
    "    def _compute_totals(self):\n"
    "        for rec in self:\n"
    "            lines = rec.pnl_line_ids\n"
    "            rec.total_revenue = sum(lines.mapped('revenue'))\n"
    "            rec.total_cogs = sum(lines.mapped('total_cogs'))\n"
    "            rec.total_gross_margin = sum(lines.mapped('gross_margin'))\n"
    "            rec.gross_margin_pct = (\n"
    "                (rec.total_gross_margin / rec.total_revenue * 100)\n"
    "                if rec.total_revenue else 0.0\n"
    "            )\n"
    "\n"
    "    def action_reset_draft(self):\n"
    "        self.ensure_one()\n"
    "        self.revenue_line_ids.unlink()\n"
    "        self.cogs_line_ids.unlink()\n"
    "        self.pnl_line_ids.unlink()\n"
    "        self.cashflow_line_ids.unlink()\n"
    "        self.state = 'draft'\n"
)

FINANCIAL_MODELS_INIT = (
    "from . import forecast_revenue_line\n"
    "from . import forecast_cogs_line\n"
    "from . import forecast_pnl_line\n"
    "from . import forecast_cashflow_line\n"
    "from . import forecast_opex_line\n"
    "from . import forecast_config_ext\n"
)

# ----------------------------------------------------------------
# Execute patches on remote server
# ----------------------------------------------------------------
print("=== Patching source files on remote server ===")
client = connect()

print("  Writing patched forecast_config.py...")
write_remote(client,
    '/tmp/mml_forecasting_repo/mml_forecast_core/models/forecast_config.py',
    PATCHED_FORECAST_CONFIG)

print("  Writing forecast_config_ext.py to mml_forecast_financial/models/...")
write_remote(client,
    '/tmp/mml_forecasting_repo/mml_forecast_financial/models/forecast_config_ext.py',
    FORECAST_CONFIG_EXT)

print("  Updating mml_forecast_financial/models/__init__.py...")
write_remote(client,
    '/tmp/mml_forecasting_repo/mml_forecast_financial/models/__init__.py',
    FINANCIAL_MODELS_INIT)

# Verify patches
rc, out, _ = run(client,
    "grep -n 'One2many' /tmp/mml_forecasting_repo/mml_forecast_core/models/forecast_config.py")
print(f"\n  forecast_config.py One2many fields (should only show 3 core ones):\n{out}")

rc, out, _ = run(client,
    "cat /tmp/mml_forecasting_repo/mml_forecast_financial/models/__init__.py")
print(f"\n  mml_forecast_financial models/__init__.py:\n{out}")

rc, out, _ = run(client,
    "head -15 /tmp/mml_forecasting_repo/mml_forecast_financial/models/forecast_config_ext.py")
print(f"\n  forecast_config_ext.py (first 15 lines):\n{out}")

client.close()
print("\nPatch complete.")
