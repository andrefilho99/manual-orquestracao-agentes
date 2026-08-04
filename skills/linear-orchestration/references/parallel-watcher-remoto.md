# Parallel watcher (remote workers) — design, bugs caught, test harness

Session 2026-08-03: created `manual-orquestracao-agentes-remotos` as the remote/parallel counterpart of the local manual. This file is the delta vs the serial v2 watcher (`references/linear-driven-watcher.md`).

## Why parallel now
Local worker = 1 GPU → 1 worker at a time (physical bottleneck → serial watcher). Remote worker = API → no physical contention; the bottlenecks become orchestration capacity, API cost/tokens, and the human review queue. `MAX_PARALLEL` is the knob for all three.

## Watcher output contract (multi-event)
One line per event, in suggested processing order (REVIEW/CONFLICT/MERGE first — they free/resolve slots; REFINE/DISPATCH/PROMOTE after):

```
CONFLICT task=X pr=N url=U
REVIEW task=X pr=N comment_id=I login=L url=U
MERGE current=X pr=N url=U dependents=A,B
REFINE task=X title=T
DISPATCH task=X title=T
PROMOTE task=X title=T
```

The cron agent processes ALL lines of the tick, in order. `IDLE` only when there are no lines. The script is still deterministic (no LLM): `parallel-watch.py`, block `CONFIGURAR POR PROJETO` at the top.

## WIP slot rules (the 2 bugs found by mock testing)
- `running` = started tasks whose PR is open (with or without pending review) OR whose worker is still running.
- Merged-PR tasks are NOT in `running` (worker stopped; the MERGE handler closes the issue in the same tick → slot frees).
- `capacity = MAX_PARALLEL - len(running)`. Fill order: REFINE (1/tick) → DISPATCH (Todo by priority, none last) → PROMOTE (unblocked backlog), each decrementing capacity.

**Bug 1 (WIP overflow on REVIEW):** a REVIEW-pending task was `continue`d without adding to `running` → the script dispatched 2 new workers while the review re-dispatch was pending → WIP 3 > MAX_PARALLEL 2. Fix: `running.append(ident)` on the REVIEW branch too — the worker is re-dispatched in the SAME worktree, so the slot stays occupied.

**Bug 2 (redundant PROMOTE):** after emitting `MERGE ... dependents=PRJ-2`, the same tick also emitted `PROMOTE task=PRJ-2` (it was unblocked backlog) → the agent would `status set --to Todo` twice. Fix: collect dependents from all MERGE lines emitted this tick and exclude them from the PROMOTE candidate list (filter before slicing by capacity).

## CONFLICT event
`gh pr view <n> --repo <R> --json mergeable` == "CONFLICTING" (ignore "UNKNOWN" — GitHub still computing). Emit `CONFLICT`, keep the slot occupied, no re-dispatch, no Linear state change. Human resolves via the GitHub UI ("Resolve conflicts"/"Update branch") OR comments on the PR → next tick fires REVIEW → worker does `git pull --rebase origin <BASE>` + resolves. Parallel merge conflicts are expected: briefs should restrict touched files ("git status mostra apenas X") and same-file tasks should be serialized with `blocked-by`.

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
1. `python -m py_compile assets/parallel-watch.py` — templates must stay compilable (see placeholder pitfall in SKILL.md).
2. Run the 12 mock cases (script under `<TEMP_DIR>` with `hermes-verify-` prefix; delete after; also delete any `__pycache__` the compile creates).
3. `bash -n` on wrapper `.sh` files; YAML-parse worker-config.yaml.
4. manual.md section 7.1 code block byte-identical to `assets/parallel-watch.py` (regex `### 7.1.*?```python\n(.*?)``` + diff) — the manual embeds the full watcher.
5. Token scan for machine-specific strings (nome de usuário da máquina, dono/repo, ids do fluxo, nomes de modelo, perfil do worker, prefixo de task, caminhos de dados do usuário) before any public push; "local"/"GPU" hits are expected in the comparison table and irmão-manual references.
