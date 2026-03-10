"""Check result types used throughout the suite."""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class Check:
    name: str
    status: Status
    detail: str = ""
    screenshot_b64: Optional[str] = None  # base64-encoded PNG, set by browser helper


@dataclass
class ModuleResult:
    module_name: str
    module_label: str          # e.g. "ROQ Forecast"
    installed: bool = True
    smoke: list = field(default_factory=list)    # list[Check]
    spec: list = field(default_factory=list)     # list[Check]
    workflows: list = field(default_factory=list) # list[Check]
    console_errors: list = field(default_factory=list)  # list[str]

    @property
    def smoke_score(self) -> str:
        passed = sum(1 for c in self.smoke if c.status == Status.PASS)
        return f"{passed}/{len(self.smoke)}"

    @property
    def spec_score(self) -> str:
        passed = sum(1 for c in self.spec if c.status == Status.PASS)
        return f"{passed}/{len(self.spec)}"

    @property
    def workflow_score(self) -> str:
        passed = sum(1 for c in self.workflows if c.status == Status.PASS)
        return f"{passed}/{len(self.workflows)}"

    @property
    def overall_status(self) -> Status:
        all_checks = self.smoke + self.spec + self.workflows
        if not all_checks:
            return Status.SKIP
        failures = [c for c in all_checks if c.status == Status.FAIL]
        warns = [c for c in all_checks if c.status == Status.WARN]
        if failures:
            return Status.FAIL
        if warns:
            return Status.WARN
        return Status.PASS
