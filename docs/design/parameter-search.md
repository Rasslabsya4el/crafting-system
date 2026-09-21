# Bounded template parameter search — lead design, 2026-09-21

GOAL2 replaces fixed recipes with enumerated choices under the same sourced ordinary rules
in basic_currency.md, bench_metamods.md, affix_generation.md, essences.md and harvest.md.
These are policy/mathematical choices, not new game mechanics. D14 source limitations persist.

## Legal protected cycles
Three Exalts after lock+Scour can fill all prefixes on failure. A new prefix lock then has
no slot. Therefore k=1 or2 failed Exalts may repeat the lock/scour cycle; k=3 full failure
must return to Envy preparation on the same base. No free lock, annul, or empty slot is
invented. This costs more than treating all three-Exalt failures as ordinary repeat cycles.
Success is checked after each slam. A rejected lower life tier blocks its group until Scour;
the group-aware draw DP handles that event, so probabilities are not independent p per slam.

Let q_j be probability of target life after j prefix draws from an empty prefix side;
q_0=0. Success first at j has probability d_j=q_j-q_(j-1), j<=k. The cycle success
p=q_k; expected number of Exalts=sum_(j=0..k-1)(1-q_j). L is lock+Scour price.
Cycle cost expectation c=L+Exalt_price*sum survival. Full-reset probability b is1-p for
k=3 and0 for k<=2. Other failure probability r=1-p-b. Every cycle starts from the same
prepared full-suffix state, and side groups must be disjoint. The empty-prefix reset
makes these repeated prefix distributions independent; projected junk outcomes are never
used to continue arbitrary future draws.

For Harvest use its exact success p, failed-three-prefix mass b and constant cycle cost
lock+reforge. A nonfull failure has room to relock; a full failure returns to preparation.

## Preparation acceptance and early completion
Each Envy roll either completes the requested item (probability u), prepares a usable suffix
state (v), or repeats. The outcomes for u and v are DISJOINT: when early completion is on,
remove completed outcomes from preparation. When off, u=0 and even a naturally successful
prepared item continues through the declared cycle. Preparation variants require exactly3
suffixes, at least1 or2 desired elemental suffixes, and at most1 or2 prefixes. These are
real choices with sourced slot constraints, not changes to the target. Full desired items
may early-stop even when outside the chosen preparation subset.

With Envy price e, raw-state continuation R and prepared continuation W:

`R = e + (1-u-v)*R + v*W`

`W = c + r*W + b*R`

Thus `D = u*(p+b)+v*p` and
`R = [e*(p+b)+v*c]/D`, with base cost once. A zero denominator is unreachable.
Expected Envy applications `(p+b)/D`; expected prefix cycles `v/D`.
Final probability of early terminal output is `u*(p+b)/D`; via prefix stage is `v*p/D`.
Conditional final prefix hit at j has probability d_j/p. Combine terminal distributions
with these probabilities, retaining actual final prefix/suffix counts.

Checks: u0,v.5,e5,p.25,b.25,c2 ->mean28, Envy4, cycles4. b0 ->18.
u.1,v.4 with the former other values ->mean22, Envy10/3, cycles8/3.
Add base7 once ->35/25/29 respectively. These fixtures are mathematical inputs.

## Exact mean and sampled p90 without unbounded item simulation
Let s=u+v, t=p+b and q=D/(s*t). Raw preparation blocks end in U or W; a block eventually
finishes instead of resetting with probability q. Draw N~Geom(q) raw blocks.
The final block visits W with probability `(v*p)/D`; let I be this independent Bernoulli,
so H=N-1+I total W visits. Total Envy applications J~NegBinomial(N,s)+N.
Total prefix cycles K~NegBinomial(H,t)+H (K=0 when H=0).
For a fixed max k Exalt cycle, let F=L+k*Exalt_price. Every failed cycle costs F; the final
successful prefix cycle has cost L+j*Exalt_price, with j drawn from d_j/p if I=1.
Total cost=`base+e*J+F*K-I*(k-j)*Exalt_price`. For Harvest use F=lock+reforge and no
last-cycle discount. N,J,K have their standard failures-before-success NB convention.
All input draws use an explicit NumPy generator; N50000, seed20260921, DKW99% interval.
This is the joint renewal law; it is not a percentile of expected costs. Guard p=0,
b=0, u=0, v=0 and probability1 branches. A u>0,v=0 policy is just Envy stopping.

## General finite magic schedule
For each raw magic cycle, perform Alteration and Augment if required, reaching two mods
with magic caps1/1. At this decision: stop if target and early-stop enabled; otherwise
continue only if the number of desired labels meets m in{0,1,2}; rejected states reset.
Then Regal. Check target if early-stop enabled; optional gate after Regal uses minimum
desired count n in{0,1,2,3}. Exalt up to k in{0,1,2,3}, checking target after each if early
stop is enabled. If no early stop, test only at the last configured stage. Restart failures
with Scour+Transmute. First Transmute is paid setup and intentionally discarded, unchanged.
One/two-mod Alteration plus optional Augment has the same two-draw law under D14, so the
augmentation coin is independent of the subsequent path. Keep exact internal group profiles
through every gate; only absorbing/completed outputs may discard group identities.

