# Quality Hardening Sprint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the one critical security gap (hardcoded SSH credentials in deployment scripts), close test coverage gaps, add FTP circuit breaker, add correlation-ID logging, write the ROQ→Freight→3PL E2E integration test, and produce the two missing documentation artefacts — all in one sprint.

**Architecture:** Each task is self-contained and independently testable. Tasks 2–7 are independent of each other and can be parallelised. Task 1 (credentials) must go first because it touches git history.

**Tech Stack:** Python 3.11, Odoo 19, paramiko, pytest, python-dotenv (scripts only — not installed in Odoo)

---

## Task 1: Strip hardcoded SSH credentials from deployment scripts

> Must be done first. All other tasks can run in parallel after this one.

**Files:**
- Create: `ssh_utils.py` (repo root — alongside the four scripts)
- Modify: `patch_and_install.py` (remove `connect()` / `run()` / `write_remote()`, import from ssh_utils)
- Modify: `patch_roq_settings.py` (same)
- Modify: `patch_views.py` (same)
- Modify: `restart_and_verify.py` (same; also remove hardcoded password from `sudo -S` calls)
- Create: `.env.example` (repo root)
- Modify: `.gitignore` (add `.env`, `ssh.txt`)

**Context:** The four deployment scripts (`patch_and_install.py`, `patch_roq_settings.py`, `patch_views.py`, `restart_and_verify.py`) each contain an identical `connect()` function with the SSH host, username, and password hardcoded at lines 7–8. The server is Tailscale-only so there is no active external exposure, but the credentials are in git history and must be removed. The fix: extract a shared `ssh_utils.py` at the repo root, update all four scripts to import it, then strip history with BFG.

**Note on `sudo -S`:** `restart_and_verify.py` also passes the password inline to `sudo -S` on lines 29, 31, 46, 68. These are replaced with a `sudo_run()` that pipes via stdin (avoids the password appearing in `ps aux` and avoids shell escaping issues with special characters in passwords).

- [ ] **Step 1: Write the shared SSH util module**

Create `ssh_utils.py` at the repo root (same directory as `patch_and_install.py`):

```python
"""
Shared SSH connection helper for MML deployment scripts.

Reads connection details from environment variables.
Copy .env.example to .env and fill in values before running any script.
Never commit .env to git.
"""
import os
import paramiko


def connect() -> paramiko.SSHClient:
    host = os.environ["MML_SSH_HOST"]
    user = os.environ["MML_SSH_USER"]
    password = os.environ["MML_SSH_PASSWORD"]

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.WarningPolicy())
    c.connect(host, username=user, password=password, timeout=30)
    c.get_transport().set_keepalive(30)
    return c


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120):
    if not client.get_transport() or not client.get_transport().is_active():
        raise RuntimeError("SSH session dropped")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    err_clean = "\n".join(l for l in err.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def sudo_run(client: paramiko.SSHClient, cmd: str, timeout: int = 120):
    """
    Run a command under sudo, piping the password via stdin.
    Safer than echo-piping: password never appears in remote process list,
    and no shell escaping issues with special characters in the password.
    """
    password = os.environ["MML_SSH_PASSWORD"]
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd} 2>&1", timeout=timeout)
    stdin.write(password + "\n")
    stdin.flush()
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    out_clean = "\n".join(l for l in out.splitlines() if not l.startswith("[sudo]"))
    return rc, out_clean, err_clean


def write_remote(client: paramiko.SSHClient, path: str, content: str) -> None:
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(content.encode("utf-8") if isinstance(content, str) else content)
    sftp.close()
```

- [ ] **Step 2: Create .env.example at repo root**

```
# Copy this file to .env and fill in values before running deployment scripts.
# Never commit .env to git — it is in .gitignore.
MML_SSH_HOST=
MML_SSH_USER=
MML_SSH_PASSWORD=
```

- [ ] **Step 3: Add secrets to .gitignore and delete ssh.txt**

Add to the repo root `.gitignore`:

```
# Deployment script secrets
.env
ssh.txt
*.pem
*.key
```

Then delete the working-tree copy of ssh.txt and unstage it so it does not get re-committed:

```bash
git rm --cached ssh.txt 2>/dev/null; rm -f ssh.txt
```

- [ ] **Step 4: Update patch_and_install.py**

Replace the top of the file (lines 1–28: the bare `import` block plus the three function definitions `connect`, `run`, `write_remote`) with:

```python
import sys
import time
from pathlib import Path

# Load env vars from .env if present (local dev convenience)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not required; export env vars manually instead

from ssh_utils import connect, run, write_remote
```

The rest of the file (from `PATCHED_FORECAST_CONFIG = ...` onward) is unchanged.

- [ ] **Step 5: Apply the same replacement to patch_roq_settings.py and patch_views.py**

Both scripts have the same 25-line block (lines 1–25). Replace with the same import block above, omitting `time` if unused in that script.

- [ ] **Step 6: Update restart_and_verify.py**

Replace the top import block (lines 1–26) with the same pattern, adding `sudo_run` to the import:

```python
import sys
import time
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from ssh_utils import connect, run, sudo_run, write_remote
```

Then replace each inline `sudo -S` call (lines 29, 31, 46, 68). Example:

Before:
```python
rc, out, err = run(client, "echo '***REDACTED***' | sudo -S systemctl start odoo19.service 2>&1")
```
After:
```python
rc, out, err = sudo_run(client, "systemctl start odoo19.service")
```

Apply the same pattern to all four `sudo` calls. The `psql` calls that also use `echo '***REDACTED***' | sudo -S -u postgres` follow the same pattern.

- [ ] **Step 7: Strip git history with BFG Repo-Cleaner**

This is a one-time manual step requiring the actual password value. Run from a Linux/macOS shell or WSL (BFG uses `/tmp/` — on Windows native, substitute `%TEMP%`):

