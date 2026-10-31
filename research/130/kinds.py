from light import *
d, ab, L = make(float, True)
tot = {"prefix":0,"suffix":0}
for k,v in sorted(L.info.items(), key=lambda kv:(kv[1]["side"], kv[1]["W"])):
    goal = any(sum(c) for c,_ in v["classes"])
    print(v["side"], v["N"], v["W"], "GOAL" if goal else "", v["names"], v["classes"] if goal else "")
    tot[v["side"]] += v["N"]*v["W"]
print(tot)
