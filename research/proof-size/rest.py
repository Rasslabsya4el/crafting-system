"""t1363: R24's keys outside the lemma's F (Avoid Shock and T1 Suppress both passing): what they lack, and how many are in a certificate.
python rest.py SPEC.npz CERT_SUPPORT.npy  (in the folder of e-R24.npz)"""
import sys, re, pickle, numpy as np
e = np.load("e-R24.npz"); P = pickle.load(open("e-R24.npz.parts.pkl", "rb")); parts = P["parts"]; V, g = e["V"], e["goal"]
F = np.load(sys.argv[1])["free"]; S = np.load(sys.argv[2])
st = lambda k: tuple(int(x) for x in re.findall(r": (\d)>", parts[k][2]))
nf = np.flatnonzero(~F & ~g)
print("keys outside F", len(nf), "without a passing resistance", sum(not any(x == 2 for x in st(k)[4:7]) for k in nf),
      "holding an unveil's offer", sum("OfferedMod" in parts[k][3] for k in nf), "worth at least V0", int(np.sum(V[nf] >= V[0] * (1 - 1e-9))),
      "in the certificate", int(S[nf].sum()), "certificate size", int(S.sum()), "start in F", bool(F[0]), "start in certificate", bool(S[0]))
