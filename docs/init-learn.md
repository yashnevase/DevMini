# Init And Learn

## Using MiniDev in another project

MiniDev is installed into the development virtual environment created in the
MiniDev repository. Activate that environment before running project commands:

```bash
source /Users/yashnevse/Desktop/devmini/.venv/bin/activate
cd /path/to/your/project
minidev init
minidev learn
minidev study
```

You can also run the absolute executable path without activation:
`/Users/yashnevse/Desktop/devmini/.venv/bin/minidev init`.

## `minidev init`

Detects basic project facts and writes project context:

- `.devmini/project.md`
- `.devmini/environment.md`
- `.devmini/conventions.md`
- `.devmini/decisions.md`
- `.devmini/bugs.md`
- `AGENTS.md`
- `memory.md`
- `.opencode/opencode.json`
- `.opencode/commands/minidev-study.md`
- `.opencode/skills/minidev-study/SKILL.md`

Detected facts include package manager, likely languages, entry points, and common
JavaScript frameworks. Existing files are skipped unless `--force` is passed.

The `.opencode` files tell OpenCode to load MiniDev's project context through its
native `instructions` config, and add a `minidev-study` command/skill for asking
what MiniDev has learned about the project.

## `minidev learn`

Builds `.devmini/index.json` with:

- Source files discovered through `rg --files`.
- A hard-coded deny-list for secrets, keys, credentials, `.env*`, and common build
  folders.
- Tree-sitter parsed symbol and import snippets where a grammar is available.
- File hashes and language summary.

MiniDev only builds this index file. OpenCode handles retrieval and runtime coding
behavior.
