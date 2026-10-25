"""Tools the agent can call.

Every tool is a small, side-effect-contained function that writes under the output
directory. Real integrations (Jira, e-mail, Slack...) can replace these handlers
without touching the agent: only the :class:`Tool` contract matters.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


class ToolError(RuntimeError):
    """A tool failed (bad arguments, I/O error, ...)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema ("properties" + "required")
    handler: Callable[..., str]

    def schema(self) -> dict[str, Any]:
        """Description in the shape LLM tool-calling APIs expect."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {"type": "object", **self.parameters},
        }


class ToolRegistry:
    """Holds the available tools and validates calls before executing them."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].schema() for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def validate(self, name: str, arguments: dict[str, Any]) -> None:
        """Raise :class:`ToolError` unless ``arguments`` match the tool's schema."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool '{name}'")
        properties: dict[str, dict[str, Any]] = tool.parameters.get("properties", {})
        for key in tool.parameters.get("required", []):
            if key not in arguments:
                raise ToolError(f"Tool '{name}': missing argument '{key}'")
        for key, value in arguments.items():
            spec = properties.get(key)
            if spec is None:
                raise ToolError(f"Tool '{name}': unexpected argument '{key}'")
            expected = JSON_TYPES.get(spec.get("type", "string"), str)
            if not isinstance(value, expected) or (isinstance(value, bool) and expected is int):
                raise ToolError(f"Tool '{name}': argument '{key}' must be {spec.get('type')}")
            if "enum" in spec and value not in spec["enum"]:
                raise ToolError(f"Tool '{name}': '{key}' must be one of {spec['enum']}")

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.validate(name, arguments)
        return self._tools[name].handler(**arguments)


# --------------------------------------------------------------------------- default tools


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")[:80] or "document"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_default_registry(output_dir: Path, source: str = "document") -> ToolRegistry:
    """Create the standard tool set, writing under ``output_dir/actions``."""
    base = Path(output_dir) / "actions"

    def create_ticket(title: str, priority: str, details: str) -> str:
        ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"
        path = base / "tickets" / f"{ticket_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": ticket_id,
            "created_at": _now(),
            "source": source,
            "title": title,
            "priority": priority,
            "details": details,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"ticket {ticket_id} created ({path.name})"

    def send_alert(channel: str, message: str) -> str:
        _append_jsonl(
            base / "alerts.jsonl",
            {"at": _now(), "source": source, "channel": channel, "message": message},
        )
        return f"alert sent to '{channel}' (simulated outbox)"

    def request_human_review(reason: str) -> str:
        _append_jsonl(
            base / "review_queue.jsonl", {"at": _now(), "source": source, "reason": reason}
        )
        return "document queued for human review"

    def archive_document(status: str) -> str:
        _append_jsonl(
            base / "archive.jsonl", {"at": _now(), "source": _slug(source), "status": status}
        )
        return f"document archived with status '{status}'"

    return ToolRegistry(
        [
            Tool(
                "create_ticket",
                "Open a maintenance/quality ticket for a critical finding.",
                {
                    "properties": {
                        "title": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "details": {"type": "string"},
                    },
                    "required": ["title", "priority", "details"],
                },
                create_ticket,
            ),
            Tool(
                "send_alert",
                "Notify a team channel about a problem that needs quick attention.",
                {
                    "properties": {
                        "channel": {"type": "string", "enum": ["maintenance", "quality", "safety"]},
                        "message": {"type": "string"},
                    },
                    "required": ["channel", "message"],
                },
                send_alert,
            ),
            Tool(
                "request_human_review",
                "Put the document in the manual review queue (missing or doubtful data).",
                {"properties": {"reason": {"type": "string"}}, "required": ["reason"]},
                request_human_review,
            ),
            Tool(
                "archive_document",
                "Archive the processed document with a final status.",
                {
                    "properties": {"status": {"type": "string", "enum": ["ok", "needs_attention"]}},
                    "required": ["status"],
                },
                archive_document,
            ),
        ]
    )
