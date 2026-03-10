"""HTML report generator for MML test sprint results."""
from datetime import datetime
from pathlib import Path

from mml_test_sprint.checks import ModuleResult, Status


_STATUS_ICON = {
    Status.PASS: "✓",
    Status.FAIL: "✗",
    Status.SKIP: "—",
    Status.WARN: "⚠",
}
_STATUS_COLOR = {
    Status.PASS: "#065f46",
    Status.FAIL: "#991b1b",
    Status.SKIP: "#6b7280",
    Status.WARN: "#92400e",
}
_STATUS_BG = {
    Status.PASS: "#d1fae5",
    Status.FAIL: "#fee2e2",
    Status.SKIP: "#f3f4f6",
    Status.WARN: "#fef3c7",
}


def _badge(status: Status) -> str:
    icon = _STATUS_ICON[status]
    color = _STATUS_COLOR[status]
    bg = _STATUS_BG[status]
    return (
        f'<span style="background:{bg};color:{color};padding:2px 8px;'
        f'border-radius:3px;font-weight:600;font-size:0.8em">{icon} {status.value.upper()}</span>'
    )


def _check_row(check, tier_color: str) -> str:
    icon = _STATUS_ICON[check.status]
    color = _STATUS_COLOR[check.status]
    bg = _STATUS_BG[check.status]
    screenshot_html = ""
    if check.screenshot_b64:
        screenshot_html = (
            f'<details style="margin-top:4px">'
            f'<summary style="cursor:pointer;font-size:0.75em;color:#6b7280">screenshot</summary>'
            f'<img src="data:image/png;base64,{check.screenshot_b64}" '
            f'style="max-width:100%;border:1px solid #e5e7eb;border-radius:4px;margin-top:4px"/>'
            f'</details>'
        )
    detail = f'<div style="font-size:0.8em;color:#6b7280;margin-top:2px">{check.detail}</div>' if check.detail else ""
    return (
        f'<tr style="background:{bg}">'
        f'<td style="padding:6px 8px;color:{color};font-weight:700;width:24px">{icon}</td>'
        f'<td style="padding:6px 8px;border-left:3px solid {tier_color}">'
        f'<strong style="font-size:0.875em">{check.name}</strong>{detail}{screenshot_html}'
        f'</td></tr>'
    )


def _module_section(result: ModuleResult) -> str:
    overall = result.overall_status
    overall_bg = _STATUS_BG[overall]
    overall_color = _STATUS_COLOR[overall]

    if not result.installed:
        return (
            f'<div style="background:#f9fafb;border:1px solid #e5e7eb;'
            f'border-radius:8px;padding:16px;margin-bottom:16px">'
            f'<h3 style="margin:0;color:#9ca3af">{result.module_label} '
            f'<small style="font-weight:normal;font-size:0.75em">not installed on mml_dev</small></h3>'
            f'</div>'
        )

    scores = (
        f'Smoke: <strong>{result.smoke_score}</strong> &nbsp;|&nbsp; '
        f'Spec: <strong>{result.spec_score}</strong> &nbsp;|&nbsp; '
        f'Workflows: <strong>{result.workflow_score}</strong>'
    )

    def tier_table(checks, tier_label, color):
        if not checks:
            return ""
        rows = "".join(_check_row(c, color) for c in checks)
        return (
            f'<h4 style="margin:12px 0 4px;color:{color};font-size:0.8em;'
            f'text-transform:uppercase;letter-spacing:.06em">{tier_label}</h4>'
            f'<table style="width:100%;border-collapse:collapse;margin-bottom:8px">{rows}</table>'
        )

    smoke_table = tier_table(result.smoke, "Smoke", "#1e40af")
    spec_table = tier_table(result.spec, "Spec", "#7c3aed")
    workflow_table = tier_table(result.workflows, "Workflows", "#065f46")

    errors_html = ""
    if result.console_errors:
        err_items = "".join(f"<li style='font-size:0.8em;color:#991b1b'>{e}</li>"
                            for e in result.console_errors[:20])
        errors_html = (
            f'<details style="margin-top:8px">'
            f'<summary style="cursor:pointer;font-size:0.8em;color:#991b1b">'
            f'{len(result.console_errors)} console error(s)</summary>'
            f'<ul style="margin:4px 0;padding-left:16px">{err_items}</ul>'
            f'</details>'
        )

    return (
        f'<div style="background:{overall_bg};border:2px solid {overall_color};'
        f'border-radius:8px;padding:16px;margin-bottom:16px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
        f'<h3 style="margin:0;color:{overall_color}">{result.module_label}</h3>'
        f'{_badge(overall)}'
        f'</div>'
        f'<div style="font-size:0.85em;color:#6b7280;margin-bottom:12px">{scores}</div>'
        f'{smoke_table}{spec_table}{workflow_table}{errors_html}'
        f'</div>'
    )


def generate_html(results: list, output_path: Path, server_url: str, db: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pass = sum(1 for r in results if r.overall_status == Status.PASS and r.installed)
    total_fail = sum(1 for r in results if r.overall_status == Status.FAIL and r.installed)
    total_warn = sum(1 for r in results if r.overall_status == Status.WARN and r.installed)

    summary_color = "#991b1b" if total_fail else ("#92400e" if total_warn else "#065f46")
    summary_label = "FAILURES FOUND" if total_fail else ("WARNINGS" if total_warn else "ALL PASS")

    module_sections = "".join(_module_section(r) for r in results)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MML Module Test Report — {now}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background:#f9fafb; color:#1c1917; margin:0; padding:24px; }}
  .header {{ background:#1e293b; color:#f8fafc; padding:20px 24px;
             border-radius:8px; margin-bottom:24px; }}
  .header h1 {{ margin:0 0 4px; font-size:1.25rem; }}
  .header .meta {{ font-size:0.8rem; color:#94a3b8; }}
  .summary {{ display:flex; gap:12px; margin-bottom:24px; flex-wrap:wrap; }}
  .stat {{ background:#fff; border:1px solid #e5e7eb; border-radius:6px;
           padding:12px 20px; text-align:center; min-width:80px; }}
  .stat .num {{ font-size:2rem; font-weight:700; }}
  .stat .lbl {{ font-size:0.75rem; color:#6b7280; text-transform:uppercase; }}
  table {{ border-radius:4px; overflow:hidden; }}
  details summary {{ user-select:none; }}
</style>
</head>
<body>
<div class="header">
  <h1>MML Module Test Report</h1>
  <div class="meta">
    {now} &nbsp;|&nbsp; Server: {server_url} &nbsp;|&nbsp; DB: {db}
    &nbsp;|&nbsp; <span style="color:{summary_color};font-weight:700">{summary_label}</span>
  </div>
</div>
<div class="summary">
  <div class="stat"><div class="num" style="color:#065f46">{total_pass}</div><div class="lbl">Pass</div></div>
  <div class="stat"><div class="num" style="color:#991b1b">{total_fail}</div><div class="lbl">Fail</div></div>
  <div class="stat"><div class="num" style="color:#92400e">{total_warn}</div><div class="lbl">Warn</div></div>
  <div class="stat"><div class="num" style="color:#1e40af">{len(results)}</div><div class="lbl">Modules</div></div>
</div>
{module_sections}
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Report written to: {output_path}")
