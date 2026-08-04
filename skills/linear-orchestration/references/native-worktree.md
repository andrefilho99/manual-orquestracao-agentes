# Native worktree + visible dispatch — proven recipe (<TASK_PREFIX>-7 test, 2026-08-02)

Environment: Hermes TUI inside Orca 1.4.164 on Windows 10. Repo `<REPO>`
is registered in Orca as **`kind: git`** (checked via `orca repo list --json`), which
makes the NATIVE worktree path work — no folder-kind workaround needed.

Full end-to-end run, all commands as executed (output shapes verbatim):

## 1. Preconditions
```bash
ORCA="<ORCA_CLI>"
"$ORCA" status --json                    # ok:true, runtime ready
"$ORCA" repo list --json                 # repo kind: git → native path OK
"$ORCA" linear team list --workspace all --json   # team <TEAM_KEY>, wsId <WS_ID>
# base repo: git fetch origin && git status → main clean & up-to-date; .gitignore has .worktrees/
# smoke-test worker: HERMES_YOLO_MODE=1 hermes.exe -p <WORKER_PROFILE> chat -q "Responda apenas com: OK" -Q
```

## 2. Create the Linear issue (brief-style body via --body-file)
```bash
"$ORCA" linear create \
  --title "<TASK_PREFIX>-7: <título>" \
  --body-file "<TEMP_DIR>/<proj>-bodies/<proj>-7.md" \
  --team <TEAM_KEY> --workspace <WS_ID> \
  --label Improvement --priority low --json
# → "identifier": "<TASK_PREFIX>-7", "url": "https://linear.app/<WS_NAME>/issue/<TASK_PREFIX>-7/..."
# Standalone test issue: no blocked-by relation needed.
```

## 3. Native worktree create (kind: git → REAL checkout)
```bash
"$ORCA" worktree create --repo id:<REPO_ID> \
  --name <proj>-7-test --no-parent --json
```
Key fields in `result.worktree`:
- `id` = `<REPO_ID>::<WORKTREES_ROOT>/<REPO>/<proj>-7-test` (full `<repoId>::<path>` — copy whole value)
- `path` = `<WORKTREES_ROOT>/<REPO>/<proj>-7-test`
- `branch` = `refs/heads/<SEU_USUARIO>/<proj>-7-test` (Orca names branch `<gitUsername>/<taskName>`)
- `baseRef` = `refs/remotes/origin/main`, `head` = main's current commit

MSYS quirk: `git -C /c/Users/...` fails ("cannot change to ... No such file or
directory") — use `cd <WORKTREES_ROOT>/<REPO>/<proj>-7-test && git ...`
instead.

## 4. Link the Linear issue
```bash
WT="id:<REPO_ID>::<WORKTREES_ROOT>/<REPO>/<proj>-7-test"
"$ORCA" worktree set --worktree "$WT" --linear-issue <TASK_PREFIX>-7 --json
# → "linkedLinearIssue": "<TASK_PREFIX>-7"
```

## 5. Wrapper script (<TEMP_DIR>, OUTSIDE the worktree so it can't be committed)
`<TEMP_DIR>/<proj>-7-run.sh`:
```bash
#!/usr/bin/env bash
cd "<WORKTREES_ROOT>/<REPO>/<proj>-7-test" || exit 1
export HERMES_YOLO_MODE=1
exec "<HERMES_BIN>" \
  -p <WORKER_PROFILE> chat -q "$(cat "<TEMP_DIR>/<proj>-bodies/<proj>-7.md>")"
```
(no `-Q` — the user watches live output in the Orca terminal)

## 6. Visible terminal
```bash
"$ORCA" terminal create --worktree "$WT" --title "<TASK_PREFIX>-7 worker (<WORKER_PROFILE>)" \
  --command '"<BASH_BIN>" "<TEMP_DIR>/<proj>-7-run.sh"' --json
# → handle term_<id>, "surface": "visible"
```

## 7. Monitor (do NOT use `terminal wait --for exit`)
`terminal wait --for exit` never fires: the bash that `exec`'d hermes stays alive at
the prompt after hermes exits (`status` stays `running`). Poll instead:
```bash
"$ORCA" terminal read --terminal <handle> --limit 100 --json   # grep tail for PR URL / "Session: <id>"
```
Worker run: 1m32s, 21 messages; tail ends with the shell prompt `C:\...>`. Grep the
terminal tail for `https://github.com/.../pull/N` to catch the PR.

## 8. Verify the PR
```bash
"<GH_CLI>" pr view <N> --repo <SEU_USUARIO>/<REPO> \
  --json number,title,state,headRefName,baseRefName,url,additions,deletions,files
"<GH_CLI>" pr diff <N> --repo <SEU_USUARIO>/<REPO>
```
Result: PR #<N>, `+4`/`-0`, only README.md, state OPEN. Worker stopped after PR (per
SOUL contract) — no merge, no Linear state change.

## Notes
- Standalone test issue <TASK_PREFIX>-7 was created WITHOUT a blocked-by relation; the serial
  chain (<TASK_PREFIX>-1..6) remains untouched and all still Backlog as of this date.
- The old folder-kind workaround (raw `git worktree add` + `orca repo add --path`) is
  now only needed for repos still registered as `kind: folder` — see
  `worker-dispatch-and-orca-visibility.md`.
