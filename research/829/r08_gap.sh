# R08's first plan and gap plan on main ($1, a commit) or this branch, one side per runner (research/829/r08_gap.py). $2: main or branch.
set -euo pipefail
if [ "$2" = main ]; then
  git fetch --depth 1 origin "$1"
  git worktree add --detach main-src FETCH_HEAD
  CRAFTING_SOURCE="$PWD/main-src/src" uv run --no-sync python -u research/829/r08_gap.py main
else
  uv run --no-sync python -u research/829/r08_gap.py branch
fi
