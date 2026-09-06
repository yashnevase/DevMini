# Doctor, Status, And Uninstall

## `minidev doctor`

Checks:

- Ollama installed and responding.
- Selected model is present in `ollama list`.
- Selected model returns structured Ollama tool calls.
- OpenCode is installed.
- OpenCode config includes MiniDev permissions and the local Ollama model.
- Editor integration is detectable through config, `code`, `zed`, or the
  `MINIDEV_EDITOR_CONNECTED=1` environment signal.
- Current directory is inside a git repository.

Use `--fix` to attempt repair of missing or broken fixable items.

`Model tool calls [ TEXT TOOL JSON ]` means the model is reachable and can answer,
but it returns tool-call JSON as ordinary text. That is not enough for reliable
OpenCode file edits from chat.

## `minidev status`

Shows a compact live view:

- Server running.
- Model loaded.
- Editor connected/detected.
- LAN status.

LAN is shown as on when config contains `{"lan": {"enabled": true}}` or
`OLLAMA_HOST` points at a non-localhost address.

After `minidev share`, LAN status shows `HOST` while the recorded OpenCode
server process is alive. After `minidev connect`, LAN status shows `REMOTE`.

## `minidev uninstall`

Reads `~/.minidev/manifest.json` and removes only MiniDev-owned entries:

- Files recorded inside `~/.minidev`.
- Packages recorded with action `install`.
- Ollama models recorded with action `pull`.

Entries recorded as already present or repaired are left alone.