```bash
# 1. Fresh bare clone
git clone --mirror <repo-url> repo-mirror.git
cd repo-mirror.git

# 2. Create replacement file (one literal per line)
echo "***REDACTED***" > /tmp/passwords.txt   # WSL/Linux/macOS
# On Windows native: echo ***REDACTED*** > %TEMP%\passwords.txt

# 3. Replace all occurrences of the password in blobs
java -jar bfg.jar --replace-text /tmp/passwords.txt .

# 4. Also delete ssh.txt from all historical blobs
java -jar bfg.jar --delete-files ssh.txt .

# 5. Clean refs and GC
git reflog expire --expire=now --all && git gc --prune=now --aggressive

# 6. Force push (coordinate with team — all local clones must be re-cloned after this)
git push --force
```

- [ ] **Step 8: Verify scripts work**

```bash
export MML_SSH_HOST=<tailscale-ip>
export MML_SSH_USER=jono
export MML_SSH_PASSWORD=<password>
python restart_and_verify.py
```

Expected: connects, runs module-state checks, exits 0. No credential in any log line.

- [ ] **Step 9: Commit**

```bash
git add ssh_utils.py .env.example patch_and_install.py \
        patch_roq_settings.py patch_views.py restart_and_verify.py \
        .gitignore
git commit -m "security: extract SSH credentials to env vars in deployment scripts"
```

---

## Task 2: EDIFACT encoding edge-case tests

> Can run in parallel with Tasks 3–7 after Task 1 is committed.

**Files:**
- Modify: `mml_edi/tests/test_briscoes_edifact_parser.py`
- Create (optional): `mml_edi/tests/fixtures/briscoes_orders_x92_terminator.edi`

**Context:** The existing parser tests (`TestOrdersParsing`, `TestChangeOrderParsing`) cover the happy path against real fixture files. They do not test the `\x92` Windows-1252 encoding normalisation path, the UNA service string skip, empty-file handling, or an unrecognised BGM code. These are the gaps.

The `_split_segments()` function at `briscoes.py:67–109` decodes as `cp1252`, maps `\u2019` → `'`, then splits on `'`. The critical path is: if a file's segment terminators are byte `0x92` (cp1252 right single quote), they must produce the same segments as byte `0x27` (standard apostrophe).

- [ ] **Step 1: Write the failing tests**

Append this class to `mml_edi/tests/test_briscoes_edifact_parser.py`:

```python
class TestEdgeCases:
    """Tests for encoding edge cases and malformed input — no fixture files needed."""

    def test_x92_terminator_produces_same_result_as_standard_quote(self):
        """
        EDIFACT files from some Briscoes EDIS endpoints use byte 0x92
        (Windows-1252 right single quotation mark) as the segment terminator
        instead of the standard 0x27 (apostrophe).

        Both must parse identically.
        """
        standard = (
            b"UNB+UNOA:3+VENDOR:ZZ+BUYER:14+261122:0900+00001++ORDERS'"
            b"UNH+1+ORDERS:D:96A:UN:EAN005'"
            b"BGM+220+4500099999+9'"
            b"DTM+137:20261122:102'"
            b"NAD+BY+9421234567890::92'"
            b"NAD+SU+VENDOR::92'"
            b"LIN+00010++9414844375629:EN'"
            b"QTY+21:24.000:EA'"
            b"QTY+11:12.000:EA'"
            b"QTY+52:6.000:EA'"
            b"PRI+AAA:5.50'"
            b"LOC+7+1005::92'"
            b"DTM+2:20261216:102'"
            b"UNS+S'"
            b"CNT+2:1'"
            b"UNT+14+1'"
            b"UNZ+1+00001'"
        )
        # Replace 0x27 with 0x92 throughout
        x92_version = standard.replace(b"'", b"\x92")

        from mml_edi.parsers.briscoes import BriscoesParser
        from unittest.mock import MagicMock
        partner = MagicMock()
        parser = BriscoesParser()

        result_standard = parser.parse_file(standard, partner)
        result_x92 = parser.parse_file(x92_version, partner)

        assert len(result_standard) == len(result_x92)
        assert result_standard[0].po_number == result_x92[0].po_number
        assert result_standard[0].lines[0].product_code == result_x92[0].lines[0].product_code
        assert result_standard[0].lines[0].quantity == result_x92[0].lines[0].quantity

    def test_empty_file_returns_empty_list(self):
        from mml_edi.parsers.briscoes import BriscoesParser
        from unittest.mock import MagicMock
        parser = BriscoesParser()
        result = parser.parse_file(b"", MagicMock())
        assert result == []

    def test_whitespace_only_file_returns_empty_list(self):
        from mml_edi.parsers.briscoes import BriscoesParser
        from unittest.mock import MagicMock
        parser = BriscoesParser()
        result = parser.parse_file(b"   \r\n  ", MagicMock())
        assert result == []

    def test_una_service_string_skipped(self):
        """Files with UNA prefix must parse the same as files without it."""
        from mml_edi.parsers.briscoes import BriscoesParser
        from unittest.mock import MagicMock

        body = (
            b"UNB+UNOA:3+VENDOR:ZZ+BUYER:14+261122:0900+00001++ORDERS'"
            b"UNH+1+ORDERS:D:96A:UN:EAN005'"
            b"BGM+220+4500099999+9'"
            b"DTM+137:20261122:102'"
            b"NAD+BY+9421234567890::92'"
            b"NAD+SU+VENDOR::92'"
            b"LIN+00010++9414844375629:EN'"
            b"QTY+11:12.000:EA'"
            b"PRI+AAA:5.50'"
            b"LOC+7+1005::92'"
            b"UNS+S'"
            b"CNT+2:1'"
            b"UNT+11+1'"
            b"UNZ+1+00001'"
        )
        with_una = b"UNA:+.? '" + body
        partner = MagicMock()
        parser = BriscoesParser()

        result_plain = parser.parse_file(body, partner)
        result_una = parser.parse_file(with_una, partner)

        assert len(result_plain) == len(result_una)
        assert result_plain[0].po_number == result_una[0].po_number

    def test_unrecognised_bgm_type_raises(self):
        """BGM codes other than 220 (ORDERS) and 230 (ORDCHG) must raise EDIParseError."""
        from mml_edi.parsers.briscoes import BriscoesParser
        from mml_edi.parsers.base_parser import EDIParseError
        from unittest.mock import MagicMock

        bad_msg = (
            b"UNH+1+ORDERS:D:96A:UN:EAN005'"
            b"BGM+999+4500099999+9'"
            b"UNS+S'"
            b"UNT+3+1'"
            b"UNZ+1+00001'"
        )
        with pytest.raises(EDIParseError, match="Unrecognised BGM"):
            BriscoesParser().parse_file(bad_msg, MagicMock())

    def test_missing_po_number_raises(self):
        """BGM with empty PO number must raise EDIParseError."""
        from mml_edi.parsers.briscoes import BriscoesParser
        from mml_edi.parsers.base_parser import EDIParseError
        from unittest.mock import MagicMock

        bad_msg = (
            b"UNH+1+ORDERS:D:96A:UN:EAN005'"
            b"BGM+220++9'"
            b"UNS+S'"
            b"UNT+3+1'"
            b"UNZ+1+00001'"
        )
        with pytest.raises(EDIParseError, match="missing PO number"):
            BriscoesParser().parse_file(bad_msg, MagicMock())

    def test_invalid_bytes_produce_replacement_char_warning_not_crash(self):
        """
        Bytes invalid in Windows-1252 (e.g. 0x81) should produce a warning
        via _logger.warning and not crash — the replacement char path.
        """
        from mml_edi.parsers.briscoes import BriscoesParser
        from unittest.mock import MagicMock, patch
        import logging

        raw_with_bad_byte = (
            b"UNH+1+ORDERS:D:96A:UN:EAN005'"
            b"BGM+220+4500099999+9'"
            b"\x81"  # invalid in cp1252 — becomes \ufffd replacement char
            b"UNS+S'"
            b"UNT+3+1'"
            b"UNZ+1+00001'"
        )
        with patch("mml_edi.parsers.briscoes._logger") as mock_logger:
            # Should not raise; may return [] due to missing NAD+LIN
            try:
                BriscoesParser().parse_file(raw_with_bad_byte, MagicMock())
            except Exception:
                pass
            # Must have logged a warning about invalid bytes
            assert mock_logger.warning.called
            warning_call = str(mock_logger.warning.call_args)
            assert "invalid" in warning_call.lower() or "corrupt" in warning_call.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd E:/ClaudeCode/projects/mml.odoo/mml.odoo.apps
pytest mml_edi/tests/test_briscoes_edifact_parser.py::TestEdgeCases -v
```

