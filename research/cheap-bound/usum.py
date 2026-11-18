"""#1321: one table row per uled.py log (finished or stopped).    python usum.py OUTDIR > uled-summary.md"""
import glob, re, sys

print("| Route | Lead (lower value of a tip) | Lead at the start, % | Rule | Weights | End | Keys at the end | Stop L >= 0.99 U, restart upper | Stop, no upper at tips | L within 1% of V | U (restart) within 1% of V | U (no upper) within 1% of V | Seconds | Peak GB |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def upper_within(tsv):
    """first keys worked out at which each incumbent is within 1% of the complete value (read from the per-round file)"""
    try:
        rows = [line.split("\t") for line in open(tsv).read().splitlines()[1:]]
    except OSError:
        return "-", "-"
    v = next((float(r[2]) / float(r[5]) for r in rows if float(r[5]) > 0), None)
    first = lambda col: next((f"{int(r[1]):,}" for r in rows if v and float(r[col]) <= 1.01 * v), "never")
    return first(3), first(4)

for path in sorted(glob.glob(sys.argv[1] + "/u-R*.log")):
    text = open(path).read()
    m = re.search(r"RESULT k-(\w+)\.pkl lead (\S+) rule (\S+) upper-weights (\S+): coarse keys \d+; complete build (\d+) keys; (STOPPED at the limit after|no tip on the lower policy after) (\d+) keys \(([\d.]+)%\), (\d+) rounds; "
                  r"stop L >= 0.99 U \(restart upper\) after (never|[^;]+); stop L >= 0.99 U \(no upper at tips\) after (never|[^;]+); L within 1% of the complete value after (never|[^;]+); .*?; (\d+) s; peak memory ([\d.]+) GB", text)
    lead = re.search(r"^lead \S+: coarse keys \d+; at the start \S+ \(([\d.]+)%\)", text, re.M)
    if not m:
        last = [line for line in text.splitlines() if line.startswith("  round")][-1:] or ["no round"]
        print(f"| {path.split('/')[-1]} | running or failed: {last[0].strip()[:160]} | | | | | | | | | | | | |")
        continue
    short = lambda s: s if s == "never" else re.sub(r", round \d+", "", s)
    end = "stopped at the limit" if m[6].startswith("STOPPED") else "no tip on the policy"
    print(f"| {m[1]} | {m[2]} | {lead[1] if lead else '-'} | {m[3]} | {m[4]} | {end} | {int(m[7]):,} ({m[8]}%) of {int(m[5]):,} | {short(m[10])} | {short(m[11])} | {short(m[12])} | {' | '.join(upper_within(path[:-4] + '.tsv'))} | {m[13]} | {m[14]} |")
