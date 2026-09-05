from minidev.install import model_present


def test_model_present_parses_ollama_list(monkeypatch) -> None:
    class Proc:
        returncode = 0
        stdout = "NAME ID SIZE MODIFIED\nqwen2.5-coder:14b abc 9 GB now\n"

    def fake_run(*args, **kwargs):
        return Proc()

    monkeypatch.setattr("subprocess.run", fake_run)

    assert model_present("qwen2.5-coder:14b") is True
    assert model_present("qwen2.5-coder:7b") is False
