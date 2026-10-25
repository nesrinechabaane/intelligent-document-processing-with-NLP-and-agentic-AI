from __future__ import annotations

import json
from pathlib import Path

import pytest

from idp_agent.tools import Tool, ToolError, ToolRegistry, build_default_registry


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    return build_default_registry(tmp_path, source="doc.txt")


def test_ticket_is_written_as_json(registry: ToolRegistry, tmp_path: Path) -> None:
    message = registry.call(
        "create_ticket", {"title": "Leak", "priority": "high", "details": "flange"}
    )
    (ticket,) = (tmp_path / "actions" / "tickets").glob("TCK-*.json")
    data = json.loads(ticket.read_text(encoding="utf-8"))
    assert data["title"] == "Leak" and data["source"] == "doc.txt"
    assert ticket.stem in message


def test_jsonl_tools_append(registry: ToolRegistry, tmp_path: Path) -> None:
    registry.call("send_alert", {"channel": "safety", "message": "one"})
    registry.call("send_alert", {"channel": "safety", "message": "two"})
    lines = (tmp_path / "actions" / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["message"] for line in lines] == ["one", "two"]


@pytest.mark.parametrize(
    ("name", "arguments", "fragment"),
    [
        ("delete_everything", {}, "Unknown tool"),
        ("send_alert", {"channel": "safety"}, "missing argument 'message'"),
        ("send_alert", {"channel": "safety", "message": "x", "extra": 1}, "unexpected argument"),
        ("send_alert", {"channel": "nowhere", "message": "x"}, "must be one of"),
        ("send_alert", {"channel": "safety", "message": 3}, "must be string"),
    ],
)
def test_invalid_calls_are_rejected(
    registry: ToolRegistry, name: str, arguments: dict, fragment: str
) -> None:
    with pytest.raises(ToolError, match=fragment):
        registry.call(name, arguments)


def test_bool_is_not_accepted_as_integer() -> None:
    tool = Tool("t", "d", {"properties": {"n": {"type": "integer"}}, "required": ["n"]}, str)
    registry = ToolRegistry([tool])
    with pytest.raises(ToolError):
        registry.validate("t", {"n": True})


def test_duplicate_registration_fails(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError):
        registry.register(Tool("send_alert", "dup", {}, str))


def test_schemas_follow_llm_tool_format(registry: ToolRegistry) -> None:
    schema = registry.schemas()[0]
    assert {"name", "description", "input_schema"} <= schema.keys()
    assert schema["input_schema"]["type"] == "object"
