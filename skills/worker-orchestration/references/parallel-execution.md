# Parallel execution — watcher design, WIP slot rules, mock harness

Design notes for the PARALLEL variant of the Linear-driven watcher (remote workers). The delta vs the serial watcher (`references/linear-driven-watcher.md` in the `linear-orchestration` skill).

## Why parallel now

Local worker = 1 GPU → 1 worker at a time (physical bottleneck → serial watcher). Remote worker = API → no physical contention; the bottlenecks become orchestration capacity, API cost/tokens, and the human review queue. `MAX_PARALLEL` is the knob for all three.

## Watcher output contract (multi-event)

One line per event, in suggested processing order (REVIEW/CONFLICT/MERGE first — they free/resolve slots; REFINE/DISPATCH/PROMOTE after):

```
CONFLICT task=X pr=N url=U
REVIEW task=X pr=N comment_id=I login=L url=U
MERGE current=X pr=N url=U dependents=A,B
REFINE task=X title=T
STUCK task=X branch=B
DISPATCH task=X title=T
PROMOTE task=X title=T
```

The cron agent processes ALL lines of the tick, in order. `IDLE` only when there are no lines. The script is still deterministic (no LLM): `parallel-watch.py`, block `CONFIGURAR POR PROJETO` at the top.

## WIP slot rules (2 bugs found by mock testing)

- `running` = started tasks whose PR is open (with or without pending review) OR whose worker is still running. STUCK tasks (no PR, no live process) also stay in `running` — the slot stays occupied until the cron re-dispatches (prevents WIP overflow during recovery).
- Merged-PR tasks are NOT in `running` (worker stopped; the MERGE handler closes the issue in the same tick → slot frees).
- `capacity = MAX_PARALLEL - len(running)`. Fill order: REFINE (1/tick) → DISPATCH (Todo by priority, none last) → PROMOTE (unblocked backlog), each decrementing capacity.

**Bug 1 (WIP overflow on REVIEW):** a REVIEW-pending task was `continue`d without adding to `running` → the script dispatched 2 new workers while the review re-dispatch was pending → WIP 3 > MAX_PARALLEL 2. Fix: `running.append(ident)` on the REVIEW branch too — the worker is re-dispatched in the SAME worktree, so the slot stays occupied.

**Bug 2 (redundant PROMOTE):** after emitting `MERGE ... dependents=PRJ-2`, the same tick also emitted `PROMOTE task=PRJ-2` (it was unblocked backlog) → the agent would `status set --to Todo` twice. Fix: collect dependents from all MERGE lines emitted this tick and exclude them from the PROMOTE candidate list (filter before slicing by capacity).

## CONFLICT event

`gh pr view <n> --repo <R> --json mergeable` == "CONFLICTING" (ignore "UNKNOWN" — GitHub still computing). Auto-resolution (2026-08): emit `CONFLICT` ONLY for PRs not yet marked in the conflict state file; the cron re-dispatches the worker in the SAME worktree with a resolution body (rebase onto base, integrate preserving others' work, run tests, push) and marks the PR (`--mark-conflict` — only AFTER a successful re-dispatch; on wrapper/terminal failure do NOT mark, next tick re-emits). A marked PR still CONFLICTING is not re-emitted (worker failed → human resolves in the GitHub UI or comments → REVIEW). REVIEW takes PRIORITY over CONFLICT in the watcher loop: a pending human comment re-dispatches even on a CONFLICTING PR (bug 2026-08: the CONFLICT `continue` skipped the review check, so a "resolve the conflicts" comment was never processed). Parallel merge conflicts are expected: briefs should restrict touched files ("git status mostra apenas X") and same-file tasks should be serialized with `blocked-by`.

## STUCK event (worker died silently)

A started task with NO PR (open or merged) and NO live worker process = the session died without concluding (low `max_turns` on research/exploration tasks, or runtime error at session close — "scope close failed" in the worker profile log). Real incident 2026-08: 2 remote workers died this way; the old watcher saw them as "running" forever (tasks stuck In Progress for 45+ min, no PR).

- Detection (deterministic, in the watcher): count live worker processes via `Get-CimInstance Win32_Process` filtering `Name -eq <HERMES_PROC>` AND `CommandLine -match <WORKER_PROFILE>` — filtering by **Name** avoids self-match (the check command itself contains the profile string; filtering by CommandLine alone catches the cron's own powershell/bash). Distribute the live count among started tasks without PR (oldest first); the excess emits `STUCK task=X branch=B`. On check failure assume alive (never kill anything by mistake).
- Handler (cron agent): NEVER re-dispatch the original body blindly — inspect the worktree git state and adapt: (a) local commits with no remote branch (`## branch` without `...origin/`) → continuation body "work is committed; push + open PR"; (b) uncommitted changes → continuation body "continue from where you stopped (partial changes in worktree), finalize, validate, commit, push, PR"; (c) clean worktree → original body from the issue description. Reuse the SAME worktree (no new worktree, no Linear state change). Check the worker log first: if max_turns was the cause, raise it BEFORE re-dispatching or the death repeats.
- Emergency: when the work is committed and validated, the orchestrator may push + open the PR manually to free the slot (the human review gate stays the same).

## Mock test harness (reusable)

Deterministic watcher = easy to unit-test without Linear/GitHub/Orca. Load the module and monkeypatch its CLI functions:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("pw", r"...\assets\parallel-watch.py")
pw = importlib.util.module_from_spec(spec); spec.loader.exec_module(pw)
pw.linear_issues = lambda: list(ISSUES.values())          # ISSUES: dict ident -> issue dict
pw.linear_issue_relations = lambda i: RELATIONS.get(i, [])
pw.gh_pr = lambda branch, state: ...                      # PRS[branch] -> ("open"/"merged", num)
pw.gh_mergeable = lambda pr: PRS_MERGEABLE.get(pr, "MERGEABLE")
pw.gh_review_comments = lambda pr: COMMENTS               # [{id, login, created, body}]
pw.gh_last_commit_date = lambda b: pw.parse_dt(LAST_COMMIT)
pw.orca_worktrees = lambda: []
pw.REVIEW_STATE = <tmp path>; pw.MAX_PARALLEL = 2; pw.BRANCH_PREFIX = ""
# redirect stdout, call pw.main(), assert the exact list of printed lines
```

The 12 cases that caught the bugs: fan-out 2×DISPATCH; WIP=1 → only 1 DISPATCH; REVIEW occupies slot (REVIEW + 1 DISPATCH); CONFLICT; MERGE without redundant PROMOTE; fan-in partial → IDLE; fan-in complete → PROMOTE; IDLE; MERGE frees slot + 2 DISPATCH; double MERGE; saturation → IDLE; fan-in via MERGE dependents.

## Post-edit verification checklist (repo de manuais)

1. `python -m py_compile assets/parallel-watch.py` — templates must stay compilable (a placeholder outside a string is a SyntaxError; keep a default value + placeholder in a comment: `MAX_PARALLEL = 2  # <MAX_PARALLEL>`).
2. Run the 12 mock cases (script under Temp with `hermes-verify-` prefix; delete after; also delete any `__pycache__` the compile creates).
3. `bash -n` on wrapper `.sh` files; YAML-parse worker-config.yaml.
4. manual.md section 7.1 code block byte-identical to `assets/parallel-watch.py` (regex `### 7.1.*?```python\n(.*?)```` + diff) — the manual embeds the full watcher.
5. Token scan for machine-specific strings before any public push.
