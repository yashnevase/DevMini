# Doctor, Status, And Uninstall

## `minidev doctor`

Checks:

- Ollama installed and responding.
- Selected model is present in `ollama list`.
- OpenCode is installed.
- MiniDev config exists at `~/.minidev/config.json`.
- Editor integration is detectable through config, `code`, `zed`, or the
  `MINIDEV_EDITOR_CONNECTED=1` environment signal.
- Current directory is inside a git repository.

Use `--fix` to attempt repair of missing or broken fixable items.

## `minidev status`

Shows a compact live view:

- Server running.
- Model loaded.
- Editor connected/detected.
- LAN status.

LAN is shown as on when config contains `{"lan": {"enabled": true}}` or
`OLLAMA_HOST` points at a non-localhost address.

## `minidev uninstall`

Reads `~/.minidev/manifest.json` and removes only MiniDev-owned entries:

- Files recorded inside `~/.minidev`.
- Packages recorded with action `install`.
- Ollama models recorded with action `pull`.

Entries recorded as already present or repaired are left alone.
