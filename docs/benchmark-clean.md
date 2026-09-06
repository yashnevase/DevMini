# Benchmark And Clean

## `minidev benchmark`

Runs a fixed short prompt against the configured Ollama model:

```bash
minidev benchmark
minidev benchmark --model qwen2.5-coder:14b
```

MiniDev measures generated tokens per second from Ollama's response metadata when
available, then compares the result with simple reference bands for 7B, 14B, and
32B model sizes.

## `minidev clean`

Scans MiniDev context for stale file references:

- `.devmini/index.json` entries whose `path` no longer exists.
- `memory.md` lines that explicitly mention stale paths.

It lists stale references first, then asks before modifying files:

```bash
minidev clean
minidev clean --yes
```

The cleanup is intentionally conservative. It prunes stale index entries and
removes only memory lines that directly reference stale paths.
