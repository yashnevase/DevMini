from minidev.install import context_model_name, model_present, profile_pull_list
from minidev.model_catalog import ModelCandidate


def test_model_present_parses_ollama_list(monkeypatch) -> None:
    class Proc:
        returncode = 0
        stdout = "NAME ID SIZE MODIFIED\nqwen2.5-coder:14b abc 9 GB now\nminidev-qwen3-4b-instruct-16k:latest def 2.5 GB now\n"

    def fake_run(*args, **kwargs):
        return Proc()

    monkeypatch.setattr("subprocess.run", fake_run)

    assert model_present("qwen2.5-coder:14b") is True
    assert model_present("minidev-qwen3-4b-instruct-16k") is True
    assert model_present("qwen2.5-coder:7b") is False


def test_profile_pull_list_dedupes_profiles() -> None:
    profiles = {
        "low": ModelCandidate("qwen2.5-coder:7b", "low", "", 4.7),
        "medium": ModelCandidate("qwen2.5-coder:14b", "medium", "", 9.0),
        "max": ModelCandidate("qwen3:30b-a3b", "max", "", 19.0),
    }

    assert profile_pull_list(profiles, "qwen3:30b-a3b", all_profiles=True) == [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen3:30b-a3b",
    ]


def test_context_model_name_is_safe_for_ollama() -> None:
    assert context_model_name("qwen3:4b-instruct") == "minidev-qwen3-4b-instruct-16k"
    assert context_model_name("dagbs/qwen2.5-coder-7b:q5_k_m") == "minidev-dagbs-qwen2.5-coder-7b-q5_k_m-16k"
