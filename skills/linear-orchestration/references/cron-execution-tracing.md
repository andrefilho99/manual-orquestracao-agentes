# Tracing what a cron execution actually did (<TASK_PREFIX> merge-watcher diagnostics)

Use when the user asks "a execução do cron fez X?" / "por que Y só aconteceu depois?" /
"isso vai rodar no próximo tick?" — reconstruct the real timeline from local artifacts
instead of guessing. Proven 2026-08-02 on the "<TASK_PREFIX>-6 promoted but dev only 5 min later?"
question (answer: NOT true — PROMOTE enchains DISPATCH in the same tick).

## Local artifacts (all under `<HERMES_HOME>`)

1. **Full cron prompt** — `cron/jobs.json` (field `jobs[0].prompt`). The cronjob
   `list` preview truncates it; read the JSON. This tells you the EXACT handlers the
   agent must follow (e.g. PROMOTE step 2 = re-run script → DISPATCH same tick).
2. **Per-tick execution records** — `cron/output/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md`.
   One file per tick: contains the script's stdout (IDLE/DISPATCH/MERGE/PROMOTE),
   the full prompt, and the agent's final response (resumo / [SILENT]). `ls -lt` to
   see the timeline at a glance; grep for `PROMOTE|<TASK_PREFIX>-6|DISPATCH` across files.
3. **Agent session trace with timestamps** — `logs/agent.log`. Each cron run gets a
   session id `cron_<job_id>_<YYYYMMDD_HHMMSS>` where HHMMSS = the run START time
   (e.g. `cron_<job_id>_20260802_221858` started 22:18:58). grep that id for:
   - `API call #N: ... latency=NNNs` — model latency per call (<ORCHESTRATOR_MODEL>: 80–120s each;
     this is the "delay" users perceive as a skipped tick)
   - `tool terminal completed / write_file completed` — what the agent actually executed
   - `Turn ended` — when the run finished
4. **Scheduler state** — `cron/jobs.json` `last_run_at` / `next_run_at` / `last_status`,
   and `cron/ticker_heartbeat` / `cron/ticker_last_success` (epoch seconds) if the
   ticker seems stalled.

## Cross-check the live state (never trust only the logs)

- Linear: `orca.exe linear list --filter all --team <TEAM_KEY> --workspace <wsId> --json`
  → per-issue `state.name` + `state.type`; and `orca.exe linear issue <TASK_PREFIX>-N --json`
  → `result.issue.state` + `updatedAt` (ISO, UTC — convert to local -03:00).
- Worktrees: `orca.exe worktree ps --json` → paths + `linkedLinearIssue`.
- Terminals: `orca.exe terminal list --json` (match by `worktreePath`!) and
  `orca.exe terminal read --terminal <handle> --limit N --json` → `status` + `tail`.
- PR merge times: `gh.exe pr list --repo <repo> --state all --json number,state,mergedAt,headRefName`
  → `mergedAt` is UTC (e.g. `2026-08-03T01:16:05Z` = 22:16:05 local). This pins when
  the Linear bot auto-marked the previous issue Done (~2s after merge).

## Worked example — "<TASK_PREFIX>-6 foi promovido para Todo, dev só 5 min depois?"

Timeline reconstructed from artifacts alone:

| Local time | Event | Evidence |
|---|---|---|
| 22:13:52 | Tick: script stdout `IDLE` → agent `[SILENT]` | `output/2026-08-02_22-13-52.md` |
| 22:16:05 | PR #<N> (<TASK_PREFIX>-5) merged by user; Linear bot marks <TASK_PREFIX>-5 Done ~2s later | `gh pr list` mergedAt 01:16:05Z |
| 22:18:58 | Tick starts; script sees <TASK_PREFIX>-6 unblocked in Backlog → `PROMOTE task=<TASK_PREFIX>-6` | session id `..._20260802_221858` |
| 22:21:03 | Agent step 1: `status set <TASK_PREFIX>-6 --to Todo` (this is what the user SAW) | issue `updatedAt` 01:21:03Z + API call #1/#2 latency |
| 22:22–22:25 | Agent step 2 (ENCADEAMENTO): re-runs script → `DISPATCH task=<TASK_PREFIX>-6` → executes DISPATCH steps (body, worktree, link, In Progress, wrapper, terminal) | API calls #2–#4 + tool lines; then `worktree ps` shows <proj>-6 linked, terminal running |
| 22:27+ | Tick still finishing hygiene (closing old <proj>-5 worktree) | agent.log tool lines |

Conclusions the artifacts support:
- PROMOTE + DISPATCH happened in the SAME tick by design — no second tick needed.
- The Todo state is the intermediate step (history Backlog→Todo→In Progress on purpose).
- The perceived 4-min gap between "Todo" and "In Progress" = <ORCHESTRATOR_MODEL> API latency
  (~80–120s × several calls), not a cron cadence gap.
- Note: ticks that overlap a still-running agent are SKIPPED (`already running —
  skipping` in agent.log) — so `next_run_at` can slip past the nominal 5-min schedule.

## Quick answer pattern

User: "promoveu mas dev só no próximo tick?" → answer is almost always: same tick,
look at the run's own response file (`cron/output/`) which states "Encadeamento →
DISPATCH ... executado no mesmo tick", and confirm live state (issue In Progress +
worktree/terminal exist) — then the user's observed "delay" is just model latency.
