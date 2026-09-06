from minidev.model_catalog import model_candidates, pick_preferred_model, profile_models
from minidev.system import SystemInfo


def test_apple_silicon_16gb_prefers_smaller_qwen3_max() -> None:
    system = SystemInfo(os_name="Darwin", os_release="1", machine="arm64", ram_gb=16)

    assert pick_preferred_model(system) == "qwen3:4b-instruct"
    assert [candidate.model for candidate in model_candidates(system)][:3] == [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen3:4b-instruct",
    ]
    assert profile_models(system)["max"].model == "qwen3:4b-instruct"


def test_small_ram_uses_qwen3_as_max_and_coder_as_low() -> None:
    system = SystemInfo(os_name="Darwin", os_release="1", machine="arm64", ram_gb=8)

    assert pick_preferred_model(system) == "qwen3:4b-instruct"
    assert profile_models(system)["low"].model == "qwen2.5-coder:7b"
