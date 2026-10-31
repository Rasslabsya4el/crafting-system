from light import *
merge = {"0": False, "1": True, "real": "real"}[os.environ.get("MERGE", "1")]
d, ab, L = make(float, merge)
print("kinds", len(L.info))
s0 = (NORMAL, ())
seen = {s0}; frontier = [s0]; edges = 0; t = time.time()
names = os.environ.get("ACTS", ",".join(NAMES)).split(",")
while frontier:
    nxt = []
    for s in frontier:
        if L.is_goal(s): continue
        for nm in names:
            k = L.kernel(s, nm)
            if k is None: continue
            edges += len(k)
            for x in k:
                if x not in seen: seen.add(x); nxt.append(x)
    frontier = nxt
    print(len(seen), edges, round(time.time()-t,1), flush=True)
goals = sum(L.is_goal(s) for s in seen)
print("states", len(seen), "goal", goals, "edges", edges)