Expected: Most pass immediately (the parser already handles these). If `test_x92_terminator_produces_same_result_as_standard_quote` fails, the `_split_segments` normalisation has a bug — fix it before proceeding.

- [ ] **Step 3: Run the full EDI test suite**

```bash
pytest mml_edi/tests/ -m "not odoo_integration" -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add mml_edi/tests/test_briscoes_edifact_parser.py
git commit -m "test: add EDIFACT encoding edge-case tests (x92 terminator, UNA, empty file)"
```

---

## Task 3: ROQ edge-case tests

> Can run in parallel with Tasks 2, 4–7 after Task 1.

**Files:**
- Create: `mml.roq.model/mml_roq_forecast/tests/test_edge_cases.py`

**Context:** The ROQ test suite has good coverage of the happy path (normal demand, well-stocked SKUs, container filling). The gaps are: (1) zero/negative weekly demand fed into forecasting methods, (2) a SKU that has never sold (demand_history returns empty), (3) pathological container fill where no single SKU fills an LCL container. Relevant services: `ForecastMethods` (`services/forecast_methods.py`), `ABCClassifier` (`services/abc_classifier.py`), `ContainerFitter` (`services/container_fitter.py`), `SafetyStock` (`services/safety_stock.py`).

- [ ] **Step 1: Write the failing tests**

Create `mml.roq.model/mml_roq_forecast/tests/test_edge_cases.py`:

