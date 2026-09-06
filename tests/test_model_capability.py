import json

from minidev.model_capability import check_structured_tool_calls


class DummyResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_check_structured_tool_calls_accepts_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: DummyResponse({"message": {"tool_calls": [{"function": {"name": "list_files"}}]}}),
    )

    result = check_structured_tool_calls("model")

    assert result.ok is True
    assert result.detail == "STRUCTURED"


def test_check_structured_tool_calls_rejects_content_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: DummyResponse({"message": {"content": '{"name":"list_files","arguments":{"path":"."}}'}}),
    )

    result = check_structured_tool_calls("model")

    assert result.ok is False
    assert result.detail == "TEXT TOOL JSON"
