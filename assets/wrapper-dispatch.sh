#!/usr/bin/env bash
# Wrapper de DISPATCH do worker — template.
# O agente do cron escreve a versão final em <TEMP_DIR>/<bx>-run.sh (FORA do
# worktree, para nunca ser commitado). Ordem obrigatória: wrapper primeiro,
# `terminal create` depois.
#
# Placeholders (ver README, seção "Parâmetros"):
#   <WORKTREES_ROOT>  raiz dos worktrees do Orca
#   <bx>              identifier da task em minúsculas (PRJ-3 -> prj-3)
#   <HERMES_BIN>      binário do Hermes usado para disparar o worker
#   <WORKER_PROFILE>  perfil Hermes do worker
#   <TEMP_DIR>        diretório de temporários (bodies/wrappers)
#   <PROJ>            prefixo minúsculo do projeto

cd "<WORKTREES_ROOT>/<bx>" || exit 1
export HERMES_YOLO_MODE=1
exec "<HERMES_BIN>" -p <WORKER_PROFILE> chat -q "$(cat "<TEMP_DIR>/<PROJ>-bodies/<bx>-body.md")"
