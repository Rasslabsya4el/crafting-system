"""Run a command and write the peak resident memory of its largest process, in MB, next to its exit code (ticket #827; Linux runners).

    python research/827/peak.py OUT.json -- COMMAND ...

The figure is of one process, the largest of the command and its children: the planner's workers are not added to it, so it is below what
the run's own memory net counts, but it is the same measure on both sides of a pair.
"""

import json
import resource
import subprocess
import sys

out, command = sys.argv[1], sys.argv[3:]
code = subprocess.run(command).returncode
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024  # Linux reports kilobytes
with open(out, "w", encoding="utf-8") as file:
    json.dump({"exit": code, "peak_mb": round(peak, 1)}, file)
print(f"peak {peak:,.0f} MB, exit {code}", flush=True)
sys.exit(code)
