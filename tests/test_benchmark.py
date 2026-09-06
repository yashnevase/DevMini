from minidev.benchmark import extract_python_code, run_python_check, count_words_as_tokens, star_rating


def test_star_rating_uses_model_size_band() -> None:
    assert star_rating("qwen2.5-coder:14b", 2) == 1
    assert star_rating("qwen2.5-coder:14b", 12) == 3
    assert star_rating("qwen2.5-coder:14b", 40) == 5


def test_count_words_as_tokens_has_minimum() -> None:
    assert count_words_as_tokens("") == 1
    assert count_words_as_tokens("one two three") == 3


def test_extract_python_code_from_fence() -> None:
    assert extract_python_code("```python\ndef x():\n    return 1\n```") == "def x():\n    return 1"


def test_run_python_check_validates_fixed_coding_task() -> None:
    code = "def first_ten_fibonacci():\n    return [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]"

    passed, detail = run_python_check(code)

    assert passed is True
    assert detail == "PASS"


def test_run_python_check_rejects_wrong_answer() -> None:
    code = "def first_ten_fibonacci():\n    return []"

    passed, detail = run_python_check(code)

    assert passed is False
    assert "expected" in detail
