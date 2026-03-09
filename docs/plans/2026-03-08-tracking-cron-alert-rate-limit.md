# Tracking Cron Alert Rate-Limiting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add alert rate-limiting and XSS body escaping to `MFTrackingCron._send_cron_alert()`, matching the pattern already in `edi_processor.py`.

**Architecture:** The EDI module's `_send_cron_alert()` is the canonical implementation. The tracking cron has a duplicate without the cooldown guard or `html.escape()`. We copy the cooldown pattern exactly, using the same `ir.config_parameter` timestamp approach with a per-module key scoped to `mml_3pl.last_alert.<module_name>`.

**Tech Stack:** Python 3.12, Odoo 19 ORM, `ir.config_parameter`, `mail.mail`, `unittest.mock` for tests.

---

## Files

- Modify: `mml.3pl.intergration/addons/stock_3pl_mainfreight/models/tracking_cron.py`
- Modify: `mml.3pl.intergration/addons/stock_3pl_mainfreight/tests/test_tracking_cron.py`
- Reference (read-only): `mml.edi/models/edi_processor.py` lines 1–50 and 630–680

---

## Background: What the EDI pattern looks like

`edi_processor.py` rate-limits using:
- Module-level constant: `_ALERT_COOLDOWN_SECONDS = 3600`
- `ir.config_parameter` key: `mml_edi.last_alert.<module_name>` storing an ISO datetime string
- Logic: read stored timestamp → parse → compare elapsed seconds → suppress if under cooldown
- Body: wrapped with `html.escape()` before inserting into `<pre>` tag
- Timestamp only written after a successful `mail.mail.send()`
- Malformed stored value: send the alert anyway (fail-open)

The tracking cron will use key prefix `mml_3pl.last_alert.<module_name>` (not `mml_edi.`).

---

## Task 1: Write the failing tests

**File:** `mml.3pl.intergration/addons/stock_3pl_mainfreight/tests/test_tracking_cron.py`

Append a new test class `TestSendCronAlertRateLimiting` after the existing `TestRunMFTrackingNoConnector` class (before `if __name__ == '__main__':`).

**Step 1: Write the failing tests**

Add this class to the end of the test file (before the `if __name__ == '__main__':` line):

```python
# ---------------------------------------------------------------------------
# Tests: _send_cron_alert — rate-limiting and XSS escaping
# ---------------------------------------------------------------------------

class TestSendCronAlertRateLimiting(unittest.TestCase):
    """_send_cron_alert must suppress duplicate alerts within the cooldown window
    and escape HTML in the body."""

    def _make_cron_with_icp(self, icp_params):
        """Build a cron instance where ir.config_parameter returns values from icp_params dict."""
        cron = object.__new__(MFTrackingCron)
        env = MagicMock()

        icp = MagicMock()
        icp.get_param.side_effect = lambda key, default=False: icp_params.get(key, default)
        icp.set_param = MagicMock()

        mail_model = MagicMock()
        mail_instance = MagicMock()
        mail_model.create.return_value = mail_instance

        def env_getitem(key):
            if key == 'ir.config_parameter':
                mock_model = MagicMock()
                mock_model.sudo.return_value = icp
                return mock_model
            if key == 'mail.mail':
                mock_model = MagicMock()
                mock_model.sudo.return_value = mail_model
                return mock_model
            return MagicMock()

        env.__getitem__ = MagicMock(side_effect=env_getitem)
        cron.env = env
        return cron, icp, mail_model, mail_instance

    def test_alert_suppressed_within_cooldown(self):
        """Alert is not sent if the last alert was less than _ALERT_COOLDOWN_SECONDS ago."""
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        cron, icp, mail_model, _ = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
            'mml_3pl.last_alert.stock_3pl_mainfreight': recent,
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'Test subject', 'Test body')

        mail_model.create.assert_not_called()

    def test_alert_sent_after_cooldown_expires(self):
        """Alert is sent when the last alert was more than _ALERT_COOLDOWN_SECONDS ago."""
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        cron, icp, mail_model, mail_instance = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
            'mml_3pl.last_alert.stock_3pl_mainfreight': old,
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'Test subject', 'Test body')

        mail_model.create.assert_called_once()
        mail_instance.send.assert_called_once()

    def test_alert_sent_when_no_prior_timestamp(self):
        """Alert is sent on the first call (no stored timestamp)."""
        cron, icp, mail_model, mail_instance = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'First alert', 'body')

        mail_model.create.assert_called_once()

    def test_timestamp_written_after_successful_send(self):
        """ir.config_parameter.set_param is called with the cooldown key after a successful send."""
        cron, icp, mail_model, _ = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'subj', 'body')

        set_calls = [c for c in icp.set_param.call_args_list
                     if c[0][0] == 'mml_3pl.last_alert.stock_3pl_mainfreight']
        self.assertEqual(len(set_calls), 1)

    def test_timestamp_not_written_when_send_raises(self):
        """set_param is NOT called if mail.mail.send() raises."""
        cron, icp, mail_model, mail_instance = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
        })
        mail_instance.send.side_effect = Exception('SMTP failure')

        cron._send_cron_alert('stock_3pl_mainfreight', 'subj', 'body')

        set_calls = [c for c in icp.set_param.call_args_list
                     if c[0][0] == 'mml_3pl.last_alert.stock_3pl_mainfreight']
        self.assertEqual(len(set_calls), 0)

    def test_body_is_html_escaped(self):
        """HTML special characters in body are escaped before insertion into <pre>."""
        cron, icp, mail_model, _ = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'subj', '<script>alert(1)</script>')

        create_kwargs = mail_model.create.call_args[0][0]
        self.assertIn('&lt;script&gt;', create_kwargs['body_html'])
        self.assertNotIn('<script>', create_kwargs['body_html'])

    def test_malformed_stored_timestamp_sends_alert(self):
        """A malformed stored timestamp does not suppress the alert (fail-open)."""
        cron, icp, mail_model, _ = self._make_cron_with_icp({
            'mml.cron_alert_email': 'ops@example.com',
            'mml_3pl.last_alert.stock_3pl_mainfreight': 'not-a-datetime',
        })

        cron._send_cron_alert('stock_3pl_mainfreight', 'subj', 'body')

        mail_model.create.assert_called_once()

    def test_no_alert_when_email_not_configured(self):
        """When mml.cron_alert_email is not set, _send_cron_alert returns without sending."""
        cron, icp, mail_model, _ = self._make_cron_with_icp({})

        cron._send_cron_alert('stock_3pl_mainfreight', 'subj', 'body')

        mail_model.create.assert_not_called()
```

