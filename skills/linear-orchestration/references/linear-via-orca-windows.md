# Worked example: <REPO> Linear chain (2026-08)

Environment: Hermes TUI inside Orca 1.4.164 on Windows 10. CLI resolved at
`<ORCA_CLI>`.

## CLI resolution sequence (what actually worked)
1. `which orca` → not found; `where orca` → not found; `env | grep -i orca` → session runs inside Orca (TERM_PROGRAM=Orca, ORCA_APP_VERSION, ORCA_WORKSPACE_ID), NO `ORCA_CLI_COMMAND`.
2. `<ORCA_INSTALL>\Orca.exe` exists but is the 215 MB Electron app — running it with args prints `[single-instance] Another Orca instance...` and foregrounds the window.
3. `ls <ORCA_INSTALL>\resources\` → `bin/` with `orca.cmd` (665 B) + `orca.exe` (18.3 K).
4. `orca.cmd status --json` → `{"ok": true, "result": {"app": {"running": true, ...}}}`.
5. `orca.cmd skills get orca-linear` → full version-matched guide (create/list/relation/status commands).

## Discovery output shapes
- `linear team list --workspace all --json` → `result.teams[0] = {id, name, key, url, workspace: {id, name}}`.
- Team `<REPO>` (key `<TEAM_KEY>`), workspace `<WS_NAME>`.
- States: Backlog(backlog), Todo(unstarted), In Progress(started), **In Review(started, position 1002)**, Done(completed), Canceled, Duplicate.
- Labels: Feature, Improvement, Bug. Members: 1.
- `linear list-issues --team <TEAM_KEY> --workspace <wsId> --limit 20 --json` → empty (clean slate).

## Create + chain commands used
- Bodies written to `<TEMP_DIR>\<proj>-bodies\<proj>-N.md` (one per issue; `--body-file` round-trips markdown + code fences exactly).
- Create (sequential → identifiers <TASK_PREFIX>-1..<TASK_PREFIX>-6 in order):
  `orca linear create --title "<T>" --body-file <f> --team <TEAM_KEY> --workspace <wsId> --label Feature --priority medium --json`
- Serial relations (add ON the later issue, referencing the earlier):
  `orca linear relation add <TASK_PREFIX>-N --related <TASK_PREFIX>-(N-1) --type blocked-by --workspace <wsId> --json` → returns `"type": "blocks"`.
- Compact chained output: pipe through `grep -E '"identifier"|"url"|"ok"'`.
- Verify: `linear list-issues --team <TEAM_KEY> --workspace <wsId> --json` + `linear issue <TASK_PREFIX>-2 --relations --json`.

## Chain created (6 issues, all Backlog + Feature, medium, unassigned)
<TASK_PREFIX>-1 scaffold (index.html + README) → <TASK_PREFIX>-2 design system (tokens/fonts/CSS base) → <TASK_PREFIX>-3 hero → <TASK_PREFIX>-4 product grid (6 cards, exact prices/images) → <TASK_PREFIX>-5 contact + footer → <TASK_PREFIX>-6 mobile menu JS.
Branch per issue hardcoded in the body (`<proj>-N`); PR base always `main`; every body ends with "PARE — não faça merge, reporte a URL do PR".

## Body-writing conventions applied (per issue)
- Repeated "Regras travadas" block: single-file index.html, CSS/JS inline, pt-BR copy, palette hex values, Google Fonts URL.
- Exact verification greps with expected counts, e.g. `grep -c "class=\"card\"" index.html` → `6`.
- Image URLs verified live first: `curl -s -o /dev/null -w "%{http_code}" -I "https://images.unsplash.com/<id>?w=1200&q=80"` — ~40% of guessed IDs returned 404; 11 verified live for this project.

## Readiness items for the delegation round (not yet done)
- Add `.worktrees/` to the repo's `.gitignore` before first dispatch (keeps base repo `git status` clean so automated pulls work — pitfall learned on hotel-homepage kanban).
- Orchestrator creates worktrees from updated `main`, delegates <TASK_PREFIX>-1 to <WORKER_PROFILE>, watches the PR merge, then updates base and delegates the next.
