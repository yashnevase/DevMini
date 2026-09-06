from minidev.health import collect_checks, configured_editor, run_fixes
from minidev.manifest import Manifest
from minidev.system import CommandStatus


def test_configured_editor_ignores_manual_install(monkeypatch) -> None:
    monkeypatch.setattr("minidev.health.load_config", lambda: {"editor": {"name": "manual", "configured": False}})

    assert configured_editor() is None


def test_run_fixes_repairs_opencode_config(monkeypatch, tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}\n")
    manifest = Manifest(tmp_path / "manifest.json")
    called = {"configured": False}

    monkeypatch.setattr(
        "minidev.health.command_status",
        lambda name: CommandStatus(name, f"/bin/{name}", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.health.config_path", lambda: config)
    monkeypatch.setattr("minidev.health.ollama_running", lambda: True)
    monkeypatch.setattr("minidev.health.model_present", lambda model: True)
    monkeypatch.setattr("minidev.health.opencode_config_present", lambda *args, **kwargs: False)
    monkeypatch.setattr("minidev.health.editor_integration_status", lambda: type("Result", (), {"ok": True})())
    monkeypatch.setattr("minidev.health.check_structured_tool_calls", lambda model: type("ToolCalls", (), {"ok": True})())

    def fake_configure(manifest_arg, table, dry_run=False, model=None, tool_calls=True):
        called["configured"] = True
        return "manual"

    monkeypatch.setattr("minidev.health.configure_editor_and_opencode", fake_configure)

    run_fixes("qwen2.5-coder:14b", manifest)

    assert called["configured"] is True


def test_collect_checks_reports_local_only_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        "minidev.health.load_config",
        lambda: {"model": "qwen3:30b-a3b", "provider": "ollama", "model_policy": {"local_only": True}},
    )
    monkeypatch.setattr(
        "minidev.health.command_status",
        lambda name: CommandStatus(name, f"/bin/{name}", "1.0", installed=True, working=True),
    )
    monkeypatch.setattr("minidev.health.ollama_running", lambda: True)
    monkeypatch.setattr("minidev.health.model_present", lambda model: True)
    monkeypatch.setattr("minidev.health.opencode_config_present", lambda model=None: True)
    monkeypatch.setattr("minidev.health.editor_integration_status", lambda: type("Result", (), {"ok": True, "detail": "ZED ACP"})())
    monkeypatch.setattr("minidev.health.check_structured_tool_calls", lambda model: type("ToolCalls", (), {"ok": True, "detail": "STRUCTURED"})())
    monkeypatch.setattr("minidev.health.git_repo_detected", lambda path: True)

    checks = collect_checks("qwen3:30b-a3b")

    assert any(check.name == "Model policy" and check.ok and check.detail == "LOCAL ONLY" for check in checks)