```python
"""
ROQ edge-case tests: zero demand, never-sold SKUs, pathological container fill.

Pure Python — no Odoo runtime needed.
Run with:  pytest mml.roq.model/mml_roq_forecast/tests/test_edge_cases.py -v

API reference (actual module-level functions, not classes):
  forecast_methods: forecast_sma(history, window=52)
                    forecast_ewma(history, span=26)
                    forecast_holt_winters(history, seasonal_period=52, ...)
  safety_stock:     calculate_safety_stock(z_score, sigma, lt_weeks)
  abc_classifier:   AbcClassifier(env).classify_from_revenues(revenue_map, ...)
  container_fitter: ContainerFitter(lcl_threshold_pct=50).fit(lines)
                    lines = [{'product_id', 'cbm', 'roq', 'cbm_per_unit', 'tier', 'weeks_cover'}]
"""
import pytest


class TestZeroDemand:
    """forecast_methods module functions with all-zero weekly sales history."""

    def test_sma_on_all_zeros_returns_zero(self):
        from mml_roq_forecast.services.forecast_methods import forecast_sma
        result = forecast_sma([0.0] * 52, window=12)
        assert result == 0.0

    def test_sma_on_empty_history_returns_zero(self):
        from mml_roq_forecast.services.forecast_methods import forecast_sma
        result = forecast_sma([], window=12)
        assert result == 0.0

    def test_ewma_on_all_zeros_returns_zero(self):
        from mml_roq_forecast.services.forecast_methods import forecast_ewma
        result = forecast_ewma([0.0] * 52, span=26)
        assert result == 0.0

    def test_ewma_on_empty_history_returns_zero(self):
        from mml_roq_forecast.services.forecast_methods import forecast_ewma
        result = forecast_ewma([], span=26)
        assert result == 0.0

    def test_holt_winters_on_all_zeros_returns_nonnegative(self):
        """Holt-Winters on a flat-zero series must not raise and must return >= 0."""
        from mml_roq_forecast.services.forecast_methods import forecast_holt_winters
        result = forecast_holt_winters([0.0] * 104)  # 2 full seasonal cycles required
        assert result >= 0.0

    def test_holt_winters_falls_back_to_sma_with_insufficient_data(self):
        """Fewer than 2 × seasonal_period points must not raise — falls back to SMA."""
        from mml_roq_forecast.services.forecast_methods import forecast_holt_winters
        result = forecast_holt_winters([5.0] * 10)  # Too few for HW
        assert isinstance(result, float)
        assert result >= 0.0


class TestSafetyStock:
    """calculate_safety_stock edge cases."""

    def test_zero_z_score_tier_d_returns_zero(self):
        """Tier D z-score is 0 — safety stock must be 0 regardless of sigma."""
        from mml_roq_forecast.services.safety_stock import calculate_safety_stock
        result = calculate_safety_stock(z_score=0.0, sigma=10.0, lt_weeks=4.0)
        assert result == 0.0

    def test_zero_sigma_returns_zero(self):
        """Zero std dev of demand (perfectly flat demand) → zero safety stock."""
        from mml_roq_forecast.services.safety_stock import calculate_safety_stock
        result = calculate_safety_stock(z_score=1.645, sigma=0.0, lt_weeks=4.0)
        assert result == 0.0

    def test_zero_lead_time_returns_zero(self):
        """Zero lead time → zero safety stock (nothing to buffer)."""
        from mml_roq_forecast.services.safety_stock import calculate_safety_stock
        result = calculate_safety_stock(z_score=1.645, sigma=5.0, lt_weeks=0.0)
        assert result == 0.0

    def test_normal_inputs_return_positive(self):
        """Standard inputs must produce a positive safety stock."""
        from mml_roq_forecast.services.safety_stock import calculate_safety_stock
        result = calculate_safety_stock(z_score=1.645, sigma=5.0, lt_weeks=4.0)
        assert result > 0.0


class TestNeverSoldSKU:
    """AbcClassifier when a SKU has zero revenue contribution."""

    def test_zero_revenue_sku_classified_as_d(self):
        """A SKU with zero revenue must map to D tier."""
        from mml_roq_forecast.services.abc_classifier import AbcClassifier
        from unittest.mock import MagicMock
        classifier = AbcClassifier(env=MagicMock())
        result = classifier.classify_from_revenues({"sku_001": 0.0})
        assert result.get("sku_001") == "D"

    def test_zero_total_revenue_does_not_divide_by_zero(self):
        """If ALL SKUs have zero revenue, must not raise ZeroDivisionError."""
        from mml_roq_forecast.services.abc_classifier import AbcClassifier
        from unittest.mock import MagicMock
        classifier = AbcClassifier(env=MagicMock())
        # Should not raise
        result = classifier.classify_from_revenues({"sku_001": 0.0, "sku_002": 0.0})
        assert all(v in ("A", "B", "C", "D") for v in result.values())

    def test_single_sku_with_revenue_classifies_as_a(self):
        """A single SKU with all the revenue → 100% contribution → A tier."""
        from mml_roq_forecast.services.abc_classifier import AbcClassifier
        from unittest.mock import MagicMock
        classifier = AbcClassifier(env=MagicMock())
        result = classifier.classify_from_revenues({"sku_001": 1000.0})
        assert result.get("sku_001") == "A"


class TestContainerFitter:
    """ContainerFitter.fit() edge cases."""

    def _make_line(self, product_id=1, cbm=5.0, roq=100, cbm_per_unit=0.05,
                   tier="B", weeks_cover=8.0):
        return {
            "product_id": product_id,
            "cbm": cbm,
            "roq": roq,
            "cbm_per_unit": cbm_per_unit,
            "tier": tier,
            "weeks_cover": weeks_cover,
        }

    def test_single_small_sku_is_lcl(self):
        """
        A single SKU with 5 CBM total is below the 50% LCL threshold
        for the smallest container (20GP = 25 CBM). Must return LCL.
        """
        from mml_roq_forecast.services.container_fitter import ContainerFitter
        fitter = ContainerFitter(lcl_threshold_pct=50)
        result = fitter.fit([self._make_line(cbm=5.0)])
        assert result["container_type"] == "LCL", (
            "5 CBM is below 50% of 20GP (12.5 CBM threshold) — expected LCL"
        )

    def test_missing_cbm_per_unit_returns_unassigned(self):
        """Lines with cbm_per_unit <= 0 must return 'unassigned', not raise."""
        from mml_roq_forecast.services.container_fitter import ContainerFitter
        fitter = ContainerFitter(lcl_threshold_pct=50)
        line = self._make_line(cbm=30.0, cbm_per_unit=0.0)
        result = fitter.fit([line])
        assert result["container_type"] == "unassigned"

    def test_fill_pct_is_between_zero_and_one(self):
        """fill_pct in fit() result must always be in [0.0, 1.0]."""
        from mml_roq_forecast.services.container_fitter import ContainerFitter
        fitter = ContainerFitter(lcl_threshold_pct=50)
        line = self._make_line(cbm=20.0, cbm_per_unit=0.2, roq=100)
        result = fitter.fit([line])
        assert 0.0 <= result["fill_pct"] <= 1.0

    def test_large_shipment_selects_largest_container(self):
        """60 CBM must be assigned to 40HQ (67.5 CBM), not 40GP (55 CBM)."""
        from mml_roq_forecast.services.container_fitter import ContainerFitter
        fitter = ContainerFitter(lcl_threshold_pct=50)
        line = self._make_line(cbm=60.0, cbm_per_unit=0.3, roq=200)
        result = fitter.fit([line])
        assert result["container_type"] == "40HQ", (
            "60 CBM exceeds 40GP (55 CBM) — must select 40HQ (67.5 CBM)"
        )


class TestNegativeDemand:
    """Guard against returns/credits producing negative demand in forecasts."""

    def test_sma_with_negative_history_returns_nonnegative(self):
        """SMA on a history that includes returns (negative weeks) must be >= 0."""
        from mml_roq_forecast.services.forecast_methods import forecast_sma
        history = [10.0, -5.0, 8.0, -2.0, 15.0, 0.0] * 8 + [10.0, 12.0, 8.0, 9.0]
        result = forecast_sma(history, window=12)
        assert result >= 0.0

    def test_ewma_with_negative_history_returns_nonnegative(self):
        from mml_roq_forecast.services.forecast_methods import forecast_ewma
        history = [10.0, -5.0, 8.0, -2.0, 15.0, 0.0] * 8 + [10.0, 12.0, 8.0, 9.0]
        result = forecast_ewma(history, span=26)
        assert result >= 0.0
```

