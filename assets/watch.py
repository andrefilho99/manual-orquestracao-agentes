#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Watcher do pipeline <PROJ> — Linear-driven, multi-evento.

UNIFICADO: cobre as duas modalidades do manual — serial (worker LOCAL,
MAX_PARALLEL = 1) e paralela (workers REMOTOS, MAX_PARALLEL = N). Com
MAX_PARALLEL = 1 o comportamento reproduz o watcher serial (uma decisao por
tick na pratica); com N > 1, um tick emite UMA LINHA POR EVENTO (fan-out).

O Linear eh a fonte da verdade (estados + descriptions). Eventos:

  IDLE                        - nada a fazer
  CONFLICT task=X pr=N url=U  - PR aberto da task X esta em CONFLITO de merge
                                (mergeable=CONFLICTING) e ainda nao foi
                                re-despachado — o cron re-despacha o worker no
                                MESMO worktree para resolver SOZINHO e marca o
                                PR (--mark-conflict); PR ja marcado nao re-emite
                                (aguarda humano: resolve na UI ou comenta)
  REVIEW task=X pr=N comment_id=I url=U
                              - PR aberto da task X tem comentario de review
                                humano mais novo que o ultimo push (nao-bot,
                                nao-processado)
  MERGE current=X pr=N url=U dependents=A,B
                              - PR da task X foi mergeado (dependents = issues
                                em Backlog que X desbloqueia)
  REFINE task=X title=T       - issue em "To Refine" com descricao BREVE
  STUCK task=X branch=B       - task In Progress SEM PR e SEM processo de worker
                                vivo (sessao morreu sem concluir — limite de
                                turns ou erro de runtime) — o cron deve
                                re-despachar no MESMO worktree com body de
                                continuacao (ver manual, secao 8)
  DISPATCH task=X title=T     - task pronta em Todo (unstarted) — respeitando
                                a capacidade livre (MAX_PARALLEL)
  PROMOTE task=X title=T      - task em Backlog DESBLOQUEADA (todos os
                                blockedBy dela Done/Canceled) — respeitando a
                                capacidade livre

Concorrencia: MAX_PARALLEL limita o WIP TOTAL (tasks em In Progress, incluindo
PRs abertos aguardando review/merge). Capacidade livre = MAX_PARALLEL - tasks
em execucao. Tasks com PR ja mergeado NAO ocupam slot (o worker parou; o
handler MERGE fecha a issue no mesmo tick). Tasks com review pendente SEGUEM
ocupando slot (o worker e re-disparado no mesmo worktree — o WIP nao pode
estourar).

Fila Todo/Backlog: prioridade (urgent primeiro, none por ultimo), depois
updatedAt. Dependencias: fan-in suportado (task so promove quando TODOS os
blockedBy estao Done/Canceled).

Review state: <PROJ>-review-state.json guarda comment ids ja processados (o
agente marca com `--mark <id>` apos re-disparar o worker). Evita loop quando
o worker nao consegue resolver (comentario continua mais novo que o ultimo
commit).

