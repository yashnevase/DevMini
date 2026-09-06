from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCallCheck:
    ok: bool
    detail: str


def check_structured_tool_calls(model: str, timeout: int = 45) -> ToolCallCheck:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Call the list_files tool for the current directory."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ],
        "stream": False,
    }
    try:
        request = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return ToolCallCheck(False, f"UNREACHABLE: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ToolCallCheck(False, "BAD RESPONSE")

    if isinstance(data.get("error"), str):
        return ToolCallCheck(False, "NO TOOL SUPPORT")

    message = data.get("message")
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            return ToolCallCheck(True, "STRUCTURED")
        content = message.get("content")
        if looks_like_tool_json(content):
            return ToolCallCheck(False, "TEXT TOOL JSON")
    return ToolCallCheck(False, "NO STRUCTURED CALL")


def looks_like_tool_json(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return '"name"' in text and '"arguments"' in text
