# Orca + Linear + worktree recipes (<REPO> session 2026-08)

## Linear chain setup (orca linear)

- Discovery: `orca linear team list --workspace all --json`; then `team states|labels|members --team <KEY> --workspace <wsId> --json`.
- Create with body file: `orca linear create --title "<t>" --body-file <path> --team <KEY> --workspace <wsId> --label Feature --priority medium --json` → returns `identifier` (<TASK_PREFIX>-N) + `url`. First created issue in an empty team gets <TASK_PREFIX>-1.
- Serial chain: after creating N issues, `orca linear relation add <TASK_PREFIX>-N --related <TASK_PREFIX>-(N-1) --type blocked-by --workspace <wsId> --json` (creates a `blocks` relation pair).
- UPDATE QUIRK: `orca linear save-issue <TASK_PREFIX>-N --body-file <f> --workspace <ws> --json` reports `"ok": false` / `linear_write_unconfirmed` ("may have applied, could not confirm") even when the write DID apply. Always verify by reading back: `orca linear issue <TASK_PREFIX>-N --workspace <ws> --json | grep -c '<marker>'`. Title/label/priority survive updates (confirmed).
- Workspace/team used by this user: workspace `<WORKSPACE>` (<uuid>), team `<REPO>` key <TASK_PREFIX>. Only member: <USUARIO>. Leave issues unassigned (user's kanban rule carries over).
- Linear states (<TASK_PREFIX> team): Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate.

## Orca CLI resolution (Windows)

- GUI: `<ORCA_INSTALL>\Orca.exe` — Electron, single-instance; running it with args just focuses the app ("another instance already running").
- CLI shim: `<ORCA_INSTALL>\resources\bin\orca.cmd` (+ `orca.exe`, 18KB). Not on PATH.
- Full guides: `orca skills get orca-linear`, `orca skills get orca-cli` (the installed skill files are deliberate discovery stubs).
- Use `orca.exe` DIRECTLY (not `.cmd`) when any argument contains double quotes — the cmd batch wrapper mangles nested quotes.

## Worktree visibility in the Orca IDE

Problem: a raw `git worktree add` checkout is invisible to Orca → the user cannot watch the worker in the IDE ("não vejo ele trabalhando na ideia do Orca").

Root cause: the repo was added to Orca as kind `folder` (added before `git init`). On folder-kind repos, `orca worktree create --repo id:<repoId> --name <task>` produces a VIRTUAL WORKSPACE on the same path: id `<repoId>::<path>::workspace:<uuid>`, `branch: ""`, `isMainWorktree: false` — no checkout, no branch. `orca repo` has no remove/upgrade command; `orca repo add --path <base>` on the existing path is idempotent (returns the existing folder record).

Working recipe (proven):
```bash
git worktree add .worktrees/<proj>-1 -b <proj>-1            # from base repo on main
orca repo add --path "<BASE_REPO_PATH>\.worktrees\<proj>-1"   # -> kind git, displayName <proj>-1
orca worktree set --worktree "name:<proj>-1" --linear-issue <TASK_PREFIX>-1 --json   # link the Linear issue
# wrapper script to dodge quoting (Temp, outside the worktree so it can't be committed):
#   <proj>-1-run.sh:
#     cd "<WORKTREES_ROOT>/<proj>-1" || exit 1
#     export HERMES_YOLO_MODE=1
#     exec "<HERMES_HOME>/hermes-agent/venv/Scripts/hermes.exe" \
#       -p <WORKER_PROFILE> chat -q "$(cat "<TEMP_DIR>/<proj>-bodies/<proj>-1.md")"
orca terminal create --worktree "name:<proj>-1" \
  --command '"<HERMES_HOME>\git\bin\bash.exe" "<TEMP_DIR>\<proj>-1-run.sh"' --json
orca terminal read --terminal <handle> --json          # live output; status: running
```
- bash.exe used: `<HERMES_HOME>\git\bin\bash.exe` (Hermes-bundled git bash; no `C:\Program Files\Git` on this machine).
- `orca terminal create` result: `handle` (term_...), `worktreeId`, `surface: visible` → the terminal shows in the app.
- The registered card is repo-level (kind git) rather than a child of the folder context — a known consequence of the folder-kind limitation. Note it to the user; offer full-native `orca worktree create` only if they accept re-registering the base repo as git.

## Worker dispatch (invisible mode)

```bash
cd <worktree> && hermes -p <WORKER_PROFILE> chat -q "$(cat <TEMP_DIR>/<proj>-bodies/<proj>-1.md)" -Q
```
- `-p <profile>` selects the profile; the generated alias (`<WORKER_PROFILE>.bat` in `~/.local/bin`) is just `hermes -p <WORKER_PROFILE>`.
- `$(cat file)` command substitution: content is not re-parsed, so backticks/quotes/brackets survive (same rule as kanban `--body "$(cat bodyfile.md)"`).
- Smoke-test first: `hermes -p <WORKER_PROFILE> chat -q "Responda apenas com: OK" -Q` — confirms profile + local model + env.
- HERMES_YOLO_MODE=1 present in the session env (inherited by children) avoids approval hangs on git push / gh pr create in non-interactive runs.
- hermes full path: `<HERMES_HOME>\hermes-agent\venv\Scripts\hermes.exe`.

## Killing the worker + cleanup (restart path)

- Process tree of a dispatched worker: `hermes.exe chat` (launcher) → `python.exe` (hermes venv) → `python.exe` (uv runtime).
- Find: `powershell -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "chat -q" -and $_.Name -match "python|hermes" } | Select-Object ProcessId,Name | Format-Table -AutoSize'` — the whole -Command MUST be single-quoted; MSYS bash expands `$_` (turns `$_.CommandLine` into a path) otherwise.
- Kill: `powershell -NoProfile -Command 'Stop-Process -Id <pids> -Force'`. NEVER kill `gateway run` (pid with `-m hermes_cli.main gateway run`), `dashboard`, or the `--tui "--yolo"` process — that is the user's live session.
- Worktree removal: `git worktree remove --force` may fail `Permission denied` while a killed process still holds cwd → `rm -rf .worktrees/<task>` + `git worktree prune` + `git branch -D <branch>`.
- Aborted PR: `gh pr close <n> --delete-branch --repo <owner>/<repo> --comment "..."` closes the PR AND deletes the remote head branch. Stale `refs/remotes/origin/<branch>` clears on next `git fetch --prune` (harmless).
- Base repo hygiene: `.gitignore` with `.worktrees/` must be committed to main BEFORE dispatching worktree tasks, or `git status` stays dirty and automated pulls break. Verify with `git check-ignore -v .worktrees/<name>`.

## MSYS/native-tool path quirk (recurring)

Native Windows exes (python.exe) mangle MSYS paths: `python /c/Users/...` becomes `C:\c\Users\...`. Always pass `C:/Users/...` style paths to native exes; MSYS tools (rm, cat) accept `/c/...` fine.

## Task-chain state (<REPO>, 2026-08)

- Linear team <TASK_PREFIX> has 6 issues (<TASK_PREFIX>-1..<TASK_PREFIX>-6), all Backlog + Feature label, chained blocked-by <TASK_PREFIX>-2←<TASK_PREFIX>-1 … <TASK_PREFIX>-6←<TASK_PREFIX>-5. Bodies are brief-style (Contexto/Objetivo/Diretrizes/Critérios de aceite/Entrega).
- Repo: github.com/<SEU_USUARIO>/<REPO> (private, default branch main). Base repo must be on main, pulled, clean before each delegation.
- Delivery: worker pushes `<proj>-N` branch and opens PR vs main; user reviews/merges; orchestrator then updates the base repo, marks the Linear issue Done, delegates <TASK_PREFIX>-(N+1).