Saida: uma linha por evento, na ordem de processamento sugerida (REVIEW/
CONFLICT/MERGE primeiro — liberam/ajudam a resolver; REFINE/DISPATCH/PROMOTE
depois). O agente do cron processa TODAS as linhas do tick.
"""

# ===================== CONFIGURAR POR PROJETO =====================
ORCA = "<ORCA_CLI>"
GH = "<GH_CLI>"
WS = "<WS_ID>"                              # Linear workspace id (secao 4)
TEAM = "<TEAM_KEY>"                         # Linear team key (secao 4)
REPO = "<REPO>"                             # GitHub owner/repo (secao 4)
BRANCH_PREFIX = "<BRANCH_PREFIX>"           # ex.: "usuario/"
MAX_PARALLEL = 1                            # <MAX_PARALLEL> — WIP total (execucao + PRs abertos); 1 = serial (worker local), N = paralelo (workers remotos)
REVIEW_STATE = "<SCRIPTS_DIR>/<PROJ>-review-state.json"   # Windows: usar forward slashes
CONFLICT_STATE = "<SCRIPTS_DIR>/<PROJ>-conflict-state.json"  # PRs cujo conflito ja foi re-despachado (anti-loop)
HERMES_PROC = "hermes.exe"                  # basename do executavel do Hermes (Name no Win32_Process)
WORKER_PROFILE = "<WORKER_PROFILE>"         # perfil do worker (filtro de processo)
# ==================================================================

import json
import subprocess
import sys
from datetime import datetime, timezone


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = p.stdout.strip()
        if not out:
            return None
        try:
            return json.loads(out)
        except Exception:
            return out
    except Exception as e:  # noqa: BLE001 - watcher nao pode quebrar
        print(f"WATCH_ERROR run({' '.join(cmd)}): {e}", file=sys.stderr)
        return None


def linear_issues():
    d = run([ORCA, "linear", "list", "--filter", "all",
             "--team", TEAM, "--workspace", WS, "--json"])
    if isinstance(d, dict):
        return d.get("result", {}).get("issues", [])
    return []


def linear_issue_relations(ident):
    d = run([ORCA, "linear", "issue", ident, "--relations",
             "--workspace", WS, "--json"])
    if isinstance(d, dict):
        return d.get("result", {}).get("relations", [])
    return []


def gh_pr(branch, state):
    d = run([GH, "pr", "list", "--repo", REPO, "--head", branch,
             "--state", state, "--json", "number,url,state"])
    if isinstance(d, list) and d:
        return d[0].get("number"), d[0].get("url")
    return None, None


def gh_mergeable(pr):
    """mergeable: MERGEABLE | CONFLICTING | UNKNOWN (GitHub ainda calculando)."""
    d = run([GH, "pr", "view", str(pr), "--repo", REPO,
             "--json", "mergeable,mergeStateStatus"])
    if isinstance(d, dict):
        return d.get("mergeable")
    return None


def gh_review_comments(pr):
    """Comentarios do PR: issue comments + review comments inline.
    Retorna lista de {id, login, created, body} — NAO inclui bots."""
    out = []
    for ep in (f"repos/{REPO}/issues/{pr}/comments",
               f"repos/{REPO}/pulls/{pr}/comments"):
        d = run([GH, "api", ep, "--jq",
                 "[.[] | {id: .id, login: .user.login, created: .created_at, body: .body}]"])
        if isinstance(d, list):
            out.extend(d)
    return [c for c in out
            if c.get("login") and not str(c.get("login", "")).lower().endswith("[bot]")]


def gh_last_commit_date(branch):
    d = run([GH, "api", f"repos/{REPO}/commits/{branch}",
             "--jq", ".commit.committer.date"])
    if isinstance(d, str) and d:
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def parse_dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def gh_pending_review(pr, branch):
    """Comentario de review humano mais recente que ainda NAO foi respondido
    (mais novo que o ultimo commit da branch) E nao marcado como processado.
    Retorna dict ou None."""
    comments = gh_review_comments(pr)
    if not comments:
        return None
    last_commit = gh_last_commit_date(branch)
    if not last_commit:
        return None
    pend = [c for c in comments
            if parse_dt(c.get("created")) > last_commit
            and not is_review_processed(c.get("id"))]
    if not pend:
        return None
    return max(pend, key=lambda c: parse_dt(c.get("created")))


def mark_review_processed(comment_id):
    """Marca um comment_id como processado (state file). Retorna bool."""
    try:
        state = {}
        try:
            with open(REVIEW_STATE, encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
        processed = set(state.get("processed", []))
        processed.add(str(comment_id))
        state["processed"] = sorted(processed)
        with open(REVIEW_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception:
        return False


def is_review_processed(comment_id):
    try:
        with open(REVIEW_STATE, encoding="utf-8") as f:
            return str(comment_id) in set(json.load(f).get("processed", []))
    except Exception:
        return False


def mark_conflict_processed(pr):
    """Marca um PR como ja re-despachado por conflito (state file). Retorna bool."""
    try:
        state = {}
        try:
            with open(CONFLICT_STATE, encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
        processed = set(state.get("processed", []))
        processed.add(str(pr))
        state["processed"] = sorted(processed)
        with open(CONFLICT_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception:
        return False


def is_conflict_processed(pr):
    try:
        with open(CONFLICT_STATE, encoding="utf-8") as f:
            return str(pr) in set(json.load(f).get("processed", []))
    except Exception:
        return False


def orca_worktrees():
    """Lista worktrees do Orca com linkedLinearIssue."""
    d = run([ORCA, "worktree", "ps", "--json"])
    if isinstance(d, dict):
        r = d.get("result", {})
        if isinstance(r, dict):
            return r.get("worktrees", [])
    return []


def sort_key(i):
    p = i.get("priority") or 0
    # none(0) por ultimo; urgent(1) primeiro; depois updatedAt
    return (1 if p == 0 else 0, p if p > 0 else 999, i.get("updatedAt") or "")


def started_dependents(ident, by_id):
    """Dependents de uma task started: issues em Backlog que ela desbloqueia
    (relacao outbound 'blocks', relatedIssue ainda em backlog)."""
    deps = []
    for r in linear_issue_relations(ident):
        if (r.get("direction") == "outbound"
                and r.get("relationship") == "blocks"
                and "relatedIssue" in r):
            rid = r["relatedIssue"].get("identifier")
            if rid and by_id.get(rid, {}).get("state", {}).get("type") == "backlog":
                deps.append(rid)
    return deps


def unblocked_backlog(issues, by_id):
    """Backlog DESBLOQUEADA: sem bloqueadores ou com todos os blockedBy
    Done/Canceled. Exclui estado 'To Refine' (tipo backlog mas aguardando
    refinement — o caminho certo e REFINE, nunca PROMOTE)."""
    backlog = [i for i in issues
               if i.get("state", {}).get("type") == "backlog"
               and i.get("state", {}).get("name") != "To Refine"]
    unblocked = []
    for b in sorted(backlog, key=sort_key):
        rels = linear_issue_relations(b["identifier"])
        blockers = []
        for r in rels:
            if (r.get("direction") == "inbound"
                    and r.get("relationship") == "blockedBy"
                    and "relatedIssue" in r):
                rid = r["relatedIssue"].get("identifier")
                if rid:
                    blockers.append(rid)
        if not blockers:
            unblocked.append(b)  # orfa de verdade, sem bloqueadores
            continue
        all_done = all(
            by_id.get(bid, {}).get("state", {}).get("type") in ("completed", "canceled")
            for bid in blockers
        )
        if all_done:
            unblocked.append(b)
    return unblocked


def worker_alive_count():
    """Numero de processos do executavel Hermes rodando com o WORKER_PROFILE
    (workers vivos). Filtra por Name — evita auto-match do powershell/bash do
    proprio cron (o comando de checagem contem o profile no command line)."""
    cmd = ["powershell", "-NoProfile", "-Command",
           f"(Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq '{HERMES_PROC}' -and $_.CommandLine -match '{WORKER_PROFILE}' }}).Count"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        out = p.stdout.strip()
        return int(out) if out.isdigit() else 1  # falha: assume 1 (nao mata nada)
    except Exception:
        return 1  # falha ao checar: assume vivo (nunca mata nada por engano)


def main():
    issues = linear_issues()
    if issues is None:  # falha real da CLI; lista vazia ([]) e estado valido -> IDLE
        print("WATCH_ERROR: nao consegui listar issues do Linear (CLI Orca ok?)")
        return 1

    by_id = {i["identifier"]: i for i in issues}
    started = [i for i in issues if i.get("state", {}).get("type") == "started"]
    events = []
    running = []  # tasks que ocupam slot de WIP (In Progress, PR aberto ou worker rodando)

    # 1) Para CADA task em execucao: CONFLICT / REVIEW / MERGE / STUCK / aguarda
    alive_remaining = worker_alive_count()  # processos de worker vivos, distribuir entre tasks sem PR
    for cur in sorted(started, key=lambda i: i.get("updatedAt") or ""):
        ident = cur["identifier"]
        branch = f"{BRANCH_PREFIX}{ident.lower()}"

        num, url = gh_pr(branch, "open")
        if num:
            # REVIEW primeiro: comentario humano pendente (mais novo que o ultimo
            # push) re-dispara o worker mesmo com PR CONFLICTING — e assim o
            # worker resolve o conflito sozinho (pull --rebase + resolver).
            # Sem essa ordem, o continue do CONFLICT nunca deixaria o review
            # pendente ser processado (bug 2026-08: PR #10 QUE-8).
            rev = gh_pending_review(num, branch)
            if rev:
                events.append(f"REVIEW task={ident} pr={num} "
                              f"comment_id={rev['id']} login={rev['login']} url={url}")
                running.append(ident)  # re-disparo no MESMO worktree — segue ocupando slot
                continue
            if gh_mergeable(num) == "CONFLICTING":
                if not is_conflict_processed(num):
                    # Conflito novo (ou re-despacho anterior falhou): o cron
                    # re-despacha o worker para resolver SOZINHO e marca.
                    events.append(f"CONFLICT task={ident} pr={num} url={url}")
                running.append(ident)  # presa em conflito ate resolver
                continue
            running.append(ident)  # PR aberto aguardando review/merge do humano
            continue

        num, url = gh_pr(branch, "merged")
        if num:
            deps = started_dependents(ident, by_id)
            events.append(f"MERGE current={ident} pr={num} url={url} "
                          f"dependents={','.join(deps)}")
            # NAO ocupa slot: o worker ja parou; o handler MERGE fecha a issue
        else:
            # Sem PR aberto nem merged: ou o worker ainda trabalha, ou morreu
            # sem concluir (sessao encerrada por limite de turns/erro). Distribui
            # os processos vivos entre as tasks sem PR; o excedente e STUCK.
            if alive_remaining > 0:
                alive_remaining -= 1
                running.append(ident)  # worker ainda rodando, PR ainda nao existe
            else:
                events.append(f"STUCK task={ident} branch={branch}")
                running.append(ident)  # ocupa o slot ate o handler agir

    # 2) Capacidade livre (WIP total)
    capacity = MAX_PARALLEL - len(running)

    # 3) REFINE: um por tick, so com capacidade (refinar sem slot so adia)
    if capacity > 0:
        to_refine = [i for i in issues if i.get("state", {}).get("name") == "To Refine"]
        if to_refine:
            nxt = sorted(to_refine, key=sort_key)[0]
            events.append(f"REFINE task={nxt['identifier']} title={nxt.get('title', '')}")

    # 4) DISPATCH: tasks em Todo (unstarted) ate a capacidade
    if capacity > 0:
        todo = [i for i in issues if i.get("state", {}).get("type") == "unstarted"]
        for nxt in sorted(todo, key=sort_key)[:capacity]:
            events.append(f"DISPATCH task={nxt['identifier']} title={nxt.get('title', '')}")
            capacity -= 1

    # 5) PROMOTE: Backlog desbloqueada (ate a capacidade restante). Exclui
    #    dependents que os MERGEs deste tick ja vao promover (o handler MERGE
    #    faz status set --to Todo) — evita PROMOTE redundante no mesmo tick.
    if capacity > 0:
        already = set()
        for ev in events:
            if ev.startswith("MERGE "):
                for d in ev.split("dependents=", 1)[-1].split(","):
                    if d:
                        already.add(d)
        candidates = [nxt for nxt in sorted(unblocked_backlog(issues, by_id), key=sort_key)
                      if nxt["identifier"] not in already]
        for nxt in candidates[:capacity]:
            events.append(f"PROMOTE task={nxt['identifier']} title={nxt.get('title', '')}")
            capacity -= 1

    # 6) CLEANUP: worktrees orfaos — so quando nao ha outros eventos (evita
    #    misturar limpeza com dispatch no mesmo tick; a regra de higiene do
    #    agente ja cuida da limpeza incremental a cada evento processado)
    if not events:
        orphans = []
        for wt in orca_worktrees():
            ident = wt.get("linkedLinearIssue")
            if not ident:
                continue
            issue = by_id.get(ident)
            if issue and issue.get("state", {}).get("type") in ("completed", "canceled"):
                orphans.append(ident)
        if orphans:
            events.append(f"CLEANUP worktrees={','.join(sorted(orphans))}")

    # 7) Saida: uma linha por evento (ou IDLE)
    if not events:
        print("IDLE")
        return 0
    print("\n".join(events))
    return 0


if __name__ == "__main__":
    # Modo utilitario: marca um comment_id como processado (usado pelo agente
    # do cron apos re-disparar o worker para resolver um review)
    if len(sys.argv) == 3 and sys.argv[1] == "--mark":
        ok = mark_review_processed(sys.argv[2])
        print("marked" if ok else "mark_failed")
        sys.exit(0 if ok else 1)
    # Modo utilitario: marca um PR como ja re-despachado por conflito (anti-loop:
    # o cron marca apos re-disparar o worker para resolver o conflito)
    if len(sys.argv) == 3 and sys.argv[1] == "--mark-conflict":
        ok = mark_conflict_processed(sys.argv[2])
        print("marked" if ok else "mark_failed")
        sys.exit(0 if ok else 1)
    sys.exit(main())
