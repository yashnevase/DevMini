# `minidev install`

`minidev install` sets up the local coding stack:

- Detects OS and RAM.
- Checks existing `ollama` and `opencode` binaries with `--version`.
- Repairs broken installs only when `--repair`, `--yes`, or an interactive prompt
  allows it.
- Selects an Ollama model from RAM unless `--model` is supplied.
- Installs missing tools using Homebrew or npm.
- Pulls the selected Ollama model.
- Checks whether the model returns structured tool calls through Ollama.
- Writes OpenCode permission policy, Ollama provider config, and local default
  model into `~/.config/opencode/opencode.json`.
- Installs the VS Code ACP extension when the `code` CLI is available, or writes
  a Zed ACP agent server into `~/.config/zed/settings.json` when Zed is installed.
- Writes `~/.minidev/config.json` and `~/.minidev/manifest.json`.

## Development install

From the project directory, use a fresh virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Older macOS Python distributions often ship pip versions that cannot install
editable `pyproject.toml` projects until pip is upgraded.

## Model selection

| Device | Preferred local model | Fallbacks |
| --- | --- | --- |
| Less than 16 GB RAM | `qwen3:4b-instruct` | `qwen2.5-coder:7b` |
| 16-32 GB Apple Silicon | `qwen3:4b-instruct` | `qwen2.5-coder:14b`, `qwen2.5-coder:7b` |
| 16-32 GB non-Apple-Silicon | `qwen2.5-coder:14b` | `qwen2.5-coder:7b` |
| More than 32 GB RAM | `qwen3:30b-a3b` | `qwen2.5-coder:32b`, `qwen2.5-coder:14b` |

MiniDev records the candidate list in `~/.minidev/config.json`.
For OpenCode, MiniDev creates a local Ollama alias named
`minidev-<base-model>-16k` with `num_ctx 16384`; this keeps the chat/tool loop
inside a usable local context window without duplicating the downloaded model
weights.

## Current installer defaults

Ollama is installed with:

```bash
brew install ollama
```

OpenCode is installed with Homebrew when available:

```bash
brew install anomalyco/tap/opencode
```

If Homebrew is unavailable and npm is available, OpenCode falls back to:

```bash
npm install -g opencode-ai
```

MiniDev deliberately avoids creating a custom agent server or tool executor.

## Editor integration

MiniDev tries editors in this order:

1. VS Code: `code --install-extension formulahendry.acp-client`
2. Zed: writes an `agent_servers.MiniDev` entry into
   `~/.config/zed/settings.json` pointing at `minidev acp`

If neither editor is present, MiniDev prints manual setup instructions and exits
cleanly. On macOS, MiniDev detects `/Applications/Zed.app` even when the `zed`
CLI is not on `PATH`.

## OpenCode local model

MiniDev configures OpenCode's native provider format:

- Provider: `ollama`
- Base URL: `http://localhost:11434/v1`
- Default model: `ollama/minidev-<base-model>-16k`
- Default agent: `minidev`

If `minidev doctor` reports `Model tool calls [ TEXT TOOL JSON ]`, the model is
answering locally but is not returning structured tool calls. OpenCode may chat,
but file reading/editing through the agent loop will not be reliable until a
tool-capable local model is selected with `minidev install --model ...`.

`minidev chat` is local-only. It always passes the configured Ollama model and
refuses hosted model IDs such as `opencode/big-pickle`.

## OpenCode permissions

MiniDev writes OpenCode's native `permission` config. It does not implement its
own permission layer.

- Read/search commands are allowed.
- Test commands are allowed.
- File edits are allowed.
- Commits, installs, deletes, pushes, and tags ask first.
