# Worker dispatch + Orca IDE visibility (<REPO> session 2026-08)

## Dispatch (invisible mode — no IDE)

```bash
cd <worktree> && hermes -p <WORKER_PROFILE> chat -q "$(cat <TEMP_DIR>/<proj>-bodies/<proj>-1.md)" -Q
```
- `-p <profile>` selects the profile; the generated alias (`<WORKER_PROFILE>.bat` in `~/.local/bin`) is just `hermes -p <WORKER_PROFILE>`.
- `$(cat file)` command substitution: content is not re-parsed, so backticks/quotes/brackets survive.
- Smoke-test first: `hermes -p <WORKER_PROFILE> chat -q "Responda apenas com: OK" -Q` — confirms profile + local model + env.
- HERMES_YOLO_MODE=1 in the session env (inherited by children) avoids approval hangs on `git push` / `gh pr create` in non-interactive runs.
- hermes full path: `<HERMES_BIN>`.
- The worker runs in the worktree cwd; the task body is the prompt (platform-agnostic SOUL contract — see SKILL.md).

## Worktree visibility in the Orca IDE

Problem: a raw `git worktree add` checkout is invisible to Orca → the user cannot watch the worker in the IDE ("não vejo ele trabalhando na ideia do Orca").

Root cause: repo added to Orca as kind `folder` (added before `git init`). On folder-kind repos, `orca worktree create --repo id:<repoId> --name <task>` produces a VIRTUAL WORKSPACE on the same path: id `<repoId>::<path>::workspace:<uuid>`, `branch: ""`, `isMainWorktree: false` — no checkout, no branch. `orca repo` has no remove/upgrade command; `orca repo add --path <base>` on the existing path is idempotent (returns the existing folder record).

Working recipe (proven):
```bash
git worktree add .worktrees/<proj>-1 -b <proj>-1                          # from base repo on main
orca repo add --path "<BASE_REPO_PATH>\.worktrees\<proj>-1"               # -> kind git, displayName <proj>-1
orca worktree set --worktree "name:<proj>-1" --linear-issue <TASK_PREFIX>-1 --json   # link the Linear issue
# wrapper script to dodge quoting (put it in <TEMP_DIR>, OUTSIDE the worktree so it can't be committed):
#   <proj>-1-run.sh:
#     cd "<BASE_REPO_PATH>/.worktrees/<proj>-1" || exit 1
#     export HERMES_YOLO_MODE=1
#     exec "<HERMES_BIN>" \
#       -p <WORKER_PROFILE> chat -q "$(cat "<TEMP_DIR>/<proj>-bodies/<proj>-1.md>")"
orca terminal create --worktree "name:<proj>-1" \
  --command '"<BASH_BIN>" "<TEMP_DIR>/<proj>-1-run.sh"' --json
orca terminal read --terminal <handle> --json                        # live output; status: running
```
- bash.exe used: `<BASH_BIN>` (Hermes-bundled git bash; no `C:\Program Files\Git` on this machine).
- `orca terminal create` result: `handle` (term_...), `worktreeId`, `surface: visible` → the terminal shows in the app.
- The registered card is repo-level (kind git) rather than a child of the folder context — a known consequence of the folder-kind limitation. Tell the user; offer fully-native `orca worktree create` only if they accept re-registering the base repo as git.

## Killing the worker + cleanup (restart path)

- Process tree of a dispatched worker: `hermes.exe chat` (launcher) → `python.exe` (hermes venv) → `python.exe` (uv runtime).
- Find:
  `powershell -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "chat -q" -and $_.Name -match "python|hermes" } | Select-Object ProcessId,Name | Format-Table -AutoSize'`
  The whole -Command MUST be single-quoted; MSYS bash expands `$_` (turns `$_.CommandLine` into a path) otherwise.
- Kill: `powershell -NoProfile -Command 'Stop-Process -Id <pids> -Force'`. NEVER kill `gateway run` (`-m hermes_cli.main gateway run`), `dashboard`, or the `--tui "--yolo"` process — that is the user's live session.
- Worktree removal: `git worktree remove --force` may fail `Permission denied` while a killed process still holds cwd → `rm -rf .worktrees/<task>` + `git worktree prune` + `git branch -D <branch>`.
- Aborted PR: `gh pr close <n> --delete-branch --repo <owner>/<repo> --comment "..."` closes the PR AND deletes the remote head branch. Stale `refs/remotes/origin/<branch>` clears on next `git fetch --prune` (harmless).
- Base repo hygiene: `.gitignore` with `.worktrees/` must be committed to main BEFORE dispatching, or `git status` stays dirty and automated pulls break. Verify with `git check-ignore -v .worktrees/<name>` + `git status --porcelain`.

## MSYS/native-tool path quirk (recurring)

Native Windows exes (python.exe) mangle MSYS paths: `python /c/Users/...` becomes `C:\c\Users\...`. Always pass `C:/Users/...` style paths to native exes; MSYS tools (rm, cat) accept `/c/...` fine.
