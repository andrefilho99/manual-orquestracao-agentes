# Worker post-PR verification ritual (<WORKER_PROFILE> / <LOCAL_MODEL>)

Observed 2026-08 on the <REPO> chain (<TASK_PREFIX>-1..3). Class-level pattern: small local
models do not honor "PARE após o PR" as a hard stop — they run an ad-hoc verification ritual
after the PR is open, wasting 40s–1min+ of wall time per task.

## Evidence (tool calls AFTER the PR was created)

| Task | Last real step | Tool calls after PR | Extra cost |
|---|---|---|---|
| <TASK_PREFIX>-1 | commit → push → PR #<N> | created `hermes-verify-<proj>1.py` in `<TEMP_DIR>`, ran 19 checks, deleted it | ~3 calls, ~40s |
| <TASK_PREFIX>-2 | commit → push → PR #<N> | `execute_code` HTML/CSS validation + re-check | ~2 calls |
| <TASK_PREFIX>-3 | commit → push → PR #<N> | `execute_code` ×3 validations + created/ran/deleted `hermes-verify-hero.py` | ~5 calls, ~1min |

The ritual NEVER touches the repo (no commits, no extra files — temp scripts go in
`<TEMP_DIR>` and are deleted; working-tree state stays clean), so the PR
itself is unaffected. The cost is: (1) wall-clock dead time per task, (2) the wrapper terminal
stays `running` longer, which delays the merge-handler's cleanup of the previous worktree
(cleanup matches the terminal by worktreePath and closes it — it just happens later), (3) the
IDE shows the task as "working" when the deliverable is already on GitHub.

## Root cause

Task-completion ritual of small models: opening the PR without "confirming it's all correct"
feels like unfinished work to the model, so it self-verifies even though the SOUL and the body
both say stop. Prompt rules are suggestions to a small local model mid-ritual.

## Fixes (recommended order)

1. **Invert body order (BEST)**: instruct the worker to verify EVERYTHING *before* commit/push —
   `verifique e valide todo o resultado ANTES do commit; após abrir o PR, não execute mais nada`.
   The PR becomes literally the last action; the ritual is channeled into productive pre-commit
   checking instead of post-PR dead time. The user's bodies already ask for "verificação" in
   critérios — make it explicit that verification happens pre-commit.
2. **Negative rule in SOUL.md/body**: "Após o PR aberto: ZERO operações — não verifique, não
   releia, não rode nada. A verificação é feita pelo orquestrador no review do PR."
3. **Mechanical kill (emergency-only, risky)**: orchestrator watches GitHub for the PR URL and
   kills the worker session; can cut mid-push — keep as last resort, not default.

## Technique: inspecting what a dispatched worker actually did

`session_search` FTS does NOT reliably find worker sessions (they run headless via
`hermes -p <WORKER_PROFILE> chat -q "..."`, per-profile DB, discovery ignores the profile filter).
Read the worker's state DB directly:

```python
import sqlite3, json
db = r'<HERMES_HOME>\profiles\<WORKER_PROFILE>\state.db'
con = sqlite3.connect(db); cur = con.cursor()
# 1) list recent worker sessions (cli source = dispatched)
rows = cur.execute('''
SELECT s.id, s.source, s.model,
       (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS msgs
FROM sessions s ORDER BY (SELECT MAX(m.timestamp) FROM messages m WHERE m.session_id=s.id) DESC LIMIT 10
''').fetchall()
# 2) per session, dump the tool-call sequence (content + tool_calls JSON on assistant rows)
#    -> find the LAST PR-creating call, then list every call after it = the ritual cost
```

Map sessions to tasks by timestamp: each <TASK_PREFIX>-N dispatch produces one `cli` session with the
<LOCAL_MODEL> model; the PR URL in the session tail tells you which PR/task it was.

## Where this bites

- Delaying merge-handler cleanup (old worktree lingers in the Orca UI).
- User perception: "task finished but the worker keeps doing stuff" — the user raised this
  explicitly and asked for it to be eliminated.
