from __future__ import annotations

from pathlib import Path

from idp_agent.agent import DocumentAgent
from idp_agent.config import Settings
from idp_agent.models import DocType, ExtractedDocument, Finding, Severity
from idp_agent.planner import Plan, PlannedAction
from idp_agent.tools import Tool, ToolRegistry, build_default_registry

CRITICAL = [Finding(rule="limits", severity=Severity.CRITICAL, message="too high")]


def _doc() -> ExtractedDocument:
    return ExtractedDocument(source="s", doc_type=DocType.MAINTENANCE_REPORT, confidence=1.0)


class ScriptedPlanner:
    name = "scripted"

    def __init__(self, *actions: PlannedAction) -> None:
        self._actions = list(actions)

    def plan(self, doc, findings, registry) -> Plan:
        return Plan(list(self._actions))


def _flaky_registry(failures: int, calls: list[int]) -> ToolRegistry:
    """A registry whose 'create_ticket' fails ``failures`` times, then succeeds."""

    def create_ticket(title: str, priority: str, details: str) -> str:
        calls.append(1)
        if len(calls) <= failures:
            raise OSError("disk busy")
        return "ticket created"

    schema = {
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string"},
            "details": {"type": "string"},
        },
        "required": ["title", "priority", "details"],
    }
    noop = {"properties": {"status": {"type": "string"}}, "required": ["status"]}
    return ToolRegistry(
        [
            Tool("create_ticket", "t", schema, create_ticket),
            Tool(
                "request_human_review",
                "r",
                {"properties": {"reason": {"type": "string"}}, "required": ["reason"]},
                lambda reason: "queued",
            ),
            Tool("archive_document", "a", noop, lambda status: "archived"),
        ]
    )


def _agent(settings: Settings, registry: ToolRegistry, planner=None) -> DocumentAgent:
    return DocumentAgent(
        settings,
        planner=planner,
        registry_factory=lambda *_: registry,
        sleep=lambda _: None,
    )


def test_transient_failure_is_retried(settings: Settings) -> None:
    calls: list[int] = []
    outcome = _agent(settings, _flaky_registry(2, calls)).run(_doc(), CRITICAL)
    ticket = next(r for r in outcome.actions if r.tool == "create_ticket")
    assert ticket.ok and ticket.attempts == 3 and len(calls) == 3


def test_backoff_is_exponential(settings: Settings) -> None:
    delays: list[float] = []
    agent = DocumentAgent(
        settings.with_updates(retry_backoff=1.0),
        registry_factory=lambda *_: _flaky_registry(2, []),
        sleep=delays.append,
    )
    agent.run(_doc(), CRITICAL)
    assert delays == [1.0, 2.0]


def test_permanent_failure_triggers_recovery(settings: Settings) -> None:
    outcome = _agent(settings, _flaky_registry(99, [])).run(_doc(), CRITICAL)
    ticket = next(r for r in outcome.actions if r.tool == "create_ticket")
    assert not ticket.ok and ticket.attempts == settings.max_retries
    assert any(r.tool == "request_human_review" and r.ok for r in outcome.actions)
    assert any("Verification failed" in note for note in outcome.notes)


def test_invalid_call_is_not_retried(settings: Settings, tmp_path: Path) -> None:
    bad = PlannedAction("send_alert", {"channel": "nowhere", "message": "x"})
    registry = build_default_registry(tmp_path)
    outcome = _agent(settings, registry, ScriptedPlanner(bad)).run(_doc(), [])
    alert = next(r for r in outcome.actions if r.tool == "send_alert")
    assert not alert.ok and alert.attempts == 1 and alert.result.startswith("rejected")


def test_guardrail_adds_ticket_when_planner_forgets(settings: Settings, tmp_path: Path) -> None:
    registry = build_default_registry(tmp_path)
    outcome = _agent(settings, registry, ScriptedPlanner()).run(_doc(), CRITICAL)
    assert [r.tool for r in outcome.actions] == ["create_ticket", "archive_document"]
    assert any("Guardrail" in note for note in outcome.notes)


def test_archive_is_always_last_and_unique(settings: Settings, tmp_path: Path) -> None:
    registry = build_default_registry(tmp_path)
    planner = ScriptedPlanner(
        PlannedAction("archive_document", {"status": "ok"}),
        PlannedAction("request_human_review", {"reason": "r"}),
        PlannedAction("request_human_review", {"reason": "r"}),
    )
    outcome = _agent(settings, registry, planner).run(_doc(), CRITICAL)
    tools = [r.tool for r in outcome.actions]
    assert tools == ["request_human_review", "create_ticket", "archive_document"]
    assert outcome.actions[-1].arguments == {"status": "needs_attention"}


def test_planner_name_is_reported(settings: Settings, tmp_path: Path) -> None:
    outcome = _agent(settings, build_default_registry(tmp_path)).run(_doc(), [])
    assert outcome.planner == "rules"
