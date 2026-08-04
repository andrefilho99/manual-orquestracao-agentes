# Template do brief da task (description da issue no Linear)

> Formato obrigatório das descriptions. Brief de desenvolvedor REAL: Contexto →
> Objetivo (WHAT, nunca HOW) → Diretrizes (só convenções + dados fixos) → Critérios
> de aceite (resultados verificáveis) → Entrega. Implementação é julgamento do
> worker, documentada em Notes do PR.

```markdown
# <TASK_PREFIX>-<N> — <título curto e acionável>

## Contexto
- Repositório/base: `<REPO>`, branch base `<BASE>` (atualizada), estado atual do repo.
- O que já existe (tasks anteriores da cadeia, já mergeadas) e o que ESTA task adiciona.
- Onde o worker está: raiz de um **worktree git** na branch criada pela orquestração (a partir da base atualizada).
- Projeto/identidade fictícia se houver lacunas preenchidas pelo orquestrador.

## Objetivo
O WHAT em termos de produto — NUNCA o HOW. Implementação (cores, fontes, markup, comandos, verificação) é julgamento do worker, documentado na seção Notes do PR.

## Diretrizes do projeto
- Apenas convenções de equipe: ex. arquivo único `index.html`, CSS/JS inline, pt-BR, sem frameworks/build, PR para `<BASE>`.
- Dados FIXOS que não devem ser redecididos (dados de negócio, não código): paleta (hex exatos), fontes, moeda, ids de seção que tasks futuras vão mirar (ex. `inicio`, `catalogo`, `formulario`), tabelas de produto com nomes/preços/URLs de imagem — "dados fornecidos — não altere os valores".
- ⚠️ Repetir este bloco IDÊNTICO em toda issue da cadeia — modelo pequeno regride ao padrão de treino se algo ficar de fora.

## Critérios de aceite
- Resultados verificáveis, um por linha, SEM ditar implementação: ex. "README.md contém exatamente uma ocorrência do heading `## Status do projeto`", "nenhuma outra parte do arquivo alterada", "git status mostra apenas <arquivo>".
- Verificação (grep/inspeção) é do worker; o critério descreve o RESULTADO, não o comando.

## Entrega
- Commit → push da branch atual → **PR para `<BASE>`** → PARAR.
- Detalhes de processo (verificação antes do commit, git add seletivo, pr_body.md com Summary/Changes/How to verify/Notes, limite de tentativas) vivem no SOUL do worker — NÃO repetir aqui (o corpo descreve o que entregar, não como trabalhar).
- ⚠️ PARE após abrir o PR — NÃO faça merge, NÃO altere estados nem crie outras tasks.
```