**Step 2: Run tests to confirm they FAIL**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mml.3pl.intergration"
pytest addons/stock_3pl_mainfreight/tests/test_tracking_cron.py::TestSendCronAlertRateLimiting -v
```

Expected: All 8 tests FAIL (`AttributeError` or assertion failures — `_ALERT_COOLDOWN_SECONDS` does not exist, cooldown logic missing, no `html.escape`).

**Step 3: Commit the failing tests**

```bash
git add addons/stock_3pl_mainfreight/tests/test_tracking_cron.py
git commit -m "test(tracking_cron): write failing tests for alert rate-limiting and XSS escaping"
```

---

## Task 2: Implement the fix

**File:** `mml.3pl.intergration/addons/stock_3pl_mainfreight/models/tracking_cron.py`

**Step 1: Make the minimal changes**

1. Add `import html` to the imports at the top (after `import re`)
2. Add `from datetime import datetime, timezone` to the imports
3. Add the module-level constant after the `_TERMINAL_STATUSES` declaration:
   ```python
   # One alert per hour per module — prevents inbox flooding on repeated failures.
   _ALERT_COOLDOWN_SECONDS = 3600
   ```
4. Replace the entire `_send_cron_alert` method body with the rate-limited version:

```python
def _send_cron_alert(self, module_name: str, subject: str, body: str) -> None:
    """Send an email alert when a scheduled action fails.

    Rate-limited to one alert per hour per module to prevent alert storms.
    Timestamp stored in ir.config_parameter under mml_3pl.last_alert.<module>.
    """
    alert_email = self.env['ir.config_parameter'].sudo().get_param(
        'mml.cron_alert_email', False
    )
    if not alert_email:
        return

    # Rate limiting: suppress if an alert was sent within the cooldown window.
    param_key = 'mml_3pl.last_alert.%s' % module_name
    ICP = self.env['ir.config_parameter'].sudo()
    last_alert_str = ICP.get_param(param_key, '')
    if last_alert_str:
        try:
            last_alert = datetime.fromisoformat(last_alert_str)
            if last_alert.tzinfo is None:
                last_alert = last_alert.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_alert).total_seconds()
            if elapsed < _ALERT_COOLDOWN_SECONDS:
                _logger.debug(
                    '3PL alert suppressed for %s (%.0fs ago, cooldown %ds)',
                    module_name, elapsed, _ALERT_COOLDOWN_SECONDS,
                )
                return
        except (ValueError, TypeError):
            pass  # Malformed stored value — send the alert.

    try:
        self.env['mail.mail'].sudo().create({
            'subject': '[MML ALERT] %s: %s' % (module_name, subject),
            'body_html': '<pre>%s</pre>' % html.escape(body),
            'email_to': alert_email,
        }).send()
        # Record timestamp only after a successful send.
        ICP.set_param(param_key, datetime.now(timezone.utc).isoformat())
    except Exception:
        _logger.exception('Failed to send cron alert email for %s', module_name)
```

**Step 2: Run the tests to confirm they PASS**

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mml.3pl.intergration"
pytest addons/stock_3pl_mainfreight/tests/test_tracking_cron.py -v
```

Expected: All tests pass including the 8 new ones.

**Step 3: Run the full 3PL test suite to check for regressions**

```bash
pytest addons/ -m "not odoo_integration" -q
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add addons/stock_3pl_mainfreight/models/tracking_cron.py
git commit -m "fix(tracking_cron): add alert rate-limiting and html.escape to _send_cron_alert

Matches the pattern already in mml_edi/edi_processor.py.
- Suppresses duplicate alerts within a 1-hour cooldown window
- Stores last-alert timestamp in ir.config_parameter (mml_3pl.last_alert.<module>)
- Adds html.escape() to prevent XSS in alert body_html
- Fails open on malformed stored timestamp (sends alert rather than suppressing)"
```

---

## Task 3: Push and update the root repo ref

```bash
cd "E:/ClaudeCode/projects/mml.odoo.apps/mml.3pl.intergration"
git push origin master

cd "E:/ClaudeCode/projects/mml.odoo.apps"
git add mml.3pl.intergration
git commit -m "chore: update mml.3pl.intergration ref after tracking cron alert fix"
git push origin master
```

---

## Done — verification checklist

- [ ] `TestSendCronAlertRateLimiting` — all 8 tests pass
- [ ] Full `pytest addons/ -m "not odoo_integration" -q` — zero failures
- [ ] `tracking_cron.py` has `_ALERT_COOLDOWN_SECONDS`, `html.escape()`, and the `mml_3pl.last_alert.*` key pattern
- [ ] `ir.config_parameter` docs updated — add `mml_3pl.last_alert.<module>` to the system parameters table in `mml.3pl.intergration/CLAUDE.md`
