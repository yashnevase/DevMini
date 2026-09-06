# Explain

## `minidev explain`

Explains a file path or symbol using the existing MiniDev index:

```bash
minidev learn
minidev explain src/app.py
minidev explain SomeSymbol
minidev explain SomeSymbol --model qwen2.5-coder:14b
```

The command is read-only. It does not write files or create git checkpoints.

MiniDev uses `.devmini/index.json` to locate the target, then reads source files
to gather:

- The enclosing function/class-like block.
- Direct call sites that reference the target symbol.
- Direct importers whose import snippets mention the target file or symbol.

That context is sent to the configured Ollama model for a concise plain-language
explanation.
