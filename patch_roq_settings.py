import paramiko

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
        f.write(content.encode('utf-8'))
    sftp.close()


# Odoo 19 settings view uses <app> + <block> + <setting> structure.
# Inherit from base.res_config_settings_view_form and inject inside //form.
ROQ_SETTINGS_VIEW = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<odoo>\n'
    '    <record id="res_config_settings_view_roq" model="ir.ui.view">\n'
    '        <field name="name">res.config.settings.view.roq</field>\n'
    '        <field name="model">res.config.settings</field>\n'
    '        <field name="inherit_id" ref="base.res_config_settings_view_form"/>\n'
    '        <field name="arch" type="xml">\n'
    '            <xpath expr="//form" position="inside">\n'
    '                <app string="ROQ Forecast" name="mml_roq_forecast"\n'
    '                     logo="/mml_roq_forecast/static/description/icon.png"\n'
    '                     data-string="ROQ Forecast">\n'
    '                    <block title="Forecasting Parameters" name="roq_forecast_params">\n'
    '                        <setting string="Default Lead Time (Days)"\n'
    '                                 help="System-wide default. Overridden per-supplier.">\n'
    '                            <field name="roq_default_lead_time_days"/>\n'
    '                        </setting>\n'
    '                        <setting string="Default Review Interval (Days)">\n'
    '                            <field name="roq_default_review_interval_days"/>\n'
    '                        </setting>\n'
    '                        <setting string="Lookback Weeks"\n'
    '                                 help="156 = 3 years history">\n'
    '                            <field name="roq_lookback_weeks"/>\n'
    '                        </setting>\n'
    '                        <setting string="SMA Window (Weeks)">\n'
    '                            <field name="roq_sma_window_weeks"/>\n'
    '                        </setting>\n'
    '                        <setting string="Min N Value"\n'
    '                                 help="Min data points for reliable std dev">\n'
    '                            <field name="roq_min_n_value"/>\n'
    '                        </setting>\n'
    '                        <setting string="ABC Dampener (Weeks)">\n'
    '                            <field name="roq_abc_dampener_weeks"/>\n'
    '                        </setting>\n'
    '                        <setting string="Container LCL Threshold (%)">\n'
    '                            <field name="roq_container_lcl_threshold_pct"/>\n'
    '                        </setting>\n'
    '                    </block>\n'
    '                    <block title="Order Rules" name="roq_order_rules">\n'
    '                        <setting string="Enforce Supplier MOQs"\n'
    '                                 help="When enabled, orders below supplier MOQ are raised to minimum and extra units allocated to warehouse with lowest cover.">\n'
    '                            <field name="roq_enable_moq_enforcement" widget="boolean_toggle"/>\n'
    '                        </setting>\n'
    '                    </block>\n'
    '                </app>\n'
    '            </xpath>\n'
    '        </field>\n'
    '    </record>\n'
    '</odoo>\n'
)

print("=== Patching ROQ res_config_settings_views.xml ===")
client = connect()

write_remote(client,
    '/tmp/mml_roq_repo/mml_roq_forecast/views/res_config_settings_views.xml',
    ROQ_SETTINGS_VIEW)

# Verify
rc, out, _ = run(client,
    "head -20 /tmp/mml_roq_repo/mml_roq_forecast/views/res_config_settings_views.xml")
print(out)

client.close()
print("\nROQ settings view patch complete.")
