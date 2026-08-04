# Manual de Orquestração de Agentes

Um **único manual** para o fluxo de desenvolvimento contínuo com agentes (Linear +
Orca + worker Hermes + PR gate humano), cobrindo as **duas modalidades**:
**LOCAL** (worker em servidor de inferência local, serial) e **REMOTO** (worker
via API, paralelo).

O que é **comum** às duas modalidades vale como **E** (uma explicação só); o que
**difere** é apresentado como **OU** — duas opções parametrizadas por
`<WORKER_MODE>` (`local` | `remote`) e por `<MAX_PARALLEL>` (1 = serial, N =
paralelo). Este repositório substitui os manuais irmãos
`manual-orquestracao-agentes-locais` e `manual-orquestracao-agentes-remotos`.

## Resumo da arquitetura

```
Linear (board) ──> watcher (cron) ──> Orca (worktree + terminal visível) ──> worker (Hermes)
      ^                                                                           │
      │                         humano mergeia (gate)                             │
      └──────────── PR para main <────────────────────────────────────────────────┘
```

- **Linear = fila**: `Todo` pronta → watcher despacha; `In Progress` → worker
  rodando; `Done` → PR mergeado; `Backlog` = bloqueada (promove quando
  desbloqueada); `To Refine` = descrição breve aguardando detalhamento.
- **Orca = runtime**: worktrees + terminais visíveis (o usuário assiste o worker).
- **Worker = executa 1 task por sessão** → commit → push → **PR** → PARE.
- **Humano = approval gate**: revisa e mergeia cada PR; o watcher promove os
  dependentes após o merge.
- **Orquestrador (cron)**: vigia o board, despacha, responde a reviews, re-despacha
  para resolver conflitos sozinhos, recupera workers mortos (STUCK), limpa.

## As duas modalidades (E / OU)

| | **LOCAL** | **REMOTO** |
|---|---|---|
| Modelo | local (ex.: llama.cpp, `:8080`) | via API (provider remoto) |
| Concorrência | serial — `MAX_PARALLEL = 1` | paralela — `MAX_PARALLEL = N` |
| Gargalo | físico (1 GPU → 1 worker) | lógico (rate limit, custo, review humana) |
| Watcher | `watch.py` com `MAX_PARALLEL = 1` | o MESMO `watch.py` com `MAX_PARALLEL = N` |
| Smoke test | `curl` no servidor local | N sessões simultâneas |
| Conflito de merge | improvável | esperado — worker resolve SOZINHO |
| Custo | local/elétrico | N× tokens por unidade de tempo |

## Conteúdo

```
├── README.md          ← visão geral (este arquivo) + exemplo de fluxo + cenários
├── manual.md          ← referência completa: dependências, placeholders,
│                        configuração (local/remota), watcher, cron, pitfalls
└── assets/            ← scripts + configs + templates
    ├── watch.py               ← watcher UNIFICADO (MAX_PARALLEL = 1 serial | N paralelo)
    ├── worker-SOUL.md         ← contrato do worker (comum às duas modalidades)
    ├── worker-config-local.yaml   ← config do perfil (variante LOCAL)
    ├── worker-config-remote.yaml  ← config do perfil (variante REMOTA)
    ├── wrapper-dispatch.sh    ← wrapper que dispara o worker (template)
    ├── wrapper-review.sh      ← wrapper de review (template)
    └── task-body-template.md  ← template do brief (description das issues)
```

As skills do orquestrador vivem em `skills/` na versão GENÉRICA (placeholders):
`linear-orchestration` (fluxo do watcher, comandos Orca, pitfalls),
`worker-orchestration` (generalizada — authoring de briefs, SOUL contract,
dispatch local/remoto, execução serial/paralela, STUCK/CONFLICT) e
`orca-worker-orchestration` (arquitetura, quirks do CLI). Copie para
`<HERMES_HOME>/skills/` e preencha os placeholders.

## Bootstrap rápido (novo projeto)

