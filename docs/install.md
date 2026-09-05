# `minidev install`

`minidev install` sets up the local coding stack:

- Detects OS and RAM.
- Checks existing `ollama` and `opencode` binaries with `--version`.
- Repairs broken installs only when `--repair`, `--yes`, or an interactive prompt
  allows it.
- Selects an Ollama model from RAM unless `--model` is supplied.
- Installs missing tools using Homebrew or npm.
- Pulls the selected Ollama model.
- Writes OpenCode permission policy into `~/.config/opencode/opencode.json`.
- Installs the VS Code ACP extension when the `code` CLI is available, or writes
  a Zed ACP agent config when `zed` is available.
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

| RAM | Model |
| --- | --- |
| Less than 16 GB | `qwen2.5-coder:7b` |
| 16-32 GB | `qwen2.5-coder:14b` |
| More than 32 GB | `qwen2.5-coder:32b` |

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
2. Zed: writes `~/.config/zed/agents/minidev.json` pointing at `opencode acp`

If neither CLI is present, MiniDev prints manual setup instructions and exits
cleanly.

## OpenCode permissions

MiniDev writes OpenCode's native `permission` config. It does not implement its
own permission layer.

- Read/search commands are allowed.
- Test commands are allowed.
- Commits, installs, deletes, pushes, tags, and file edits ask first.
