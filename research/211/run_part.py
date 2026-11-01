"""Run this runner's share of the measured cases.  `python run_part.py --part I/N --out DIR`."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))

CASES = [
    "r25:n12:raw:lazy", "r25:n12:raw:lazy_support", "r25:n12:raw:lazy_empty", "r25:n12:raw:sizes", "r25:n12:class:lazy", "r25:n12:class:lazy_support",
    "r25:n12:class:lazy_empty", "r25:n12:class:unres", "r25:n12:class:struct_unres",
    "r25:n8:raw:lazy", "r25:n8:raw:lazy_support", "r25:n8:raw:lazy_empty", "r25:n8:raw:struct_unres", "r25:n8:class:lazy", "r25:n8:class:unres", "r25:n8:class:struct_unres",
    "r25:n6:raw:lazy", "r25:n6:raw:lazy_support", "r25:n6:raw:lazy_empty", "r25:n6:raw:unres", "r25:n6:raw:struct_unres", "r25:n6:class:lazy", "r25:n6:class:unres",
    "r18:c1:lazy", "r18:c1:unres", "r18:c1:unres_full", "r18:c2:lazy", "r18:c2:unres", "r18:c2:unres_full", "r18:c3:lazy", "r18:c3:unres", "r18:c4:lazy",
]
GAP = [("gapsearch.py", str(a), str(a + 8)) for a in range(0, 32, 8)]

if __name__ == "__main__":
    part, count = (int(x) for x in sys.argv[sys.argv.index("--part") + 1].split("/"))
    out = sys.argv[sys.argv.index("--out") + 1]
    os.makedirs(out, exist_ok=True)
    mine = CASES[part - 1 :: count]
    with open(os.path.join(out, f"part-{part}.jsonl"), "w") as sink:
        for case in mine:
            t = time.perf_counter()
            r = subprocess.run([sys.executable, os.path.join(HERE, "exp.py"), case], capture_output=True, text=True)
            line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else json.dumps(dict(case=case, error=r.stderr[-400:]))
            print(case, round(time.perf_counter() - t), "s", flush=True)
            sink.write(line + "
"); sink.flush()
        if part - 1 < len(GAP):
            name, a, b = GAP[part - 1]
            r = subprocess.run([sys.executable, os.path.join(HERE, name), a, b], capture_output=True, text=True)
            sink.write(json.dumps(dict(case=f"gap:{a}-{b}", output=r.stdout)) + "
")
