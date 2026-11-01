"""Run this runner's share of the measured cases.  `python run_part.py --part I/N --out DIR`."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))

CASES = ["r18:c3:unres", "r18:c4:lazy", "r25:n8:raw:lazy", "r18:c3:lazy_pw"]
GAP = [("gapsearch.py", str(a), str(a + 2)) for a in range(8, 16, 2)]
ITEMS = CASES + GAP

if __name__ == "__main__":
    part, count = (int(x) for x in sys.argv[sys.argv.index("--part") + 1].split("/"))
    out = sys.argv[sys.argv.index("--out") + 1]
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"part-{part}.jsonl"), "w") as sink:
        for item in ITEMS[part - 1 :: count]:
            t = time.perf_counter()
            if isinstance(item, str):
                r = subprocess.run([sys.executable, os.path.join(HERE, "exp.py"), item], capture_output=True, text=True)
                line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else json.dumps(dict(case=item, error=r.stderr[-400:]))
            else:
                r = subprocess.run([sys.executable, os.path.join(HERE, item[0]), item[1], item[2]], capture_output=True, text=True)
                line = json.dumps(dict(case=f"gap:{item[1]}-{item[2]}", output=r.stdout))
            print(item, round(time.perf_counter() - t), "s", flush=True)
            sink.write(line + chr(10))
            sink.flush()
