from minidev.system import pick_model


def test_pick_model_under_16gb() -> None:
    assert pick_model(8) == "qwen2.5-coder:7b"


def test_pick_model_between_16_and_32gb() -> None:
    assert pick_model(16) == "qwen2.5-coder:14b"
    assert pick_model(32) == "qwen2.5-coder:14b"


def test_pick_model_over_32gb() -> None:
    assert pick_model(32.1) == "qwen2.5-coder:32b"
