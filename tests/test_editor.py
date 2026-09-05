import json

from minidev.editor import MINIDEV_PERMISSION, merge_permissions, write_opencode_config, write_zed_agent_config
from minidev.manifest import Manifest


def test_merge_permissions_preserves_existing_shell_rules() -> None:
    merged = merge_permissions(
        {
            "bash": {
                "make test": "allow",
                "rm *": "deny",
            },
            "question": "allow",
        },
        MINIDEV_PERMISSION,
    )

    assert merged["question"] == "allow"
    assert merged["bash"]["make test"] == "allow"
    assert merged["bash"]["rm *"] == "ask"
    assert merged["bash"]["rg *"] == "allow"
    assert merged["edit"] == "ask"


def test_write_opencode_config_records_overwrite(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    path = home / ".config" / "opencode" / "opencode.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permission": {"question": "allow"}}))
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    write_opencode_config(manifest, table=DummyTable())

    data = json.loads(path.read_text())
    assert data["permission"]["question"] == "allow"
    assert data["permission"]["bash"]["git commit*"] == "ask"
    assert data["minidev"]["permission_policy"] == "generated"
    assert manifest.data["files"][0]["action"] == "overwrite"


def test_write_zed_agent_config(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    write_zed_agent_config(manifest)

    path = home / ".config" / "zed" / "agents" / "minidev.json"
    data = json.loads(path.read_text())
    assert data["agent_servers"]["MiniDev"]["command"] == "opencode"
    assert data["agent_servers"]["MiniDev"]["args"] == ["acp"]


class DummyTable:
    def add_row(self, *args, **kwargs):
        pass
