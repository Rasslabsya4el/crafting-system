#!/bin/bash
# queue.sh FILE MAX : each line of FILE is "TAG ROUTE PROCS ENV=VAL..." (one run1.sh call); at most MAX at once
S="/root/projects/crafting system/.claude/scratch/t1276c"; F=$1; MAX=$2
pids=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  while [ $(jobs -rp | wc -l) -ge $MAX ]; do sleep 20; done
  eval "set -- $line"
  "$S/run1.sh" "$@" &
  echo "$(date +%T) launched $1 pid $!"
  sleep 60
done < "$F"
wait
echo "$(date +%T) queue done"
