# MiniDev

MiniDev is a small Python CLI that installs and configures the local coding stack:
Ollama for local models and OpenCode for agent/tool execution.

MiniDev does not run its own agent server or tool executor. OpenCode handles the
agent runtime; MiniDev installs, configures, writes project memory, enforces
local-only model routing, and exposes the user-facing `minidev chat` and
`minidev acp` entrypoints.

## Install for development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

The pip upgrade matters on older macOS Python installations: their bundled pip
may not support editable installs from `pyproject.toml`.

The `minidev` command is available while this virtual environment is active.
To use it from another project or a new terminal window, activate this same
environment by its absolute path first:

```bash
source /Users/yashnevse/Desktop/devmini/.venv/bin/activate
cd /path/to/your/project
minidev init
```

Alternatively, call `/Users/yashnevse/Desktop/devmini/.venv/bin/minidev`
directly without activating the environment.

## Use

```bash
minidev install
minidev install --model qwen2.5-coder:14b
minidev install --dry-run
minidev doctor
minidev doctor --fix
minidev status
minidev chat
minidev share
minidev connect 192.168.1.20:4096 TOKEN
minidev benchmark
minidev init
minidev learn
minidev study
minidev clean
minidev explain src/app.py
minidev explain SomeSymbol
minidev uninstall --dry-run
```

## Zed Chat

After `minidev install`, MiniDev writes a Zed external agent named `MiniDev`.
Open Zed, open the command palette with `Cmd+Shift+P`, run
`agent: new terminal thread`, then start `minidev chat`. A fresh chat session
should show `minidev` and `MiniDev Local <model>` in its status line.

Inside the OpenCode terminal UI:

- `Ctrl+P` opens OpenCode commands.
- `Tab` switches agents/modes.
- `Esc` interrupts a running response.
- Close a thread from Zed's left thread list, or close the editor tab.

Restart the OpenCode thread after changing MiniDev/OpenCode config; an already
open thread can keep the old model and agent settings.

The installer writes:

- `~/.minidev/config.json`
- `~/.minidev/manifest.json`
- `~/.config/opencode/opencode.json`
- `~/.config/zed/settings.json` when Zed is installed

The manifest records files, packages, and Ollama models touched by MiniDev so a
future uninstall command can remove only what MiniDev created.

`minidev init` writes project-local context into `.devmini/`, `AGENTS.md`, and
`memory.md`. It also writes `.opencode/opencode.json`, a `minidev-study` command,
and a `minidev-study` skill so OpenCode can load MiniDev's project memory through
its native config. `minidev learn` builds `.devmini/index.json` with a lightweight
symbol/import index using ripgrep and Tree-sitter.

`minidev doctor` checks whether the configured local model returns structured
tool calls through Ollama. A model can still be useful for chat, benchmark, and
`minidev explain` while failing this check, but OpenCode needs structured tool
calls to reliably read/edit files from the chat loop. When this check fails,
MiniDev marks the model as chat-only in OpenCode to avoid fake JSON tool calls.
On small Apple Silicon machines, MiniDev creates a local Ollama runtime alias
like `minidev-qwen3-4b-instruct-16k` with a 16k context window, so OpenCode has
room for its tools and project instructions without using a hosted model.

MiniDev chat is local-only. `minidev chat` always supplies the configured
`ollama/<model>` to OpenCode and rejects hosted model IDs such as
`opencode/big-pickle`.

`minidev study` walks new git commits since `.devmini/state.json`, summarizes
frequently changed files and recurring fix patterns, appends that summary to
`.devmini/decisions.md` and `memory.md`, and then records the latest studied
commit.

`minidev share` starts Ollama and `opencode serve` on the host's detected LAN IP
with a random OpenCode server password. It never binds OpenCode to `0.0.0.0`.
Use `minidev share --stop` to stop the MiniDev-started processes and revoke the
stored token. On a second device, run `minidev connect <ip:port> <token>` to save
the remote endpoint and create a local `~/.minidev/bin/minidev-opencode-remote`
launcher that runs `opencode attach`.

`minidev benchmark` runs a fixed short prompt through the configured Ollama model,
reports tokens per second with a simple five-star rating against model-size
reference bands, and runs a tiny fixed coding task with pass/fail accuracy.
`minidev clean` finds stale file references in
`.devmini/index.json` and `memory.md`, lists them, and removes them after
confirmation.

`minidev explain <path-or-symbol>` uses `.devmini/index.json` from `learn` to
locate a file or symbol, gathers the enclosing code block plus direct
callers/importers, and asks the configured Ollama model for a plain-language
read-only explanation.