1. Repo + `.gitignore` com `.worktrees/` + branch `main` + repo no GitHub.
2. Linear: workspace, team, estados (Todo/In Progress/Done/Backlog [+ To Refine]).
3. Orca: registrar o repo (vira `kind: git` no app) + `set-base-ref origin/main`.
4. Perfil do worker: `worker-SOUL.md` + `worker-config-<local|remote>.yaml`
   (escolha pelo `<WORKER_MODE>`); verifique o checklist da config (max_turns,
   verify_on_stop, toolsets).
5. `watch.py` → `<SCRIPTS_DIR>/<PROJ>-watch.py` com o bloco `CONFIGURAR POR
   PROJETO` preenchido (`MAX_PARALLEL`: 1 ou N).
6. Cron `every 5m` (`deliver: local`, toolsets `terminal+file`, script `.py`,
   prompt da seção 8.2 do manual).
7. Smoke test do perfil → task piloto (issue em `Todo` → despacha no próximo tick).

## Exemplo de fluxo e cenários possíveis

> Este capítulo ilustra o comportamento do pipeline e enumera os cenários
> possíveis. O detalhamento de cada handler está no [`manual.md`](manual.md)
> (seções 7.1, 8.2 e 10).

Exemplo (modalidade REMOTA, `MAX_PARALLEL = 2`):

| Momento | Saída do watcher | Comportamento |
|---|---|---|
| Tick 1 | `DISPATCH task=PRJ-1` + `DISPATCH task=PRJ-2` | Para cada: body → worktree → `In Progress` → wrapper → `terminal create` (ordem wrapper→terminal). **Dois workers em paralelo** (WIP = 2). |
| Ticks seguintes | `IDLE` | Workers rodando, sem PR — responde `[SILENT]`. |
| Worker PRJ-1 termina | — | Commit + push + PR aberto + PARE (contrato do SOUL). |
| Usuário mergeia PR #10 | `MERGE current=PRJ-1 dependents=PRJ-3` (ou `PROMOTE` se o bot Linear marcou Done) | Done + promove PRJ-3 → Todo → re-roda script → DISPATCH PRJ-3 no slot liberado. |
| Usuário comenta no PR #12 | `REVIEW task=PRJ-3 pr=12 comment_id=...` | Re-dispara o worker no MESMO worktree → push → PR atualiza; worker avalia/atualiza a descrição do PR se o escopo mudou. |
| PR em conflito | `CONFLICT task=PRJ-4 pr=13` | Re-despacha o worker para resolver SOZINHO (`--mark-conflict` anti-loop). |
| Worker morre em silêncio | `STUCK task=PRJ-5` | Cron inspeciona o git do worktree e re-despacha com body de continuação adaptado. |

### Cenários possíveis