- [ ] **Step 2: Run the tests**

```bash
cd E:/ClaudeCode/projects/mml.odoo/mml.odoo.apps
pytest mml.roq.model/mml_roq_forecast/tests/test_edge_cases.py -v
```

Expected: Some tests FAIL (negative demand clamping, zero total revenue divide-by-zero, HW nonnegative return). These are the real gaps.

- [ ] **Step 3: Fix each failure**

For each failing test, open the relevant service file and add the minimal guard:

**Negative demand clamping** (`services/forecast_methods.py`) — at the `return` of `forecast_sma` and `forecast_ewma`:
```python
# Before:
return sum(recent) / len(recent)
# After:
return max(0.0, sum(recent) / len(recent))
```

**Zero total revenue** (`services/abc_classifier.py`) in `classify_from_revenues`:
```python
# Before:
total_revenue = sum(revenue_map.values())
# After:
total_revenue = sum(revenue_map.values())
if total_revenue <= 0:
    return {k: 'D' for k in revenue_map}
```

**Holt-Winters nonnegative** (`services/forecast_methods.py`) — at the return:
```python
return max(0.0, result)
```

- [ ] **Step 4: Run the full ROQ test suite**

```bash
pytest mml.roq.model/ -m "not odoo_integration" -q
```

Expected: All tests pass, including existing ones.

- [ ] **Step 5: Commit**

```bash
git add mml.roq.model/mml_roq_forecast/tests/test_edge_cases.py \
        mml.roq.model/mml_roq_forecast/services/forecast_methods.py \
        mml.roq.model/mml_roq_forecast/services/abc_classifier.py
git commit -m "test(roq): add edge-case tests for zero/negative demand, never-sold SKUs, container fitting"
```

---

## Task 4: FTP circuit breaker for EDI polling

> Can run in parallel with Tasks 2, 3, 5–7 after Task 1.

**Files:**
- Modify: `mml_edi/models/edi_trading_partner.py` (add circuit breaker fields)
- Modify: `mml_edi/models/edi_processor.py` (check + update circuit state in cron)
- Create: `mml_edi/tests/test_circuit_breaker.py`

**Context:** The EDI cron calls `EDIFTPHandler.connect()` which retries 4 times within a single poll run. If the FTP server is down for hours, the cron fires every 15 min, each time exhausting all 4 retry attempts before giving up. This generates excessive log noise and keeps the Odoo cron scheduler busy. A circuit breaker on `edi.trading.partner` tracks consecutive failures and opens the circuit (skips polling) for a cooldown period.

**Circuit breaker rules:**
- Open circuit after `circuit_failure_threshold` consecutive poll failures (default: 5)
- Cooldown: `circuit_cooldown_minutes` minutes (default: 60)
- Auto-reset: if the last failure was more than `circuit_cooldown_minutes` ago, try again (half-open)
- Successful poll resets `circuit_failure_count` to 0

- [ ] **Step 1: Write the failing test**

Create `mml_edi/tests/test_circuit_breaker.py`:

```python
"""
Circuit breaker logic for EDI FTP polling.
Tests the open/close/half-open state transitions on edi.trading.partner.

Pure Python — no Odoo runtime needed.
Run with:  pytest mml_edi/tests/test_circuit_breaker.py -v
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


def _make_partner(failure_count=0, open_since=None, threshold=5, cooldown=60):
    """Build a minimal mock trading partner with circuit breaker state."""
    partner = MagicMock()
    partner.code = "TEST"
    partner.circuit_failure_count = failure_count
    partner.circuit_open_since = open_since
    partner.circuit_failure_threshold = threshold
    partner.circuit_cooldown_minutes = cooldown
    return partner


class TestCircuitBreakerState:

    def test_circuit_is_closed_with_no_failures(self):
        from mml_edi.models.edi_trading_partner import circuit_is_open
        partner = _make_partner(failure_count=0)
        assert circuit_is_open(partner) is False

    def test_circuit_opens_after_threshold_failures(self):
        from mml_edi.models.edi_trading_partner import circuit_is_open
        now = datetime.now(timezone.utc)
        partner = _make_partner(failure_count=5, open_since=now)
        assert circuit_is_open(partner) is True

    def test_circuit_is_half_open_after_cooldown_expires(self):
        from mml_edi.models.edi_trading_partner import circuit_is_open
        # Circuit opened 90 minutes ago (past the 60-min cooldown)
        old_open = datetime.now(timezone.utc) - timedelta(minutes=90)
        partner = _make_partner(failure_count=5, open_since=old_open, cooldown=60)
        # Half-open: should return False (allow one attempt)
        assert circuit_is_open(partner) is False

    def test_circuit_stays_open_within_cooldown(self):
        from mml_edi.models.edi_trading_partner import circuit_is_open
        # Circuit opened 30 minutes ago, cooldown is 60 min
        recent_open = datetime.now(timezone.utc) - timedelta(minutes=30)
        partner = _make_partner(failure_count=5, open_since=recent_open, cooldown=60)
        assert circuit_is_open(partner) is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd E:/ClaudeCode/projects/mml.odoo/mml.odoo.apps
pytest mml_edi/tests/test_circuit_breaker.py -v
```

Expected: `ImportError` — `circuit_is_open` does not exist yet.

- [ ] **Step 3: Add circuit breaker fields to EDITradingPartner**

In `mml_edi/models/edi_trading_partner.py`, add after the `alert_on_issues` field (line ~155):

```python
# ── Circuit Breaker ───────────────────────────────────────────────

circuit_failure_count = fields.Integer(
    default=0,
    string="Consecutive Poll Failures",
    readonly=True,
    help="Number of consecutive FTP poll failures since last success.",
)
circuit_open_since = fields.Datetime(
    string="Circuit Open Since",
    readonly=True,
    help="Timestamp when the circuit breaker tripped. Cleared on successful poll.",
)
circuit_failure_threshold = fields.Integer(
    default=5,
    string="Failure Threshold",
    help="Number of consecutive failures before the circuit opens and polling pauses.",
)
circuit_cooldown_minutes = fields.Integer(
    default=60,
    string="Cooldown (minutes)",
    help="Minutes to wait before retrying after the circuit trips.",
)
```

