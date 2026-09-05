# MiniDev

MiniDev is a small Python CLI that installs and configures the local coding stack:
Ollama for local models and OpenCode for agent/tool execution.

MiniDev does not run its own agent server or tool executor. OpenCode handles the
agent runtime; MiniDev only installs, configures, and writes files.

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
minidev init
minidev learn
minidev study
minidev uninstall --dry-run
```

The installer writes:

- `~/.minidev/config.json`
- `~/.minidev/manifest.json`

The manifest records files, packages, and Ollama models touched by MiniDev so a
future uninstall command can remove only what MiniDev created.

`minidev init` writes project-local context into `.devmini/`, `AGENTS.md`, and
`memory.md`. `minidev learn` builds `.devmini/index.json` with a lightweight
symbol/import index using ripgrep and Tree-sitter; OpenCode handles actual
retrieval during coding tasks.

`minidev study` walks new git commits since `.devmini/state.json`, summarizes
frequently changed files and recurring fix patterns, appends that summary to
`.devmini/decisions.md` and `memory.md`, and then records the latest studied
commit.