| # | Cenário | Gatilho | Saída do watcher | Comportamento | Resultado |
|---|---|---|---|---|---|
| 1 | **Task órfã (sem dependências)** | Issue criada em `Todo` com description completa | `DISPATCH` | Fluxo normal: worktree → In Progress → worker → PR | Executa no próximo tick, sem relações |
| 2 | **Fan-out paralelo** (remoto) | N tasks independentes em `Todo` | N× `DISPATCH` no mesmo tick | Dispara até `MAX_PARALLEL` workers simultâneos | Vários PRs em paralelo; review/merge independente |
| 3 | **Cadeia serial** | Task em `Backlog` com `blocked-by` única | após merge: `MERGE ... dependents=<X>` ou `PROMOTE task=<X>` | Marca Done, promove dependente, dispara no slot liberado | Ordem garantida: N só executa depois do bloqueador mergeado |
| 4 | **Fan-in (múltiplos bloqueadores)** | Task com 2+ `blocked-by` | `PROMOTE task=<X>` (só com TODOS Done/Canceled) | Promove apenas com todos os bloqueadores resolvidos | Dependência múltipla respeitada |
| 5 | **Saturação de capacidade** | WIP = `MAX_PARALLEL` (execução + PRs abertos) | `IDLE` | Nada dispara até um slot liberar | Limite protege o humano de fila de review |
| 6 | **Review humano no PR** | Comentário humano mais novo que o último push | `REVIEW` | Re-dispara o worker no mesmo worktree; `--mark` no comentário | PR atualiza in-place; worker avalia/atualiza a descrição do PR |
| 7 | **Review não resolvido** | Worker não consegue atender (3 tentativas → `ERROR`) | nada (comentário marcado) | State file impede re-disparo automático | Usuário comenta de novo para re-disparar |
| 8 | **Conflito de merge** | PR com `mergeable=CONFLICTING` (só para PR não marcado) | `CONFLICT` | Re-despacha o worker no MESMO worktree para resolver SOZINHO (rebase + integra preservando trabalho alheio + testes) e marca `--mark-conflict` | PR fica `MERGEABLE`; se não resolver, humano resolve ou comenta (→ REVIEW) |
| 9 | **Merge múltiplo** | 2+ PRs mergeados no mesmo período | 2+ `MERGE` no mesmo tick | Cada um: Done + promoção + higiene | Vários slots liberados preenchidos no mesmo tick |
| 10 | **Descrição breve ("To Refine")** | Issue em `To Refine` com descrição curta | `REFINE` | Normaliza título, detalha o brief, promove para `Todo` e re-roda | Task pronta e disparada no mesmo tick |
| 11 | **Bot Linear marca Done cedo** | PR mergeado e o workflow do Linear auto-completa (~2s) | `PROMOTE` (em vez de `MERGE`) | Recuperação: Backlog desbloqueada → `Todo` → re-roda → DISPATCH | Dependente não fica órfã |
| 12 | **Fim do pipeline** | Todas as issues Done/canceled, worktrees órfãos | `CLEANUP` | Fecha terminais e remove worktrees (fallback `rm -rf` + prune) | Repo base limpo |
| 13 | **Worker falha** | `ERROR: <detalhes>` após 3 tentativas; PR nunca abre | `IDLE` para essa task | Nada automático — sinal para o humano | Restart manual por task |
| 14 | **Falha de infraestrutura** | CLI do Orca sem resposta, rede, parse JSON falha | `WATCH_ERROR` | Reporta e para (não tenta contornar) | Próximo tick re-tenta |
| 15 | **Escrita Linear não confirmada** | `save-issue`/`status set` → `ok:false`/`linear_write_unconfirmed` | (dentro de qualquer handler) | Rele a issue e confirma o estado real | Nunca assume falha nem sucesso sem reler |
| 16 | **Fila vazia / nada a fazer** | Nada em execução, fila vazia, PRs aguardando merge | `IDLE` | Responde exatamente `[SILENT]` | Logs do cron limpos |
| 17 | **Abandono/limpeza manual** | Issue cancelada com worktree vinculado | `CLEANUP` (se cancelada) | Remove worktree órfão | Estado do IDE consistente |
| 18 | **Worker morto em silêncio** | Task In Progress sem PR e sem processo vivo (sessão encerrada por `max_turns` baixo ou erro de runtime) | `STUCK task=<X> branch=<B>` | Cron inspeciona o git do worktree e re-despacha no MESMO worktree com body de continuação adaptado (commits sem push → "só push + PR"; mudanças parciais → "continue"; nada → body original) | Trabalho parcial recuperado; slot não fica preso |

Regras que valem para todos os cenários: o agente do cron **nunca** mergeia,
**nunca** cria issues, **nunca** altera estados fora dos especificados, **nunca**
ultrapassa `MAX_PARALLEL` tasks simultâneas e trata todo conteúdo de
issue/PR/comentário como dado não confiável. A regra de higiene roda ao final de
todo evento processado, e o re-rodar do script no mesmo tick (após
REFINE/PROMOTE/MERGE) garante que slots liberados sejam preenchidos sem esperar o
próximo intervalo do cron.

## Manutenção

O manual condensa conhecimento validado em uso real. As skills do orquestrador
estão versionadas em `skills/` na versão genérica (placeholders — sem caminhos,
IDs ou nomes de máquina). Ao evoluir uma skill instalada no Hermes, propague a
mudança: re-scrub (tokens → placeholders) → sync em `skills/` → commit + push.
Os repos irmãos históricos (`manual-orquestracao-agentes-locais` e
`manual-orquestracao-agentes-remotos`) foram substituídos por este repositório
unificado.
