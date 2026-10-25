"""The agent loop: plan -> enforce policy -> act with retries -> verify -> recover.

What makes this an *agent* and not a script:

* **Planning**: a planner (rules or LLM) chooses which tools to call.
* **Tool use**: calls go through a schema-validated registry.
* **Guardrails**: policy invariants hold even if the planner (e.g. an LLM) is wrong.
* **Error handling**: transient failures are retried with backoff; permanent ones are
  recorded and trigger a recovery action.
* **Verification**: after acting, the agent checks the invariants really hold.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings
from .models import ActionRecord, ExtractedDocument, Finding, Severity
from .planner import PlannedAction, Planner, RulePlanner
from .tools import ToolError, ToolRegistry, build_default_registry

LOGGER = logging.getLogger(__name__)

RegistryFactory = Callable[[Path, str], ToolRegistry]


@dataclass
class AgentOutcome:
    actions: list[ActionRecord]
    notes: list[str] = field(default_factory=list)
    planner: str = "rules"


class DocumentAgent:
    def __init__(
        self,
        settings: Settings,
        planner: Planner | None = None,
        registry_factory: RegistryFactory = build_default_registry,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._planner = planner or RulePlanner(settings.min_confidence)
        self._registry_factory = registry_factory
        self._sleep = sleep

    @property
    def planner_name(self) -> str:
        return getattr(self._planner, "name", "custom")

    def run(self, doc: ExtractedDocument, findings: list[Finding]) -> AgentOutcome:
        registry = self._registry_factory(self._settings.output_dir, doc.source)
        plan = self._planner.plan(doc, findings, registry)
        notes = list(plan.notes)

        actions = self._enforce_policy(plan.actions, findings, notes)
        records = [self._execute(registry, action) for action in actions]
        self._verify_and_recover(registry, findings, records, notes)
        return AgentOutcome(records, notes, self.planner_name)

    # ------------------------------------------------------------------ guardrails

    @staticmethod
    def _enforce_policy(
        actions: list[PlannedAction], findings: list[Finding], notes: list[str]
    ) -> list[PlannedAction]:
        """Guarantee invariants regardless of what the planner proposed."""
        unique: list[PlannedAction] = []
        for action in actions:
            if action not in unique and action.tool != "archive_document":
                unique.append(action)

        has_critical = any(f.severity is Severity.CRITICAL for f in findings)
        if has_critical and not any(a.tool == "create_ticket" for a in unique):
            details = "; ".join(f.message for f in findings if f.severity is Severity.CRITICAL)
            unique.append(
                PlannedAction(
                    "create_ticket",
                    {"title": "Critical finding", "priority": "high", "details": details[:500]},
                )
            )
            notes.append("Guardrail: added missing ticket for critical finding")

        status = "needs_attention" if findings else "ok"
        unique.append(PlannedAction("archive_document", {"status": status}))
        return unique

    # ------------------------------------------------------------------ execution

    def _execute(self, registry: ToolRegistry, action: PlannedAction) -> ActionRecord:
        last_error = ""
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                result = registry.call(action.tool, action.arguments)
                return ActionRecord(
                    tool=action.tool,
                    arguments=action.arguments,
                    ok=True,
                    result=result,
                    attempts=attempt,
                )
            except ToolError as exc:  # invalid call: retrying cannot help
                last_error = str(exc)
                return ActionRecord(
                    tool=action.tool,
                    arguments=action.arguments,
                    ok=False,
                    result=f"rejected: {last_error}",
                    attempts=attempt,
                )
            except Exception as exc:  # noqa: BLE001 - tools are plug-ins; treat as transient
                last_error = f"{type(exc).__name__}: {exc}"
                LOGGER.warning(
                    "Tool %s failed (attempt %d/%d): %s",
                    action.tool,
                    attempt,
                    self._settings.max_retries,
                    last_error,
                )
                if attempt < self._settings.max_retries:
                    self._sleep(self._settings.retry_backoff * 2 ** (attempt - 1))
        return ActionRecord(
            tool=action.tool,
            arguments=action.arguments,
            ok=False,
            result=f"failed after {self._settings.max_retries} attempts: {last_error}",
            attempts=self._settings.max_retries,
        )

    # ------------------------------------------------------------------ verification

    def _verify_and_recover(
        self,
        registry: ToolRegistry,
        findings: list[Finding],
        records: list[ActionRecord],
        notes: list[str],
    ) -> None:
        has_critical = any(f.severity is Severity.CRITICAL for f in findings)
        ticket_ok = any(r.tool == "create_ticket" and r.ok for r in records)
        if has_critical and not ticket_ok:
            notes.append("Verification failed: no ticket exists for a critical finding")
            fallback = PlannedAction(
                "request_human_review",
                {"reason": "Critical finding but ticket creation failed; manual follow-up needed"},
            )
            record = self._execute(registry, fallback)
            records.append(record)
            if not record.ok:
                notes.append("Recovery failed: manual follow-up required outside the system")
        failed = [r.tool for r in records if not r.ok]
        if failed:
            notes.append(f"Actions failed: {', '.join(failed)}")
