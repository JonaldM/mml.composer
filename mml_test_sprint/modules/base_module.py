"""Abstract base class for all module test runners."""
from abc import ABC, abstractmethod

from mml_test_sprint.browser import BrowserSession
from mml_test_sprint.checks import ModuleResult, Check, Status


class BaseModuleTest(ABC):
    """Subclass this for each installed module."""

    module_name: str = ""
    module_label: str = ""

    def __init__(self, session: BrowserSession):
        self.s = session
        self.result = ModuleResult(
            module_name=self.module_name,
            module_label=self.module_label,
        )

    def add_smoke(self, check: Check):
        self.result.smoke.append(check)

    def add_spec(self, check: Check):
        self.result.spec.append(check)

    def add_workflow(self, check: Check):
        self.result.workflows.append(check)

    def run(self) -> ModuleResult:
        print(f"\n{'='*60}")
        print(f"  {self.module_label} ({self.module_name})")
        print(f"{'='*60}")
        try:
            print("  [smoke]")
            self.run_smoke()
        except Exception as e:
            self.add_smoke(Check("smoke_suite_error", Status.FAIL, str(e)))

        try:
            print("  [spec]")
            self.run_spec()
        except Exception as e:
            self.add_spec(Check("spec_suite_error", Status.FAIL, str(e)))

        try:
            print("  [workflows]")
            self.run_workflows()
        except Exception as e:
            self.add_workflow(Check("workflow_suite_error", Status.FAIL, str(e)))

        self.result.console_errors = self.s.drain_errors()
        self._print_summary()
        return self.result

    def _print_summary(self):
        print(f"  Smoke:     {self.result.smoke_score}")
        print(f"  Spec:      {self.result.spec_score}")
        print(f"  Workflows: {self.result.workflow_score}")
        print(f"  Overall:   {self.result.overall_status.value.upper()}")

    @abstractmethod
    def run_smoke(self): ...

    @abstractmethod
    def run_spec(self): ...

    @abstractmethod
    def run_workflows(self): ...
