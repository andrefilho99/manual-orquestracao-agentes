# Repo manual de orquestração — estrutura e receita de genericização (2026-08)

O pipeline validado (cron watcher + Linear + Orca + worker local) foi destilado num
repo-manual **100% genérico**, pronto para virar repositório:
`manual-orquestracao-agentes/` (ainda sem `git init`).

## Estrutura final

```
manual-orquestracao-agentes/
├── README.md          ← visão geral + exemplo de fluxo tick a tick + tabela de 12 cenários
├── manual.md          ← referência completa (dependências, placeholders, bootstrap, scripts, prompt do cron, pitfalls)
└── assets/            ← scripts + configs + templates (renomeada de Scripts/ — ver abaixo)
    ├── merge-watch.py         ← watcher determinístico; bloco CONFIGURAR POR PROJETO no topo
    ├── wrapper-dispatch.sh    ← wrapper de dispatch (template, placeholders)
    ├── wrapper-review.sh      ← wrapper de review (template, placeholders)
    ├── worker-SOUL.md         ← SOUL do worker genérico (template)
    ├── worker-config.yaml     ← config do perfil do worker (template; verify_on_stop: false)
    └── task-body-template.md  ← template do brief (description das issues no Linear)
```

## Preferências do usuário (correções explícitas nesta sessão)

1. **Exemplos no README, não no manual**: a seção "Exemplo de fluxo e cenários possíveis"
   foi inicialmente colocada no `manual.md` (seção 10) e o usuário pediu para movê-la
   para o README. Regra: README = porta de entrada + exemplos; manual.md = referência.
2. **Pasta de assets abrangente**: `Scripts/` foi renomeada para `assets/` porque passou
   a conter não só `.py`/`.sh` mas também configs (SOUL, config.yaml) e templates.
3. **Genericização total**: nenhum dado específico de máquina/projeto em doc compartilhado.

## Checklist de genericização (o que foi removido no SETUP-FLUXO-AGENTICO.md original)

Removido/substituído por placeholders:
- Caminhos de máquina: `<HERMES_HOME>`, `<GH_CLI>`,
  `<ORCA_CLI>`, `<HERMES_BIN>`, git-bash,
  `<TEMP_DIR>/<proj>-bodies/`, `<WORKTREES_ROOT>/...`
- IDs/valores do fluxo: wsId `<WS_ID>`, repoId `<REPO_ID>`, team `<TEAM_KEY>`,
  repo `<SEU_USUARIO>/<REPO>`, prefixo `<SEU_USUARIO>/`, branch `<proj>-3`
- Nomes: perfil do worker (→ `<WORKER_PROFILE>`; SOUL abre como "a focused
  task-execution agent"), modelo local (→ `<LOCAL_MODEL>`), orquestrador (→ `<ORCHESTRATOR_MODEL>`),
  plugin `spotify`, bloco `onboarding` do config
- Marcas "✓ instalado" da seção de dependências
- Exemplos de ids de seção do projeto real (`hero`/`produtos`/`contato` → neutros)

Mantido intacto: arquitetura, lógica do watcher (IDLE/REFINE/DISPATCH/REVIEW/MERGE/
PROMOTE/CLEANUP), prompt do cron (parametrizado), bootstrap, os 15 pitfalls, template
do brief. Scripts extraídos com bloco `CONFIGURAR POR PROJETO` no topo.

## Placeholders (duas tabelas no manual.md)

- **Ambiente** (muda por máquina): `<ORCA_CLI>`, `<GH_CLI>`, `<HERMES_BIN>`,
  `<BASH_BIN>`, `<HERMES_HOME>`, `<SCRIPTS_DIR>`, `<TEMP_DIR>`, `<WORKER_PROFILE>`,
  `<LOCAL_MODEL>`, `<LOCAL_SERVER_URL>`
- **Projeto** (muda por projeto): `<REPO>`, `<BASE>`, `<BASE_REPO_PATH>`, `<WS_ID>`,
  `<TEAM_KEY>`, `<REPO_ID>`, `<TASK_PREFIX>` (ex. `PRJ` → `PRJ-1`), `<PROJ>` (ex. `prj`),
  `<BRANCH_PREFIX>` (ex. `usuario/`), `<WORKTREES_ROOT>`, `<bx>` (identifier minúsculo)

## Verificação antes de entregar doc genérico

```bash
grep -n -i -E "<tokens_especificos>" <doc>.md
# ex.: nome de usuário da máquina, dono/repo do GitHub, wsId/repoId/team key do Linear/Orca,
#      nomes de modelo (local/orquestrador), nome do perfil worker, prefixo de task, ids de seção do projeto
# exit 1 = nenhum match; revisar qualquer match restante (exemplos podem precisar de troca)
```

## Técnica: mover/renumerar seções sem quebrar referências

Antes de inserir/remover/mover uma seção numerada, verificar referências internas:
`grep -n -E "se[çc]ão (N|N±1)" <doc>.md` — se não houver refs aos números afetados,
a renumeração é segura. Foi assim que a seção 10 (exemplos) saiu do manual.md e a
numeração das seguintes (Armadilhas → 10, Referências → 11) foi ajustada sem quebrar nada.

## Bootstrap de projeto novo (resumo)

Copiar `manual.md` → preencher tabelas de placeholders → copiar `assets/merge-watch.py`
para `<SCRIPTS_DIR>/<PROJ>-merge-watch.py` preenchendo o bloco `CONFIGURAR POR PROJETO`
→ criar cron (every 5m, deliver local, toolsets terminal+file, script .py, prompt da
seção 8.2 do manual) → smoke test do perfil worker → task piloto. Montar o perfil do
worker a partir de `worker-SOUL.md` + `worker-config.yaml` (verificar `verify_on_stop:
false` e toolsets restritos).
