import pytest

from minidev.chat import (
    configured_profile_model,
    enforce_local_model_args,
    extract_local_model_arg,
    extract_profile_arg,
    minidev_prompt,
    run_acp,
    run_chat,
    split_run_args,
)
from minidev.system import CommandStatus


def test_run_chat_uses_minidev_agent(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(
        "minidev.chat.command_status",
        lambda command: CommandStatus(command, "/bin/opencode", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.chat.load_config", lambda: {"model": "qwen3:30b-a3b"})
    monkeypatch.setattr("subprocess.call", lambda command: called.setdefault("command", command) or 0)

    with pytest.raises(BaseException):
        run_chat(["--mini"])

    assert called["command"] == ["opencode", "--agent", "minidev", "--model", "ollama/qwen3:30b-a3b", "--mini"]


def test_run_chat_with_prompt_uses_run(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(
        "minidev.chat.command_status",
        lambda command: CommandStatus(command, "/bin/opencode", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.chat.load_config", lambda: {"model": "qwen3:30b-a3b"})
    monkeypatch.setattr("subprocess.call", lambda command: called.setdefault("command", command) or 0)

    with pytest.raises(BaseException):
        run_chat(["hello"])

    assert called["command"] == [
        "opencode",
        "run",
        "--agent",
        "minidev",
        "--model",
        "ollama/qwen3:30b-a3b",
        minidev_prompt(["hello"]),
    ]
    assert "User request:\nhello" in called["command"][-1]


def test_run_chat_with_flag_before_prompt_uses_run(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(
        "minidev.chat.command_status",
        lambda command: CommandStatus(command, "/bin/opencode", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.chat.load_config", lambda: {"model": "qwen3:8b"})
    monkeypatch.setattr("subprocess.call", lambda command: called.setdefault("command", command) or 0)

    with pytest.raises(BaseException):
        run_chat(["--print-logs", "hello"])

    assert called["command"][:6] == ["opencode", "run", "--agent", "minidev", "--model", "ollama/qwen3:8b"]
    assert called["command"][6] == "--print-logs"
    assert "User request:\nhello" in called["command"][-1]


def test_split_run_args_preserves_option_values() -> None:
    opencode_args, message_args = split_run_args(["--session", "abc", "hello"])

    assert opencode_args == ["--session", "abc"]
    assert message_args == ["hello"]


def test_run_acp_sets_cwd(monkeypatch, tmp_path) -> None:
    called = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "minidev.chat.command_status",
        lambda command: CommandStatus(command, "/bin/opencode", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("subprocess.call", lambda command: called.setdefault("command", command) or 0)

    with pytest.raises(BaseException):
        run_acp([])

    assert called["command"] == ["opencode", "acp", "--cwd", str(tmp_path)]


def test_enforce_local_model_rejects_opencode_models() -> None:
    with pytest.raises(Exception):
        enforce_local_model_args(["--model", "opencode/big-pickle"])


def test_extract_local_model_arg_returns_ollama_override() -> None:
    model, args = extract_local_model_arg(["--model", "ollama/qwen3:4b-instruct", "hello"])

    assert model == "ollama/qwen3:4b-instruct"
    assert args == ["hello"]


def test_run_chat_honors_local_model_override(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(
        "minidev.chat.command_status",
        lambda command: CommandStatus(command, "/bin/opencode", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.chat.load_config", lambda: {"model": "qwen3:8b"})
    monkeypatch.setattr("subprocess.call", lambda command: called.setdefault("command", command) or 0)

    with pytest.raises(BaseException):
        run_chat(["--model", "ollama/qwen3:4b-instruct", "hello"])

    assert called["command"][:6] == ["opencode", "run", "--agent", "minidev", "--model", "ollama/qwen3:4b-instruct"]


def test_enforce_local_model_rejects_other_agents() -> None:
    with pytest.raises(Exception):
        enforce_local_model_args(["--agent", "build"])


def test_extract_profile_arg_removes_profile_flag() -> None:
    profile, args = extract_profile_arg(["--profile", "low", "hello"])

    assert profile == "low"
    assert args == ["hello"]


def test_configured_profile_model_reads_profile_map() -> None:
    config = {
        "model_policy": {
            "profiles": {
                "low": {"model": "qwen2.5-coder:7b"},
                "medium": {"model": "qwen2.5-coder:14b"},
                "max": {"model": "qwen3:30b-a3b"},
            }
        }
    }

    assert configured_profile_model(config, "max") == "qwen3:30b-a3b"
