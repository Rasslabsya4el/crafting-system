"""#1315: one table row per finished led.py log.    python ledsum.py OUTDIR > led-summary.md"""
import glob, re, sys

rows = []
for path in sorted(glob.glob(sys.argv[1] + "/led*-R*.log")):
    text = open(path).read()
    m = re.search(r"RESULT k-(\w+)\.pkl lead (\S+) rule (\S+): coarse keys (\d+); complete build works out (\d+) keys; led: no tip on the cheapest policy after (\d+) keys \(([\d.]+)%\), (\d+) rounds; "
                  r"within 1% of the complete value after (never|(\d+) keys \(([\d.]+)%\)), round \d+; within 10% after (never|(\d+) keys \(([\d.]+)%\)), round \d+; half after (never|(\d+) keys \(([\d.]+)%\)).*?(\d+) s$", text, re.M)
    if not m:
        rows.append((path, None))
        continue
    share = re.search(r"coarse start value \S+ \(([\d.]+)% of", text)
    rows.append((path, (m[1], m[2], m[3], int(m[4]), int(m[5]), int(m[6]), m[7], int(m[8]), m[10], m[11], m[13], m[14], m[16], m[17], share[1] if share else ("100.00" if m[2] == "exact" else "-"), m[18])))
print("| Route | Lead (parts of the key dropped; fold) | Rule | Coarse keys | Lead's start value, % of the complete | Exact keys worked out to the end | % of the complete build | Rounds | To within 1% | To within 10% | To half | Seconds |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for path, r in rows:
    if r is None:
        print(f"| {path.split('/')[-1]} | not finished | | | | | | | | | | |")
        continue
    route, lead, rule, coarse, total, end, endp, rounds, k1, p1, k10, p10, k50, p50, share, secs = r
    cell = lambda k, p: f"{int(k):,} ({p}%)" if k else "never"
    print(f"| {route} | {lead} | {rule} | {coarse:,} | {share} | {end:,} of {total:,} | {endp}% | {rounds} | {cell(k1, p1)} | {cell(k10, p10)} | {cell(k50, p50)} | {secs} |")
