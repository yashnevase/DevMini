# Share And Connect

## `minidev share`

Starts a LAN-only MiniDev host:

- Detects a non-loopback LAN IP address.
- Starts Ollama with `OLLAMA_HOST=<lan-ip>:11434` when a LAN Ollama endpoint is
  not already reachable.
- Starts `opencode serve --hostname <lan-ip> --port <port>`.
- Sets `OPENCODE_SERVER_USERNAME=opencode` and a generated
  `OPENCODE_SERVER_PASSWORD` token for the OpenCode server.
- Writes `~/.minidev/share.json` and updates `~/.minidev/config.json`.

OpenCode is bound to the detected LAN IP, not `0.0.0.0`.

```bash
minidev share
minidev share --port 4096
minidev share --stop
```

`minidev share --stop` terminates only processes MiniDev started and removes the
active token from `~/.minidev/share.json`.

## `minidev connect`

Run this on a second device:

```bash
minidev connect 192.168.1.20:4096 TOKEN_FROM_HOST
```

This writes:

- `~/.minidev/remote.json`
- `~/.minidev/bin/minidev-opencode-remote`
- remote connection details into `~/.minidev/config.json`

Then start terminal chat on the second device with:

```bash
~/.minidev/bin/minidev-opencode-remote
```

The launcher runs `opencode attach` against the authenticated LAN URL.
