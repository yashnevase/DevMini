import json

from minidev.manifest import FileTouch, Manifest, ModelTouch, PackageTouch


def test_manifest_records_and_upserts(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    manifest = Manifest(path)

    manifest.record_file(FileTouch("/tmp/config.json", "config", "write"))
    manifest.record_file(FileTouch("/tmp/config.json", "config", "rewrite"))
    manifest.record_package(PackageTouch("ollama", "brew", "install", "1.0"))
    manifest.record_model(ModelTouch("qwen2.5-coder:7b", "ollama", "pull"))
    manifest.save()

    data = json.loads(path.read_text())
    assert len(data["files"]) == 1
    assert data["files"][0]["action"] == "rewrite"
    assert data["packages"][0]["name"] == "ollama"
    assert data["models"][0]["name"] == "qwen2.5-coder:7b"
    assert "_key" not in data["packages"][0]


def test_manifest_preserves_created_file_ownership(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    manifest = Manifest(path)

    manifest.record_file(FileTouch("/tmp/memory.md", "context", "create"))
    manifest.record_file(FileTouch("/tmp/memory.md", "study", "append"))
    manifest.save()

    data = json.loads(path.read_text())
    assert data["files"][0]["action"] == "create"
