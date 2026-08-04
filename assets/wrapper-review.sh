#!/usr/bin/env bash
# Wrapper de REVIEW do worker — template.
# Idêntico ao wrapper de dispatch, mas aponta para <bx>-review.md (body
# follow-up com o apontamento do review transcrito literalmente). Reusa o MESMO
# worktree — o worker dá push na mesma branch e o PR atualiza in-place.
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
exec "<HERMES_BIN>" -p <WORKER_PROFILE> chat -q "$(cat "<TEMP_DIR>/<PROJ>-bodies/<bx>-review.md")"
