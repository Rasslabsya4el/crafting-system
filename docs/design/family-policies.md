# Bounded fossil and fracture policies — lead design, 2026-09-21

These are policy and probability derivations over the accepted action rules, not new game
facts. Sources: mechanics/fossils_resonators.md, fracturing.md, essences.md, basic_currency.md;
D14 and D21. All prices are caller inputs. Each family exposes terminal distributions,
conditional utility, paid decisions and uncertainty; a scalar success chance is insufficient.

## Ordinary Chaotic fossil spam

Begin with Alchemy on the caller's normal base. Test the target immediately; otherwise apply
the selected full Chaotic resonator repeatedly to the rare item until success. No Scour is
needed between these full rerolls. Compare all nonempty subsets of the loadout's supported
fossil allowlist, up to four distinct fossils. To bound the prototype, allow at most four
fossils in this policy allowlist, hence at most15 combinations. The adapter supports18;
the example loadout offers Aberrant1, Pristine12, Scorched13 and Serrated14. These four are
a caller availability choice, not a claim they exhaust useful crafting. Other four-fossil
allowlists are valid. Special fossil IDs remain explicitly unsupported.

One attempt costs the sum of selected fossil prices plus one resonator price for exactly
that socket count. Require each permission and price separately. Never price each socket
as a separate resonator. D21 additive is default; explicit multiplicative sensitivity is
a labelled model comparison, not an extra proven candidate in the default ranking.

Let a=P(target after Alchemy), p=P(target after one selected fossil action), A=Alchemy price,
c=complete fossil/resonator price, B=base price. Exact mean=B+A+(1-a)*c/p. Terminal
distribution is a times successful Alchemy's conditional distribution plus (1-a) times
successful fossil's conditional distribution. If a=1, no fossil is consumed. If p=0 and
a<1, the policy cannot guarantee completion and is unavailable; do not condition away failures.

Cost distribution: atom B+A of probability a; remaining mass has cost B+A+c*N,
N~Geom(p). For q=.9, if a>=q the quantile is B+A; otherwise add c times
GeomQuantile(p,(q-a)/(1-a)). Handle c=0 deterministically. Expected resonator count=(1-a)/p;
each selected fossil has the same count. Keep the full action distribution for each stage.

Math fixture:a=.25,p=.5,A2,c3,B0 ->mean6.5, p90=11. CDF at8=.8125, at11=.90625.
If a=1 mean/p90=2 and fossil count0; if a=0 mean8,p90=14. Example subset costs with
all fossils1 and resonator prices1/2/3/4 are2/4/6/8 for1/2/3/4 sockets respectively.

## Fracture Life9 then Deafening Envy

This route is specifically for the ordinary Royal Burgonet86 exact helmet target. Start
each trial on a fresh paid base. Use Alchemy, then Scour+Alchemy after rejected rolls, until
exactly four ordinary explicits include Life9. Fracture uniformly: desired Life9 has chance
1/4, verified by the action's concrete four-state distribution. An unwanted fracture remains
on that item; set it aside with caller assumption salvage0 and buy/prepare a replacement.
On Life9 fracture, use Deafening Envy repeatedly until the target's elemental requirement
also holds. Life9 is retained; Envy forces Chaos6, and other modifiers reroll. No free undo.

Compare preparation early completion off/on. If on, any Alchemy roll already satisfying
the entire requested target ends the route before fracture, even outside the four-mod gate.
Let u=that early completion probability (0 when off), v=four-mod Life9 preparation mass
excluding early completions, s=u+v. Set f=1/4 and z=u+v*f. Failure to hit either gate
uses Scour+Alchemy. Let p be the final fractured-Envy success chance, F=Fracturing price,
E=Envy price, A=Alchemy price, S=Scour price, B=each fresh base price.

Expected counts: bases=s/z, Alchemy=1/z, Scour=(1-s)/z, Fracturing=v/z,
Envy=(v*f)/(z*p). Exact mean:

`[s*B + A + (1-s)*S + v*F + v*f*E/p] / z`.

Terminal mixture: early conditional Alchemy mass u/z; fractured-Envy success distribution
mass v*f/z. Early false gives4 paid bases and4 Fracturing on average, plus four complete
preparation costs and the final Envy loop. A wrong fracture is a paid discarded input;
the orb itself does not destroy it. Report discarded-base probability and expected count
separately from irreversible item-destruction risk0.

Seeded cost law without unbounded item loops: K~Geom(z/s) fresh base trials; independent
I~Bernoulli(v*f/z) says the last trial uses fracture. Total Alchemy J~NegBinomial(K,s)+K;
Fracturing count K-1+I; Envy count I*Geom(p). Cost is
`B*K + A*J + S*(J-K) + F*(K-1+I) + E*EnvyCount`.
Use N50000, seed20260921 and99% DKW interval for estimated p90. Guard s/z/p endpoints,
unreachable paths and nonfinite inputs; when v=0 the formula reduces to Alchemy stopping.

Math fixture:u0,v.5,f.25,p.5,B3,A2,S1,F5,E4 ->mean60. Early u.1,v.4 ->mean34,
bases2.5, Alchemy5, Scour2.5, Fracturing2, Envy1. Independent quantile fixture u0,v1,
f.25,p1,B1,A1,S0,F2,E3 has cost4*K+3, K~Geom(.25):mean19,p90=39.

For the actual source state, use Life9/Chaos6/Fire8/Cold8 as an eligible four-mod fracture
demonstration, not a guessed model for preparation's unknown junk. After fracture, each Envy
roll removes all nonfractured explicit identities, so its distribution only depends on
retained Life9, the forced Chaos6 and the ordinary pool. Use a validated Life9-only fractured
rare state to calculate that reroll. Never continue from an identity-free OutcomeClass.

Independent lead calculation at2f30602 before the fracture adapter: the accepted grouped
DP with retained Life9/Chaos6, both groups excluded, and total-2 remaining draws gives
30 terminal classes and finish probability .06101200110346221. Default prices/base0
give early-off mean4244.571170153949 versus early-on4227.736691448135. The early-on
preparation masses are u=.000024282088455126462 and v=.02428733447648724. These are
acceptance references for the forthcoming adapter/policy, not proof of its implementation.
Reproduction details and measured counts: out/lead-fracture-reference.json (local output).
