---
name: orca-worker-orchestration
description: >-
  Delegate to a local Hermes worker via Linear + PRs + Orca.
---

# Orca Worker Orchestration (Linear board + PR gate + Orca runtime)

The "remote model orchestrates a local model" setup: the main profile (remote, strong model) authors tasks and delegates; the <WORKER_PROFILE> profile (small local model) executes one task per session; each task ends in a GitHub PR; the next task starts only after the previous PR merges and the base repo is updated. Linear is the board; Orca is the IDE/runtime the user watches.

## Architecture (roles)

| Piece | Who | Responsibility |
|---|---|---|
| Orchestrator | main profile (remote model) | author tasks, create Linear issues, create worktrees, dispatch worker, verify PR, update Linear after merge, delegate next |
| Worker | <WORKER_PROFILE> profile (local model on llama.cpp/LM Studio) | execute ONE task body, commit, push, open PR, STOP |
| Board | Linear team (e.g. <REPO>, key <TASK_PREFIX>) | task specs + serial order (blocked-by relations) |
| Delivery gate | GitHub PR against base branch (main) | human reviews/merges; merge unblocks next task |
| Runtime | Orca app + CLI | worktrees/terminals the user watches in the IDE |

Division of labor (user-approved): the worker NEVER marks tasks complete, never merges, never touches issue/ticket states. The orchestrator tracks merges and updates the board.

## Task body authoring — brief style (user preference, non-negotiable)

The user explicitly rejected decision-free/mechanical bodies (exact code blocks, exact commands, grep checks with expected output). Task descriptions must read like briefs for a real developer:

- **Contexto** — project one-liner + what already exists (previous merged tasks) + where this task fits
- **Objetivo** — the WHAT in product terms; never the HOW
- **Diretrizes do projeto** — only team conventions (single index.html, pt-BR, PR for main, brand identity)
- **Critérios de aceite** — verifiable outcomes, no implementation dictation
- **Entrega** — process: commit, push branch, PR for main, STOP (details live in the worker SOUL)

What may stay prescriptive (client/business data, not code): section ids later tasks must target (e.g. `hero`, `produtos`, `contato`), product data tables ("dados fornecidos — não altere os valores": names/prices/image URLs), brand identity. Colors, fonts, layout, markup, copy: worker's judgment. Bodies tell the worker to read the existing code first (like a real dev reads the team's code).

## Worker SOUL.md contract (platform-agnostic)

The <WORKER_PROFILE> SOUL.md contains NO kanban references (user directive; kanban is decommissioned for this worker). Contract:
- Task body arrives in the session prompt; fallback when the prompt says "task: <id>": `orca linear issue --current --full --json`
- Body is the single source of truth; WHAT from body, HOW is worker judgment; read existing code before editing
- Branch = the worktree's current branch; PR base = from the body (never hardcode `master`/`main` in the SOUL)
- Stage only files the work touched (`git add <files>`), never `git add -A`; `rm -f pr_body.md` first
- PR description via pr_body.md (Summary / Changes / How to verify / Notes); Notes = where the worker documents its decisions
- Max 3 attempts per problem, then report ERROR and stop; after the PR: stop, never merge, never change states
- Worker config.yaml toolset restricted to terminal/file/web/code_execution (small context window, less noise)

## Dispatch

- Invisible (no IDE): from the worktree cwd, `hermes -p <profile> chat -q "$(cat <bodyfile>)" -Q` (background). `-Q` suppresses live output — omit it when a human watches.
- Orca-visible (user watches in the IDE): see `references/orca-linear-and-worktree-quirks.md` — raw `git worktree add` → `orca repo add --path` → `orca worktree set --linear-issue` → `orca terminal create --command` running a wrapper bash script.
- Smoke-test the profile first with a tiny query (confirms local model + profile + approvals env).

## Orca CLI on Windows

- `<ORCA_INSTALL>\Orca.exe` is the Electron GUI (single-instance; running it with args just focuses the app). The CLI is `<ORCA_INSTALL>\resources\bin\orca.cmd` (+ `orca.exe` next to it) — not on PATH.
- `orca skills get orca-linear` / `orca skills get orca-cli` print the version-matched full guide. NEVER guess subcommands; the installed skill stubs deliberately omit them.
- Prefer `orca.exe` over `orca.cmd` when any argument contains double quotes (the cmd batch wrapper mangles nested quotes). For complex `terminal create --command`, put the real command in a `.sh` file and pass `bash.exe <script>`.
- Session runs inside Orca (TERM_PROGRAM=Orca, ORCA_AGENT_HOOK_* set) — use the full CLI path in the git-bash terminal tool.

## Pitfalls

- `orca linear save-issue` often returns `ok:false` / `linear_write_unconfirmed` even when the write APPLIED — always verify by reading the issue back (title/label/priority survive).
- Repos registered in Orca BEFORE `git init` stay kind `folder`; `orca worktree create` on them yields a virtual workspace on the SAME path (id suffix `::workspace:<uuid>`, empty branch) — not a checkout. No repo remove/upgrade command exists; workaround: raw `git worktree add` + `orca repo add --path <worktree>` (detected as kind git → card in IDE).
- Killing a dispatched worker: process tree is `hermes.exe chat` → python → python. Match via Win32_Process CommandLine (`chat -q` / task name); single-quote the whole powershell -Command or MSYS bash expands `$_`. Never kill `gateway run`, `dashboard`, or the `--tui --yolo` process (user session).
- `git worktree remove --force` fails Permission denied while a dead process still holds cwd → `rm -rf` the dir + `git worktree prune`.
- Restarting an aborted task: `gh pr close <n> --delete-branch` (closes PR + deletes remote head branch), delete local branch, recreate worktree.
- Base repo hygiene: `.gitignore` MUST contain `.worktrees/` (commit it) or `git status` stays permanently dirty and automated pulls break.

## Reference

- `references/orca-linear-and-worktree-quirks.md` — exact command recipes, folder-kind diagnosis, quoting layers, worker process-tree kill, and the <REPO> <TASK_PREFIX>-1..6 chain setup.