- [ ] **Step 4: Add the circuit_is_open helper function**

Add to the bottom of `mml_edi/models/edi_trading_partner.py` (outside the class, it's a pure function so tests can import it without Odoo):

```python
def circuit_is_open(partner) -> bool:
    """
    Return True if the circuit breaker is open (polling should be skipped).

    States:
      CLOSED: failure_count < threshold — poll normally
      OPEN:   failure_count >= threshold AND within cooldown — skip
      HALF-OPEN: failure_count >= threshold AND cooldown expired — allow one attempt
    """
    if partner.circuit_failure_count < partner.circuit_failure_threshold:
        return False
    if not partner.circuit_open_since:
        return False
    from datetime import datetime, timezone, timedelta
    cooldown = timedelta(minutes=partner.circuit_cooldown_minutes)
    open_since = partner.circuit_open_since
    if not open_since.tzinfo:
        open_since = open_since.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - open_since
    return elapsed < cooldown
```

- [ ] **Step 5: Wire into the EDI cron**

In `mml_edi/models/edi_processor.py`, find `run_scheduled_poll` (the cron entry point). Add circuit breaker checks:

```python
# At the top of run_scheduled_poll, before connecting to FTP:
from .edi_trading_partner import circuit_is_open

for partner in active_partners:
    if circuit_is_open(partner):
        _logger.info(
            "[EDI] Circuit breaker OPEN for %s — skipping poll "
            "(failures=%d, open_since=%s, cooldown=%dmin)",
            partner.code,
            partner.circuit_failure_count,
            partner.circuit_open_since,
            partner.circuit_cooldown_minutes,
        )
        continue
    try:
        self._poll_partner(partner)
        # Success — reset circuit
        partner.write({"circuit_failure_count": 0, "circuit_open_since": False})
    except Exception as exc:
        new_count = partner.circuit_failure_count + 1
        vals = {"circuit_failure_count": new_count}
        if new_count >= partner.circuit_failure_threshold and not partner.circuit_open_since:
            from odoo import fields as ofields
            vals["circuit_open_since"] = ofields.Datetime.now()
            _logger.error(
                "[EDI] Circuit breaker TRIPPED for %s after %d consecutive failures",
                partner.code, new_count,
            )
        partner.write(vals)
        raise
```

- [ ] **Step 6: Run the circuit breaker tests**

```bash
pytest mml_edi/tests/test_circuit_breaker.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 7: Run the full EDI test suite**

```bash
pytest mml_edi/tests/ -m "not odoo_integration" -q
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add mml_edi/models/edi_trading_partner.py mml_edi/models/edi_processor.py \
        mml_edi/tests/test_circuit_breaker.py
git commit -m "feat(edi): add FTP circuit breaker to edi.trading.partner"
```

---

## Task 5: Correlation-ID structured logging in EDI processor

> Can run in parallel with Tasks 2–4, 6–7 after Task 1.

**Files:**
- Modify: `mml_edi/models/edi_processor.py`
- Create: `mml_edi/tests/test_correlation_logging.py`

**Context:** When an EDI poll processes multiple files, log lines from different files are interleaved with no way to correlate them. Adding a `session_id` (short UUID prefix) to each log call inside a poll run makes it trivial to `grep` a single file's processing history from production logs.

**Approach:** Generate a `session_id = secrets.token_hex(4)` at the start of each poll run, and thread it through all `_logger` calls in that run as a prefix: `[EDI:abc12345]`. No changes to external interfaces.

- [ ] **Step 1: Write the test**

Create `mml_edi/tests/test_correlation_logging.py`:

```python
"""
Verify that EDI processor log output includes session correlation IDs.
Pure Python — no Odoo runtime needed.
"""
import logging
import pytest
from unittest.mock import patch, MagicMock


class TestCorrelationId:

    def test_session_id_format(self):
        """
        build_session_id() must return an 8-character lowercase hex string,
        suitable for use as [EDI:<id>] log prefix.
        """
        import re
        try:
            from mml_edi.models.edi_processor import build_session_id
        except ImportError:
            pytest.skip("build_session_id not yet implemented")

        sid = build_session_id()
        assert re.match(r'^[0-9a-f]{8}$', sid), (
            "Session ID must be 8 lowercase hex chars, got: %r" % sid
        )

    def test_two_calls_produce_different_session_ids(self):
        """Each poll run must get a unique session ID."""
        try:
            from mml_edi.models.edi_processor import build_session_id
        except ImportError:
            pytest.skip("build_session_id not yet implemented")

        ids = {build_session_id() for _ in range(20)}
        assert len(ids) > 1, "Session IDs must be unique across calls"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest mml_edi/tests/test_correlation_logging.py -v
```

Expected: `SKIP` (ImportError) — `build_session_id` does not exist yet.

- [ ] **Step 3: Add build_session_id to edi_processor.py**

At the top of `mml_edi/models/edi_processor.py`, after existing imports, add:

```python
import secrets


def build_session_id() -> str:
    """Generate a short unique ID for correlating log messages within one poll run."""
    return secrets.token_hex(4)
```

Then in `run_scheduled_poll` (or `_poll_partner`), generate the ID at the start and prefix all log calls:

```python
def _poll_partner(self, partner):
    sid = build_session_id()
    prefix = "[EDI:%s]" % sid
    _logger.info("%s Starting poll for partner %s", prefix, partner.code)
    # ... rest of poll logic uses prefix in every _logger call
```

- [ ] **Step 4: Run the tests**

```bash
pytest mml_edi/tests/test_correlation_logging.py -v
```

Expected: Both tests pass.

- [ ] **Step 5: Commit**

```bash
git add mml_edi/models/edi_processor.py mml_edi/tests/test_correlation_logging.py
git commit -m "feat(edi): add session correlation ID to EDI poll log output"
```

---

## Task 6: E2E integration test — ROQ → Freight → 3PL event chain

> Can run in parallel with Tasks 2–5, 7 after Task 1. Requires Odoo runtime.

**Files:**
- Create: `mml_roq_freight/tests/test_roq_freight_3pl_e2e.py`

**Context:** The bridge modules `mml_roq_freight` and `mml_freight_3pl` are each tested in isolation. There is no test that fires `roq.shipment_group.confirmed` and verifies that the event flows through: ROQ → (mml_roq_freight bridge) → freight.tender created → (mml_freight module) → freight.booking.confirmed → (mml_freight_3pl bridge) → 3pl.message queued.

This test must run as an Odoo integration test (requires live DB with all three modules installed). It is tagged `odoo_integration`.

- [ ] **Step 1: Write the test**

Create `mml_roq_freight/tests/test_roq_freight_3pl_e2e.py`:

```python
"""
End-to-end integration test: ROQ shipment group → Freight tender → 3PL message.

Verifies the full cross-module event chain:
  1. roq.shipment_group.confirmed event fires
  2. mml_roq_freight bridge creates a freight.tender linked to the shipment group
  3. A freight.booking is confirmed on that tender
  4. mml_freight_3pl bridge queues a 3pl.message (inward_order) for that booking

Run with:
  python odoo-bin --test-enable -u mml_roq_freight,mml_freight_3pl -d <db>
  --test-tags mml_roq_freight:TestROQFreight3PLE2E
"""
import unittest
from odoo.tests.common import TransactionCase

_ODOO_AVAILABLE = hasattr(TransactionCase, "env")


@unittest.skipUnless(_ODOO_AVAILABLE, "Requires Odoo runtime")
class TestROQFreight3PLE2E(TransactionCase):

    def setUp(self):
        super().setUp()
        # These module checks let the test fail fast with a clear message
        # rather than an obscure AttributeError if a module isn't installed
        for module_name in ("mml_roq_freight", "mml_freight_3pl", "mml_freight"):
            mod = self.env["ir.module.module"].search(
                [("name", "=", module_name), ("state", "=", "installed")]
            )
            if not mod:
                self.skipTest("%s is not installed in this database" % module_name)

    def _make_shipment_group(self):
        """Create a minimal roq.shipment.group in 'draft' state."""
        return self.env["roq.shipment.group"].create({
            "name": "E2E-TEST-SG-001",
            "state": "draft",
            # Add any required fields here based on the model definition
        })

    def test_confirmed_shipment_group_creates_freight_tender(self):
        """
        Confirming a roq.shipment_group must create a freight.tender
        linked back via freight_tender_id.
        """
        sg = self._make_shipment_group()
        self.assertFalse(sg.freight_tender_id, "No tender before confirmation")

        sg.action_confirm()  # fires roq.shipment_group.confirmed event

        sg.invalidate_recordset()
        self.assertTrue(
            sg.freight_tender_id,
            "freight_tender_id must be set after shipment group confirmation",
        )
        tender = sg.freight_tender_id
        self.assertEqual(
            tender.shipment_group_id.id, sg.id,
            "freight.tender must link back to the shipment group",
        )

    def test_confirmed_freight_booking_queues_3pl_message(self):
        """
        Confirming a freight.booking must cause mml_freight_3pl bridge
        to queue a 3pl.message of type 'inward_order'.
        """
        sg = self._make_shipment_group()
        sg.action_confirm()
        sg.invalidate_recordset()
        tender = sg.freight_tender_id
        self.assertTrue(tender, "Prerequisite: shipment group must produce a tender")

        # Create a minimal freight.booking on the tender
        booking = self.env["freight.booking"].create({
            "tender_id": tender.id,
            "state": "draft",
        })

        messages_before = self.env["3pl.message"].search_count([
            ("booking_id", "=", booking.id),
            ("message_type", "=", "inward_order"),
        ])
        self.assertEqual(messages_before, 0)

        booking.action_confirm()  # fires freight.booking.confirmed event

        messages_after = self.env["3pl.message"].search_count([
            ("booking_id", "=", booking.id),
            ("message_type", "=", "inward_order"),
        ])
        self.assertGreater(
            messages_after, 0,
            "Confirming freight.booking must queue a 3pl.message of type inward_order",
        )
```

- [ ] **Step 2: Run the test (Odoo runtime required)**

```bash
python odoo-bin --test-enable -u mml_roq_freight,mml_freight_3pl \
    -d <db> --test-tags mml_roq_freight:TestROQFreight3PLE2E --stop-after-init
```

Expected: Either PASS (if event wiring is correct end-to-end) or a clear assertion failure identifying the exact point the chain breaks.

- [ ] **Step 3: Fix any failures**

If `freight_tender_id` is not set after `action_confirm()`, check that:
- `mml_roq_freight` is installed and its `post_init_hook` registered the event subscription
- The `FreightService.create_tender()` call returns a record (not None/NullService)

If the 3pl.message is not created, check that:
- `mml_freight_3pl` event subscription is registered for `freight.booking.confirmed`
- The `3pl.service.queue_inward_order()` call is not silently swallowed by NullService

- [ ] **Step 4: Commit**

```bash
git add mml_roq_freight/tests/test_roq_freight_3pl_e2e.py
git commit -m "test(e2e): add ROQ → Freight → 3PL full event chain integration test"
```

---

## Task 7: Documentation — Ops runbook and forecasting migration guide

> Can run in parallel with Tasks 2–6 after Task 1.

**Files:**
- Create: `docs/runbook/ops-runbook.md`
- Create: `docs/runbook/forecasting-migration.md`

### 7a: Ops Runbook

- [ ] **Step 1: Create the runbook**

Create `docs/runbook/ops-runbook.md` with the following sections. Fill in specifics from the infrastructure docs in `mml.hiav/`:

```markdown
# MML Odoo Ops Runbook

## Server Access (Tailscale required)

All servers accessible only via Tailscale VPN. If not connected, no access.

| Server | Tailscale IP | Role |
|--------|-------------|------|
| Prem (bare-metal) | 10.0.0.35 | Odoo 15 prod + Odoo 19 dev (port 8073) |
| Hetzner | <hetzner-tailscale-ip> | PG 15 standby + Odoo 19 DR |

SSH: `ssh jono@<tailscale-ip>` (key-based auth required)

## Credential Rotation Procedure

1. Generate new SSH key pair: `ssh-keygen -t ed25519 -f ~/.ssh/mml_ops`
2. Add public key to `~/.ssh/authorized_keys` on target server while current session is active
3. Test new key before closing existing session
4. Remove old key from `authorized_keys`
5. Update `MML_SSH_PASSWORD` env var in deployment environment
6. Run `scripts/restart_and_verify.py` to confirm deployment scripts still work

## Alerting

EDI cron failures send email to addresses configured in `mml.cron_alert_email` (ir.config_parameter).

To add/change alert email:
```sql
UPDATE ir_config_parameter SET value = 'ops@mml.co.nz'
WHERE key = 'mml.cron_alert_email';
```

## EDI Circuit Breaker

If EDI polling stops due to the circuit breaker tripping (check `edi.trading.partner.circuit_failure_count >= circuit_failure_threshold`):

1. Diagnose FTP connectivity: `telnet post.edis.co.nz 21`
2. Check FTP credentials in Odoo: Settings > EDI > Trading Partners
3. If FTP is back: reset circuit via Odoo UI or:
```sql
UPDATE edi_trading_partner SET circuit_failure_count = 0, circuit_open_since = NULL;
```

## PG Replication Status

Check via Tailscale from dev machine:
```bash
bash mml.hiav/check-replication.sh
```

Expected output: replication lag < 60s.

## Odoo 15 → 19 Migration Status

- Prem: Odoo 15 (MML_Production DB) — active production
- Prem: Odoo 19 (MML_EDI_Compat DB, port 8073) — testing new modules
- Hetzner: Odoo 19 + PG 15 standby — planned failover target (Q2 2026)

Failover procedure: `mml.hiav/odoo-ha-migration-plan.md`

## Emergency Contacts

(Fill in from internal contact list)
```

- [ ] **Step 2: Commit the runbook**

```bash
mkdir -p docs/runbook
git add docs/runbook/ops-runbook.md
git commit -m "docs: add ops runbook (server access, EDI circuit breaker, replication checks)"
```

### 7b: Forecasting Migration Guide

- [ ] **Step 3: Create the migration guide**

Create `docs/runbook/forecasting-migration.md`:

```markdown
# ROQ Forecasting Migration Guide

## Overview

The ROQ demand forecasting system exists in three locations. This document explains
the migration path from legacy to new, and which codebase is authoritative at each stage.

## Current State (as of 2026-03-21)

| Codebase | Location | Status | Purpose |
|----------|----------|--------|---------|
| `mml.roq.model/mml_roq_forecast` | `mml.odoo.apps/` | **Active — primary** | Odoo 19 module, installed in MML_EDI_Compat |
| `mml.forecasting/mml_forecast_demand` | `mml.odoo.apps/` | In development | New modular forecasting suite; not yet installed |
| `mml.out.pro.fix/roq_forecast_job_new.py` | `mml.out.pro.fix/` | Calibration scripts | Standalone scripts for parameter calibration; not production |

## Why Three Codebases?

- `mml_roq_forecast` was the original implementation and is in production.
- `mml.forecasting` was designed as a more modular, independently installable SaaS product.
  It separates demand forecasting (`mml_forecast_demand`) from financial forecasting
  (`mml_forecast_financial`), unlike the original which only covers demand.
- `mml.out.pro.fix` contains calibration scripts that were used to tune ROQ constants
  against historical data. They have slightly different default constants.

## Migration Steps

### Phase 1: Stabilise (Current)
- `mml_roq_forecast` remains primary
- `mml.forecasting` modules installed alongside in dev DB for testing
- Do not remove `mml_roq_forecast` until Phase 2 is complete

### Phase 2: Parallel Run
- Install `mml_forecast_demand` in production alongside `mml_roq_forecast`
- Compare outputs for a full 12-month plan cycle (minimum 4 weeks)
- Document any discrepancies in JIRA/Linear

### Phase 3: Cutover
- Set `mml_roq_forecast` to inactive (do not uninstall until DB migration tested)
- `mml_forecast_demand` becomes primary
- Update `mml_roq_freight` bridge module to subscribe to new event names if they differ

### Phase 4: Cleanup
- Uninstall `mml_roq_forecast` from production DB
- Archive `mml.roq.model/` directory
- Remove `mml_roq_freight` compatibility shims if any

## Default Constants — Canonical Values

The authoritative defaults live in `mml_forecast_demand` (new module). These should be
used in `mml_roq_forecast` settings too. Where they differ, the new values are correct.

| Parameter | mml_roq_forecast default | mml_forecast_demand default | Use this |
|-----------|--------------------------|------------------------------|----------|
| Lookback weeks | 156 | 156 | 156 |
| SMA window | 12 | 12 | 12 |
| Container LCL threshold | 0.85 cbm | 15 cbm | 15 cbm (absolute, not pct) |
| Safety stock service level | 0.95 | 0.95 | 0.95 |

Note: The `mml.out.pro.fix` scripts use different defaults — treat them as
calibration artefacts only, not as authoritative values.
```

- [ ] **Step 4: Commit the migration guide**

```bash
git add docs/runbook/forecasting-migration.md
git commit -m "docs: add ROQ forecasting migration guide and canonical default constants"
```

---

## Sprint Execution Order

```
Day 1: Task 1 (security — solo, blocks history rewrite)
       └── git history strip (coordinate with team, all must re-clone)

Days 2–3 (parallel after Task 1 is committed):
  ├── Task 2: EDIFACT edge-case tests
  ├── Task 3: ROQ edge-case tests
  ├── Task 4: FTP circuit breaker
  ├── Task 5: Correlation logging
  └── Task 7: Documentation

Day 4–5:
  └── Task 6: E2E integration test (needs live Odoo DB — schedule a test DB window)
```

## Verification (before sprint close)

```bash
# All pure-Python tests green
pytest -m "not odoo_integration" -q

# No credentials in source
grep -r "Lockitdown" scripts/ && echo "FAIL" || echo "CLEAN"

# Circuit breaker fields present in trading partner
grep -n "circuit_failure_count" mml_edi/models/edi_trading_partner.py

# New doc files present
ls docs/runbook/
```
