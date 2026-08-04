# Orca Linear CLI — operations (Windows / Hermes)

Working notes for driving Linear through Orca's CLI from Hermes on Windows (verified 2026-08).

## Resolving the CLI on Windows

- `Orca.exe` (the app, at `<ORCA_INSTALL>\Orca.exe`) is the **Electron GUI** — single-instance; running it with args just focuses the existing window. It is NOT the CLI.
- The real CLI: `<ORCA_INSTALL>\resources\bin\orca.exe` (a `.cmd` wrapper sits beside it — prefer the `.exe` directly when any argument contains double quotes, the batch wrapper mangles nested quotes).
- Sessions launched inside Orca carry `TERM_PROGRAM=Orca` and `ORCA_*` env vars (ORCA_WORKSPACE_ID, ORCA_APP_VERSION, ORCA_AGENT_HOOK_*) — a good signal you are inside Orca.
- The `orca-linear` / `orca-cli` skill files are discovery stubs; the full version-matched guide comes from the binary: `<ORCA_CLI> skills get orca-linear`.
- Preconditions: `<ORCA_CLI> status --json` (app must be running → `ok: true`).

## Discovery (stable ids first)

```
<ORCA_CLI> linear team list --workspace all --json
<ORCA_CLI> linear team states --team <TEAM_KEY> --workspace <WS_ID> --json
<ORCA_CLI> linear team labels --team <TEAM_KEY> --workspace <WS_ID> --json
<ORCA_CLI> linear team members --team <TEAM_KEY> --workspace <WS_ID> --json
```

Pass `--workspace <WS_ID>` explicitly on every call — do not rely on auto-detect.

## Creating and updating issues

- Create: `<ORCA_CLI> linear create --title "..." --body-file <path> --team <TEAM_KEY> --workspace <WS_ID> --label <exact-name> --priority medium --json`. Identifiers are assigned sequentially (`<TASK_PREFIX>-1`, `<TASK_PREFIX>-2`, …) in creation order.
- Use `--body-file` for long/multiline bodies — avoids MSYS bash quoting hell (backticks, quotes, `$`, code fences). Local Windows paths work fine (only SSH-backed remote CLIs need stdin).
- Update: `<ORCA_CLI> linear save-issue <id> --body-file <path> --json` (create-or-update shape; omitting a field keeps it).

## QUIRK: `linear_write_unconfirmed`

`save-issue` (and sometimes `create`) returns `"ok": false` with `error.code: linear_write_unconfirmed` ("Linear may have applied the issue save, but Orca could not confirm it") even when the write DID apply — a confirmation race, not a failure.

Pattern: for Linear writes, do NOT trust the `ok` flag. Read back the issue (`<ORCA_CLI> linear issue <id> --json`) and grep for a marker that must be present (section header, `--body-file`, etc.). Confirmed multiple times in one session (2026-08): every save applied despite `ok: false`.

## Encoding a chain (blocked-by)

```text
<ORCA_CLI> linear relation add <TASK_PREFIX>-N --related <TASK_PREFIX>-(N-1) --type blocked-by --workspace <WS_ID> --json
```

Output reports the relation as `"type": "blocks"` on the "from" side — expected. The chain reads "<TASK_PREFIX>-N blocked by <TASK_PREFIX>-(N-1)". Fan-in (a task depending on several): add one blocked-by relation per blocker — the watcher promotes the task only when ALL blockers are Done/Canceled.

## Verification habit

- After any write, read back: `<ORCA_CLI> linear issue <id> --json` → grep markers (`"identifier"`, section headers) before telling the user a change landed.
- After bulk edits, loop over all ids and confirm each marker.
- `list-issues --team <TEAM_KEY> --workspace <WS_ID> --json` — check for existing issues first to avoid duplicates.
