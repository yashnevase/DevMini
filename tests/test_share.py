import json

import pytest

from minidev.share import normalize_endpoint, run_connect, share_is_running, write_remote_zed_agent_config
from minidev.system import CommandStatus


def test_normalize_endpoint_rejects_loopback() -> None:
    with pytest.raises(Exception):
        normalize_endpoint("127.0.0.1:4096", "token")


def test_normalize_endpoint_adds_auth_url() -> None:
    result = normalize_endpoint("192.168.1.10:4096", "abc-123")

    assert result["public_url"] == "http://192.168.1.10:4096"
    assert result["auth_url"] == "http://opencode:abc-123@192.168.1.10:4096"


def test_run_connect_writes_remote_config_and_launcher(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("minidev.state.home_dir", lambda: home)
    monkeypatch.setattr(
        "minidev.share.command_status",
        lambda *args, **kwargs: CommandStatus("code", None, None, installed=False, working=False),
    )

    run_connect("192.168.1.10:4096", "secret-token")

    remote = json.loads((home / ".minidev" / "remote.json").read_text())
    config = json.loads((home / ".minidev" / "config.json").read_text())
    launcher = home / ".minidev" / "bin" / "minidev-opencode-remote"

    assert remote["remote"]["url"] == "http://192.168.1.10:4096"
    assert remote["remote"]["token"] == "secret-token"
    assert config["remote"]["url"] == "http://192.168.1.10:4096"
    assert "opencode attach" in launcher.read_text()
    assert launcher.stat().st_mode & 0o700 == 0o700


def test_share_is_running_requires_active_process(monkeypatch) -> None:
    monkeypatch.setattr("minidev.share.process_alive", lambda pid: pid == 123)

    assert share_is_running({"active": True, "opencode": {"pid": 123}}) is True
    assert share_is_running({"active": True, "opencode": {"pid": 456}}) is False
    assert share_is_running({"active": False, "opencode": {"pid": 123}}) is False


def test_write_remote_zed_agent_config_points_to_launcher(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher = home / ".minidev" / "bin" / "minidev-opencode-remote"
    monkeypatch.setattr("minidev.state.home_dir", lambda: home)

    path, existed = write_remote_zed_agent_config(launcher)

    data = json.loads(path.read_text())
    assert existed is False
    assert data["agent_servers"]["MiniDev Remote"]["command"] == str(launcher)