An attempt produces joint atoms (terminal class, success/failure, paid stage index, mass).
For attempt success probability P, unconditional mean attempt cost E and failure reset B,
the total mean is `setup+(E+(1-P)*B)/P`. A cost correlated with success cannot use the old
independent compound-geometric shortcut. To sample costs: failures count~Geom(P)-1;
sample counts of conditional-failure cost atoms using a multinomial, add one independent
conditional-success atom, and add resets/setup. A fixed finite atom set has bounded memory.

## Parameter domains and output
Every candidate exposes a parameters object: item_level, forced essence ID (or null),
magic gates/Exalt limit/early-stop when applicable, protected cycle kind/k/preparation gates,
bench finish ID (or null), target stopping threshold. Rank each evaluated instance by
mean then p90; report chosen instance and candidate count per template. Retain a bounded
audit table of evaluated mean costs and explicit unavailable reasons.
Essence forcing choices are exactly the caller's allowed essence IDs. The existing optional
bench finish is valid on the known-one-prefix protected route; never attach it to unknown
junk states or full prefixes. Stop-now is also a candidate. It adds no invented target value.

Item level remains the caller's fixed input by default. An explicit optional search interval
may offer lower/different bases: evaluate its lower bound and each eligible PoB modifier
level breakpoint through its upper bound, collapsing identical pool signatures. Preserve
target tier IDs: lowering ilvl must never silently lower the requested quality/utility target.
Use the same caller base price for all offered levels and disclose that assumption. Show
chosen level and search range. The optimizer must not silently change a fixed input level.
Cache raw distributions by all draw inputs, excluding price/threshold; use gate-aware cache
keys for conditional schedules. No speculative classes/frameworks or multiprocessing.

## Solver boundary
Target labels+junk counts are generally not Markov: two junk prefixes can remove unequal
future group weights. Any later general-solver experiment must retain group-profile counts
or prove lumpability. A terminal OutcomeClass is suitable for scoring, not arbitrary actions.

## Measured helmet baseline for acceptance

Lead evaluated the accepted grouped prefix DP at527efa7,2026-09-21. With existing Envy
preparation probability0.0556753020849824 and example prices:

| Max Exalts | Cycle success | Mean cycle price | Full-reset probability | Total mean |
|---:|---:|---:|---:|---:|
| 1 | 0.02546148949713558 | 210.5 | 0 | 8357.193927854994 |
| 2 | 0.04784485723504098 | 220.24538510502865 | 0 | 4693.130543194264 |
| 3 | 0.06674609236085167 | 229.76693653267824 | 0.9332539076391483 | 4787.896236081543 |

The third-slam full-failure reset is charged. Before preparation early-stop optimization,
two slams win this three-choice Exalt comparison. Accepted Harvest has p0.07950823245417578,
b0.07592833649031873 and baseline mean2703.6093795549086. Envy spam remains1927.479966
under these invented prices; no new best-policy claim precedes the full grid measurement.

## Preparation-grid reference measured by the lead

At3712602, using one accepted Envy distribution and the renewal equations above, all32
protected Exalt/Harvest mean candidates were evaluated independently of the forthcoming
optimizer. The best in each bounded cycle family has max_prefixes1, min_elemental2 and
early_stop=true. It has u=.002594060684443422 and v=.0005495684166343905.

| Cycle | Mean under that gate |
|---|---:|
| Exalt1 | 3035.8209417281146 |
| Exalt2 | 2395.2703398566505 |
| Exalt3 with paid full reset | 1948.603171950813 |
| Harvest Life | 1986.1982162752881 |

These are exact-mean references under D14 and invented prices, not new probability sources.
They do not certify the optimizer, its p90 or terminal distributions. The full grid is
preserved in ignored out/lead-protected-grid.json. Gate maxP2/minElem1 with early stop gives
Exalt2=4480.326415, Exalt3=2807.303177 and Harvest=2476.341782. Strict preparation becomes
cheaper here because more successes end during Envy and fewer items enter an expensive
protected cycle. Pure Envy1927.48 remains cheaper than every protected instance. A minimum
within a named template must not be described as a reason to choose it over the whole library.
For that selected Exalt3 gate, terminal mass .9860565798144074 finishes during Envy,
and .01394342018559255 after prefix crafting; expected prefix cycles .2089024194886161.
The selected Harvest gate instead finishes early with mass .9022275259266133 and uses
expected1.2297151006310874 prefix cycles. These are the same renewal equations above.
Most of the protected-template price reduction therefore comes from preserving complete
preparation outcomes, not from claiming that expensive prefix crafting beats pure Envy.
