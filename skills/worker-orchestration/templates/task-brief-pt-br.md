# {<TASK_PREFIX>-N} — {objetivo curto}

## Contexto
{1 linha: repo, branch base, identidade do projeto} + {o que já existe — tasks anteriores mergeadas} + {o que esta task adiciona} + {⚠️ em execução paralela: outros workers podem estar rodando em branches próprias — não toque arquivos fora do escopo}.

## Objetivo
{O QUE entregar, em termos de produto — nunca o COMO. Ex.: "Criar a grade de produtos com os 6 itens abaixo."}

## Diretrizes do projeto
- {convenções de time, não código: arquivo único, idioma, identidade, "não altere outras seções"}
- {em paralelo: prefira critérios que delimitem os arquivos tocados — conflito de merge é proporcional à sobreposição de arquivos}
- Fluxo de entrega: commit → push → **PR para `main`** → PARAR (detalhes de processo no SOUL do worker).

## Critérios de aceite
- {resultados verificáveis, orientados a comportamento — sem markup/comandos/greps prescritos}
- {ex.: "Os 6 produtos aparecem com imagem, nome, descrição e preço corretos."}
- {ex.: "git status mostra apenas <arquivo1>, <arquivo2>"}

## Entrega
- Commit descritivo, push da branch, **PR para `main`** com descrição explicando o que você fez (estrutura recomendada no SOUL).
- **PARE** após abrir o PR: não faça merge, não mexa em estados de issue. Reporte a URL do PR.
