# Study

`minidev study` learns from git history without entering the runtime path.

It:

- Reads `.devmini/state.json` for the last studied commit.
- Walks commits since that hash, or all commits on first run.
- Counts frequently changed files as hotspots.
- Classifies recurring patterns from commit messages and allowed diffs.
- Appends a summary to `.devmini/decisions.md` and `memory.md`.
- Updates `.devmini/state.json` with the latest studied commit.

The command never reads or indexes denied paths, regardless of gitignore status:

- `.env*`
- paths containing `secret`
- paths containing `credential`
- paths containing `token`
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- `.git/credentials`

MiniDev only writes this summary and state. OpenCode handles retrieval and coding
behavior during actual tasks.
