# MiniDev — Project Bible

*Living document. Update this as decisions get made or reversed. Last updated: build day 1.*

---

## 1. What this is, in one line

A CLI (`minidev`) that installs, configures, and maintains Ollama + OpenCode + editor
integration + a hand-tuned context/memory layer — so a local model behaves like a
focused engineer on your specific codebase. Offline, private, free, open source.

## 2. What we are NOT building (and why)

- **Not our own agent server / tool executor.** OpenCode already does file search,
  shell execution, git-aware editing, plan/build modes. Rebuilding this = months, not
  days, and duplicates a mature project. MiniDev is a layer *around* OpenCode, not a
  replacement for it.
- **Not a cloud service.** Everything runs on the user's machine or their LAN.
- **Not a general chatbot.** Scoped to coding tasks on a real repo.

## 3. Architecture (v1, correct version — supersedes the agent-server diagram)

```
User → Editor (VS Code / Zed) → OpenCode (agent, tool exec, plan/build modes)
                                      ↑
                          reads: AGENTS.md, memory.md, .devmini/*
                                      ↓
                              Ollama (local model)
```

MiniDev's job: install this chain, generate/maintain the files OpenCode reads,
manage the lifecycle (doctor/status/update/uninstall). MiniDev does not sit in the
runtime request path.

## 4. Decisions log

| Decision | Reasoning | Status |
|---|---|---|
| Name: MiniDev | Clear, matches existing spec, not too "toy" | Locked |
| Stack: Python + Typer + Rich | Matches spec's PyInstaller packaging plan, Rich gives free styled terminal output | Locked |
| No custom agent server in v1 | OpenCode already solves this; avoid months of duplicate work | Locked |
| `study` command is user-triggered, not automatic | User's call — avoids startup lag on large repos | Locked |
| Hard deny-list for scanning (`.env*`, `*secret*`, `*.key`, credentials) | Non-negotiable safety line, not configurable, lives in code not config | Locked |
| Custom/optimized agent-brain work | Deferred to v3, after real usage reveals actual (not guessed) gaps | Deferred |
| Windows/Linux support | Mac-first, then port once Mac version is stable | Deferred |
| Website | Build after CLI works end to end | Deferred |

## 5. Build phases

**Phase 0 (done):** Manual proof-of-concept — Ollama + OpenCode + editor wired by hand,
AGENTS.md + memory.md hand-written, tested on a real repo, LAN access confirmed.

**Phase 1 (current — Codex prompts 1-5):**
1. Scaffold + `minidev install`
2. `minidev doctor` / `status` / `uninstall`
3. `minidev init` / `learn`
4. `minidev study` (git-history learning, on-demand)
5. Editor integration + safety config (writes OpenCode's own permission config,
   does not implement a separate permission layer)

**Phase 2:** `minidev share`/`connect` (LAN), `minidev benchmark`, `minidev clean`,
`minidev explain`. Polish based on real usage from Phase 1.

**Phase 3:** Custom agent-brain improvements — only for gaps proven real by actual use
(e.g. retrieval precision, specific edit-format issues). Possibly: architect/editor
two-model split, vector DB for semantic search, if OpenCode's native retrieval proves
insufficient.

**Phase 4:** Windows/Linux ports, public website, open-source polish (README,
CONTRIBUTING, templates folder for other stacks).

## 6. Open questions (resolve before the relevant phase starts)

- Does OpenCode support custom slash-commands/skills natively? If yes, register
  `study` as one so it's callable from inside chat, not just the CLI. *(check during
  Phase 1 build)*
- Does OpenCode expose a subagent/multi-model config that gives us an architect/editor
  split natively, or do we need to build routing ourselves? *(check before Phase 3)*

## 7. Safety rules (non-negotiable, enforced in code not config)

- Never read/index: `.env*`, `*secret*`, `*.key`, `.git/credentials`, anything matching
  a hard-coded deny-list — regardless of gitignore status.
- Git checkpoint before any write.
- Auto-approve: read, search, test-run. Ask before: commit, package install, delete,
  destructive commands.

## 8. Branding reference

Palette: navy `#0A1128` background, blue `#1E90FF` primary, yellow `#FFD166` accent,
white `#F5F5F5` text. Pixel-robot-claw logo. Terminal output styled to match this
palette via Rich (checkmarks, boxed sections) so the running tool visually matches
marketing material.

## 9. Codex prompt log

*(Paste each prompt here after running it, plus a one-line note on what actually
happened vs. what was expected — this becomes your real build history.)*

- [ ] Prompt 1 — Scaffold + install — model: gpt-5.5, effort: high
- [ ] Prompt 2 — doctor/status/uninstall — model: gpt-5.5, effort: medium
- [ ] Prompt 3 — init/learn — model: gpt-5.5, effort: medium
- [ ] Prompt 4 — study — model: gpt-5.5, effort: medium
- [ ] Prompt 5 — editor integration + safety config — model: gpt-5.5, effort: medium
