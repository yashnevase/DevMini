from __future__ import annotations

import json
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .install import model_present
from .state import load_config

OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
BENCHMARK_PROMPT = "Write a concise Python function that returns the first ten Fibonacci numbers."
CODING_BENCHMARK_PROMPT = (
    "Return only Python code. Define a function named first_ten_fibonacci() that returns "
    "the first ten Fibonacci numbers as a list of integers. Do not print anything."
)
REFERENCE_TOKENS_PER_SECOND = {
    "7b": (18.0, 35.0),
    "14b": (10.0, 22.0),
    "32b": (4.0, 10.0),
}
EXPECTED_FIBONACCI = "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]"


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    tokens_per_second: float
    tokens: int
    elapsed_seconds: float
    rating: int


@dataclass(frozen=True)
class CodingBenchmarkResult:
    passed: bool
    detail: str


def run_benchmark(model_override: str | None = None) -> None:
    config = load_config()
    model = model_override or str(config.get("model") or "qwen2.5-coder:7b")

    console.print(title_panel("Benchmarking MiniDev model"))
    table = status_table("Benchmark")
    table.add_row(ok("Model"), badge(model))

    if not model_present(model):
        table.add_row(warn("Model present"), badge("NO", "mini.warn"))
        console.print(table)
        raise typer.BadParameter(f"Model {model} is not present. Run `minidev install --model {model}` first.")

    result = benchmark_model(model)
    coding = benchmark_coding_task(model)
    table.add_row(ok("Prompt"), badge("fixed short prompt"))
    table.add_row(ok("Tokens"), badge(str(result.tokens)))
    table.add_row(ok("Elapsed"), badge(f"{result.elapsed_seconds:.2f}s"))
    table.add_row(ok("Speed"), badge(f"{result.tokens_per_second:.1f} tok/s", "mini.yellow"))
    table.add_row(ok("Coding task") if coding.passed else warn("Coding task"), badge(coding.detail, "mini.ok" if coding.passed else "mini.warn"))
    table.add_row(ok("Rating"), badge(stars(result.rating), "mini.yellow"))
    console.print(table)
    console.print(
        Panel(
            f"[mini.text]Reference band for this model size:[/] [mini.yellow]{reference_label(model)}[/]",
            border_style="mini.box",
            style=f"on {NAVY}",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def benchmark_model(model: str) -> BenchmarkResult:
    started = time.perf_counter()
    payload = ollama_generate(model)
    elapsed = time.perf_counter() - started
    tokens = int(payload.get("eval_count") or count_words_as_tokens(str(payload.get("response") or "")))
    duration_ns = payload.get("eval_duration")
    if isinstance(duration_ns, (int, float)) and duration_ns > 0 and tokens > 0:
        tokens_per_second = tokens / (duration_ns / 1_000_000_000)
    else:
        tokens_per_second = tokens / elapsed if elapsed > 0 else 0.0
    return BenchmarkResult(
        model=model,
        tokens_per_second=tokens_per_second,
        tokens=tokens,
        elapsed_seconds=elapsed,
        rating=star_rating(model, tokens_per_second),
    )


def ollama_generate(model: str) -> dict[str, Any]:
    return ollama_generate_with_prompt(model, BENCHMARK_PROMPT, num_predict=96)


def benchmark_coding_task(model: str) -> CodingBenchmarkResult:
    try:
        payload = ollama_generate_with_prompt(model, CODING_BENCHMARK_PROMPT, num_predict=192)
    except typer.BadParameter as exc:
        return CodingBenchmarkResult(False, str(exc))

    code = extract_python_code(str(payload.get("response") or ""))
    if "first_ten_fibonacci" not in code:
        return CodingBenchmarkResult(False, "FAIL: missing function")

    passed, detail = run_python_check(code)
    return CodingBenchmarkResult(passed, "PASS" if passed else f"FAIL: {detail}")


def ollama_generate_with_prompt(model: str, prompt: str, num_predict: int = 96) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": num_predict,
                "temperature": 0,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(OLLAMA_GENERATE_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            loaded = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        raise typer.BadParameter(f"Benchmark timed out waiting for {model}. Try a smaller profile or close other model sessions.") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            raise typer.BadParameter(
                f"Benchmark timed out waiting for {model}. Try a smaller profile or close other model sessions."
            ) from exc
        raise typer.BadParameter("Ollama is not reachable. Start it with `ollama serve` or run `minidev doctor --fix`.") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("Ollama returned an invalid benchmark response.") from exc
    return loaded if isinstance(loaded, dict) else {}


def extract_python_code(text: str) -> str:
    match = re.search(r"```(?:python|py)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def run_python_check(code: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="minidev-bench-") as tmp:
        module = Path(tmp) / "candidate.py"
        module.write_text(code + "\n", encoding="utf-8")
        runner = (
            "import importlib.util, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('candidate', {str(module)!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "result = mod.first_ten_fibonacci()\n"
            f"expected = {EXPECTED_FIBONACCI}\n"
            "if result != expected:\n"
            "    raise SystemExit(f'expected {expected}, got {result!r}')\n"
        )
        proc = subprocess.run(["python3", "-I", "-c", runner], check=False, capture_output=True, text=True, timeout=10)
    if proc.returncode == 0:
        return True, "PASS"
    detail = (proc.stderr or proc.stdout or "wrong answer").strip().splitlines()[-1]
    return False, detail[:80]


def star_rating(model: str, tokens_per_second: float) -> int:
    low, high = reference_band(model)
    if tokens_per_second <= 0:
        return 1
    if tokens_per_second < low * 0.5:
        return 1
    if tokens_per_second < low:
        return 2
    if tokens_per_second < high:
        return 3
    if tokens_per_second < high * 1.5:
        return 4
    return 5


def reference_band(model: str) -> tuple[float, float]:
    lowered = model.lower()
    for size, band in REFERENCE_TOKENS_PER_SECOND.items():
        if size in lowered:
            return band
    return (8.0, 20.0)


def reference_label(model: str) -> str:
    low, high = reference_band(model)
    return f"{low:.0f}-{high:.0f} tok/s"


def stars(rating: int) -> str:
    bounded = max(1, min(5, rating))
    return "*" * bounded + "-" * (5 - bounded)


def count_words_as_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))
