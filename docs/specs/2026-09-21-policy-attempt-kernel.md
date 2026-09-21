# Spec: finite conditional draw schedules and correlated renewal costs

Worktree: `.worktrees/policy-attempt-kernel` (branch `w-policy-attempt-kernel`).
May touch ONLY `src/craftoracle/policy_attempts.py`, `tests/test_policy_attempts.py`.

## Why
GOAL2 parameter search needs legal early stops/gates and costs correlated with outcomes.
Implement the lead's mathematics in docs/design/parameter-search.md without deciding game
rules or changing the planner. This is one bounded pure-function slice, at most60minutes.

## Requirements
1. Read docs/design/parameter-search.md fully. Add a finite grouped draw-schedule evaluator
   accepting DrawEntry-compatible rows, labels, a sequence of (draws,prefix_cap,suffix_cap),
   per-stage continue predicates, target predicate and early-stop flag. Return success and
   failure terminal distributions BY stage index plus stage reach probabilities. All masses
   are unconditional and sum1. Never continue from OutcomeClass; preserve the accepted DP's
   selected group-profile counts through gates. Reuse private DP primitives if appropriate;
   no refactor of distributions.py. A stopped/exhausted stage must not charge later actions.
2. Predicates may inspect projected labels/counts to DECIDE stop/reject while live state retains
   group identity. Check success before continuation gate. With early_stop=False only final
   stage tests success. No initial groups needed beyond the existing blocked_groups and
   initial counts/labels contract. Empty/bad schedules/predicates/weights must fail explicitly;
   preserve deterministic state cap. Return peak live state count for later bounded research.
3. Add pure correlated-attempt cost functions accepting weighted success/failure cost atoms,
   nonnegative reset and setup costs. Exact mean = setup+(Eattempt+(1-P)*reset)/P. P=0
   raises explicit unreachable, P=1 valid. Cost p90 uses explicit NumPy Generator: failed
   attempt count Geom(P)-1, conditional-failure multinomial counts and one conditional-success
   draw. N50000/default seed supplied by caller, DKW99% interval and method metadata. Never
   simulate an unbounded action loop or assume per-attempt cost independent of success.
4. Add two-state preparation/protected-cycle cost function from the same design. Inputs
   u,v,preparation_price,p,b,failed_cycle_cost and success cycle cost atoms with CONDITIONAL
   weights (their expectation plus failure cost determines unconditional cycle c).
   Return exact mean, expected preparation/cycle counts, final early/via-cycle probabilities,
   and seeded p90 with the N/H/J/K law. Handle u>0,v=0 as pure preparation, p=0,u>0,
   b=0, probability1, zero H; unreachable/invalid combinations must fail explicitly.
   No hidden global caches. Every RNG is passed explicitly; imports cause no I/O.
5. Tests first; no full real pools or CLI changes. Independent bounded convolution for small
   p90 fixtures, seeded repeatability and Monte Carlo mean agreement with stated statistical
   tolerance. Run python -m pytest -q tests/test_policy_attempts.py.

## Facts and checkable numbers
Source: design/parameter-search.md; accepted D14 draw semantics. These are mathematical
fixtures, not unsourced game facts. A/B/C distinct prefix groups, weights1/1/2, two draws:
P(A present)=7/12, P(A,C)=5/12. Gate after first draw requires A, final target A+C:
success stage2 mass1/6, failure stage1 mass3/4, failure stage2 mass1/12. Stage costs2 then3
give unconditional attempt mean11/4; failure reset1 ->total mean43/2=21.5, setup7 ->28.5.
Early target A absorbs at draw1 withmass1/4; any surviving target hit occurs later without
sampling removed-group weight again. Zero-mass branches must not cause phantom paid stages.

Protected fixture entries A1/B1 in groupL,C2 groupX,D2 groupY (all prefixes): target A
q1=1/6,q2=1/3,q3=1/2. Lock+Scour L10, Exalt2, preparation u0,v.5,e5:
k1 mean82;k2 mean51;k3 with full-reset b.5 mean50. Raising preparation e50 makes k2 mean141,
k3 mean230, so choosing three slams unconditionally is wrong. Cycle first-hit terminal
counts follow actual hit stage and conserve probability.
Renewal u0,v.5,e5,p.25,b.25,constant cycle2 ->mean28, prep4, cycles4; b0 ->18.
u.1,v.4 otherwise same ->mean22, prep10/3, cycles8/3. Base7 adds7 once.
P=1 constant attempt2 setup7 ->mean/p90 9. Deterministic cost fixture should give a zero-width
quantile interval when all samples equal. N50000, delta.01 DKW epsilon=sqrt(log(200)/(100000)).

## Numbers to report
All listed probabilities/means; synthetic p90 and independent CDF bracket; test summary;
peak state count for the gated tiny fixture; commits and files. Report starts
`=== FINAL REPORT ===`. Do not modify the design/spec or implementation outside allowed paths.
