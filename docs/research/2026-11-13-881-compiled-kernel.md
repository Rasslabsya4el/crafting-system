# A compiled kernel generator against today's Python (research, 2026-11-13, ticket #881)

Question (#881): the maths review of 2026-11-13 names kernel generation in Python as the largest constant factor of a plan. Would a compiled kernel generator (Numba, or an ahead-of-time option) make a plan at least twice as fast, on Windows and Linux, with the same answers? This is a measurement: no file under `src/` or `tests/` changes.

Rules read: OR-12 (the settings of a measurement are not planner defaults), OR-26 (roots, not patches), OR-30 (a rebuild is accepted by measuring again), OR-32 and OR-33 (about a minute per plan; the 10-minute net). Inputs: ADR-0010, `docs/research/2026-10-30-4-solver-engineering.md`, `docs/research/2026-11-13-planning-speed.md`, tickets #827, #868. Scripts and results: `research/881/` (below). Nothing heavy ran on the owner's PC: every figure is from a GitHub runner through `heavy_dispatch.py`; only the small route R13 ran locally, to test the scripts.

The measurements ran on commit 73bad379, before the planner module of #880 landed; the scripts were then moved to the paths of `main` at 55b16a07 (`src/crafting_system/planner/`) and run there on R13. The code they measure did not change in #880 (files moved, not rewritten).

## Short answer

1. **Kernel generation is the largest part of a plan, but it is not arithmetic.** On R04, 67% of a plan's time goes into making the *key* of a kernel (which kernel a state and an action have), 6% into building kernels, 0.5% into turning chances into integer weights. On the generated case essences/medium: 51%, 10% and 1%. Making a key means: turn the state into an item object, ask the action for its outcomes on it, group the pool of candidate mods by family, read the pool into a signature. Exact fractions are 11 to 13% of the profiler's time, and most of that is comparing and hashing them (the pool's test that a weight is above zero, sorting, dict keys), not big-integer arithmetic. No candidate below builds a kernel: what is compiled and timed is one loop of the key path, in pools a second.
2. **The one loop in that path that can be compiled today is 100 to 140 times faster compiled, with the same result on every pool kept.** The pool-signature loop (group the candidates by family, sort, name the family types, name the signature) does about 4,000 pools a second today. On flat tables: plain Python 47,000 to 68,000 (14 to 17 times), Numba 381,000 to 436,000 (103 to 116 times), Cython 436,000 to 500,000 (116 to 141 times), the same on Linux and Windows. All three split the 49,184 pools of R04 and the 14,074 of essences/medium exactly as today's signatures do. Those pools come from two kinds of action only (an essence and the Exalted Orb): a guaranteed tag, fossil weights and lucky rolls did not occur (section 9).
3. **That loop is about a fifth of a plan, so compiling it would make a whole plan about 1.2 times faster, and the flat tables in plain Python give almost all of that (1.22 against 1.24 on R04).** These whole-plan figures are computed from the loop's share, not run. The gain comes from the data model (integer ids in flat tables instead of objects), not from the compiler.
4. **Compiling today's Python as it is gave nothing where it could be done, and could not be done where it matters most.** Cython compiled 143 of 164 modules (136 of the 225 a plan loads: items, actions, pools, states); the plans gave the same means and ran 3 to 5% *slower* on both systems. The kernel module itself (the key path's own code) crashes the Cython compiler and the search's module uses syntax it does not read, so those two ran as Python in this measurement; 18 more modules have that syntax, and one compiled module behaved differently from its source.
5. **Fixed-width integers do not hold today's kernels; floats hold the draws.** 99.8 to 99.9% of kernels have integer weights within 53 bits, but 134 of R04's 220,710 need 128 to 1,595 bits, so 128-bit integers hold not one kernel more than 64-bit. The planner's float mode reproduces every chance of every exact draw to a relative error of at most 4.6e-16 (the solver's tolerance is 1e-10).
6. **Recommendation: do not build a compiled kernel generator now.** Build ticket #827 (the key of a kernel from what the action reads, without calling the action per state) on flat tables with integer ids, behind one function that a compiled loop can later replace. Measure again. A compiled loop behind that seam is then two tickets if the profile still asks for it; a full compiled generator (state, key and kernel all compiled) is six to eight tickets and is not justified by these numbers. The 2 times the owner asks for can come only from removing the key path, which is #827's work (it is 67% of R04's plan and 51% of essences/medium's: at most 3.0 and 2.04 times if it cost nothing, so on essences/medium 2 times is the ceiling, not the expectation); it cannot come from a compiler alone.

## 1. What a kernel costs today

A *pair* below is one (state, action) whose kernel the search asked for (`Search._kernel` in `planner/_envelope.py`, counted as `realized`). For each pair the search first makes the kernel's key (`Abstraction.kernel_key`, `abstraction/_kernel.py`); pairs with a key seen before share the stored kernel, the others build it (`Abstraction.kernel`, then `integer_weights`).

**Pairs a second today** (pairs realized over the seconds the search spent expanding; plain runs, no instrumentation; three different runners per system):

| Plan | Pairs | Kernels stored | Linux runner: plan seconds, pairs a second | Windows runner: plan seconds, pairs a second |
|---|---|---|---|---|
| R04 | 618,816 | 220,617 | 305 s, 3,297; 363 s, 2,684; 358 s, 2,694 | 738 s, 1,302; 533 s, 1,838; 733 s, 1,319 |
| essences/medium | 151,487 | 31,633 | 83 s, 2,321; 75 s, 2,505; 123 s, 1,555 | 119 s, 1,733; 150 s, 1,340; 113 s, 1,813 |

The same plan differs by 20 to 65% between two runners of one system (essences/medium on Linux: 75 s and 123 s), so a whole-plan comparison below is always made on one runner. The ticket's figure (754,755 pairs in 364 s) is an earlier run of R04 at other prices; today's R04 at the committed prices realizes 618,816.

**Where the time goes** (stage stopwatches, `profile_plan.py --mode timers`; seconds inside each function with what it calls; Linux runner; the Windows runner gives the same shares: `kernel_key` 67% and 52%):

| Stage | R04 (303 s) | essences/medium (85 s) |
|---|---|---|
| The bound's build (`pattern_lower_bound`) | 88 s, 29% | 6 s, 7% |
| The search (`Search.run`) | 212 s, 70% | 75 s, 88% |
| **Making keys (`kernel_key`), in both of the above** | **203 s, 67%** (796,624 calls) | **44 s, 51%** (136,653 calls) |
| of it: the state as an item (`_item_of`) | 46 s, 15% | 4 s, 5% |
| of it: the action's outcomes on the item (`_outcomes`: the retained item, the pool) | 88 s, 29% | 21 s, 25% |
| of it: the pool's signature (`_signatures_of`) | 39 s, 13% | 12 s, 14% |
| of it: reading the result back into state terms (`_splits_of`) | 11 s, 4% | 3 s, 3% |
| Building kernels (`kernel`) | 19 s, 6% | 8 s, 10% |
| of it: the exact draw (`exact_distribution`) | 6 s, 2% | 5 s, 5% |
| Integer weights (`integer_weights`) | 1.5 s, 0.5% | 0.8 s, 1% |
| The solver (`solve_graph`) | 16 s, 5% | 7 s, 9% |
| Reading an action's lower cost (`Search._q`) | 9 s, 3% | 12 s, 15% |

`_item_of` is also called from outside a key (the bound's members), so its seconds are not all inside `kernel_key`.

Two facts stand out. First, the cache of prepared pairs is cleared after every state (`CraftingProblem.release`), and for an action that reads the item's ordinary mods its key holds every slot of the state (an action that erases them keeps only the crafted slots), so 80% of the calls build the item and ask the action again (R04: 872,252 `_outcomes` calls for 1,096,612 lookups). Second, most of that work finds a kernel that already exists: on R04 the essence (`ApplyEssence`) made 301,746 keys and built 174 kernels; on essences/medium 103,099 keys and 58 kernels. Per kind of action (the instrumented run, so the seconds are higher than in the table above; `results/bench-linux/`):

| Kind of action, R04 | Keys made | Seconds in `kernel_key` | Kernels built | Seconds in `kernel` |
|---|---|---|---|---|
| `ApplyEssence` | 301,746 | 153 | 174 | 6 |
| `ExaltedOrb` | 121,421 | 62 | 101,716 | 10 |
| `AnnulmentOrb` | 155,496 | 47 | 154,553 | 8 |
| `FracturingOrb` | 184,349 | 27 | 35,128 | 2 |
| `BenchCraft`, `RemoveCraftedMods` | 33,612 | 5 | 8,417 | 0.2 |

**What kind of work it is** (`profile_plan.py --mode cprofile`; the profiler slows the plan 3.6 times on R04 and 2.3 times on essences/medium, and call-heavy code more than the rest, so these are shares of the profiler's own seconds, not of the plain plan; Linux runner only; `profile_groups.py` on the two `.prof` files in `results/prof-linux/` prints it):

| Kind of work | R04 | essences/medium |
|---|---|---|
| `Fraction`: comparing and hashing (the pool's `weight <= 0`, sorting weights, keys of dicts) | 8.9% | 8.9% |
| `Fraction`: arithmetic and making new ones | 1.6% | 4.0% |
| `math.gcd`, `math.lcm` | 0.2% | 0.5% |
| Hashing and comparing other objects | 2.2% | 2.2% |
| `isinstance` and abstract-class checks | 7.3% | 7.4% |
| `items/model.py`: building and validating items | 18.9% | 11.8% |
| `actions/pool.py`: the pool | 6.4% | 7.1% |
| `abstraction/_kernel.py` itself | 14.5% | 14.8% |
| `dataclasses`, `enum` | 4.3% | 3.1% |
| numpy and the solver | 3.2% | 5.7% |

Big-integer `*`, `+` and `//` inside a function are not calls, so they sit inside that function's own time; the stage table bounds them: all of `integer_weights` is 0.5 to 1% of a plan. The largest single functions on R04 are `group_pool` (the candidates grouped by family, 514,260 calls), `Fraction.__eq__` (77.6 million calls), `Fraction.__le__` (63.6 million: `group_pool` asks of every candidate whether its weight is above zero), `isinstance` (229 million), `sorted`, and the item's `__post_init__` (3.4 million items built).

## 2. The prototypes

**The loop.** One pool-draw part of an action's outcomes is read into a signature by two functions: `actions.pool.group_pool` (the candidates grouped by family, each a `PoolMod` in a `PoolFamily`) and `Abstraction._pool_signature` (per family its side and the sorted label, weight and guaranteed flag of its mods; then the sorted family types with the pool's head: the tag, the blocked tags, the mods kept, the free slots, the totals). Equal signatures share one cached distribution of the draw. This pair is the top of the profile and the one part of the key path that is a loop over numbers once the data is flat.

**The flat form** (`bench_kernels.py`). A candidate is an id whose static columns are its family and side, its label id, its weight id and its guaranteed flag, packed into one 64-bit sort key. Labels and weights are interned by equality: no weight is read as a number, so nothing is rounded. A pool is the list of its candidate ids in data order plus the id of its head. The loop sorts the keys of a pool, turns each run of one family and side into a family type (interned by its whole content, compared after the hash), sorts the types and interns the signature the same way. It returns a signature id per pool.

**The candidates**, all running the same loop on the same pools:

- `flat_python.py`: plain Python on lists and dicts. What the flat tables buy before any compiler.
- `flat_numba.py`: Numba 0.68.1 (`@njit`), compiled at the first call. Fixed-width: 64-bit integers for ids and hashes only.
- `flat_cython.pyx`: Cython 3.3.1, compiled ahead of time by the system's C compiler (gcc on the Linux runner, MSVC on the Windows runner; `build_cython.py flat`). The same fixed-width integers.
- Today's Python: the seconds its own `group_pool` and `_pool_signature` took for the same pools, timed inside the plan.

A fifth candidate measures a whole plan: **the package compiled as it is** (`build_cython.py source`: every module of `abstraction`, `actions`, `items`, `data`, `rules`, `solver`, `cli` compiled by Cython without a change, with `annotation_typing=False` so that an annotation never turns a `Fraction` into a C double), then the same plan on the same runner on the source and on the compiled copy.

**The check.** Each candidate's ids must split the pools exactly as today's signatures do: two pools get one id exactly when today's signatures are equal. It held for every candidate on every pool, on both systems. Pools kept: every 8th `_pool_signature` call of the plan (49,184 of R04's 393,479; 14,074 of essences/medium's 112,595), 123 and 103 candidates a pool on average. A pool with a family on both sides (jewels) would not be kept, because its signature has a part the prototype leaves out: none occurred.

**What the span leaves out, on both sides:** finding which candidates the item's mods block (`pool_candidates`, cached today), building the item, and the rest of `outcomes`. What the flat form moves out of the loop, and today's Python pays inside it: the label of each mod (a dict lookup), the weight times the fossil factor, and the `PoolMod` and `PoolFamily` objects. That is the point of the flat form, and it is why plain Python on it is already 14 to 17 times faster.

Not built: Rust with PyO3. For this loop (64-bit integers, sorting, a hash table) it would do what the C of Cython does; its case is exact big integers inside compiled code (section 5), which this loop does not need.

## 3. The loop: pools a second per candidate

Heavy runs 43462096163 (Linux, Python 3.14.4) and 43463173614 (Windows, Python 3.14.10), jobs 1 and 2, `bench_kernels.py`; both runners have 4 cores. (Both runs are marked failed on GitHub: their jobs 3 and 4 were the first try of the whole-plan build of section 4, which runs 43465798966 and 43465836850 repeat.) Today's Python is timed once, inside the plan; each candidate is the best of 5 repeats on warm tables.

| Case, system | Today's Python | Flat tables, plain Python | Numba | Cython |
|---|---|---|---|---|
| R04, Linux | 3,993 | 68,464 (17.1×) | 416,501 (104×) | 489,693 (123×) |
| R04, Windows | 3,279 | 46,849 (14.3×) | 380,624 (116×) | 463,467 (141×) |
| essences/medium, Linux | 4,181 | 57,769 (13.8×) | 429,013 (103×) | 499,796 (120×) |
| essences/medium, Windows | 3,760 | 54,132 (14.4×) | 435,956 (116×) | 436,280 (116×) |

Same split as today's signatures: yes in all twelve cells (6,508 distinct signatures on R04's pools, 1,307 on essences/medium's). Numba's first call took 2.7 to 3.2 s to compile; the figures are after it.

## 4. A whole plan

**The loop's share of a plan.** In the instrumented run the `group_pool` calls that feed a signature are 30% of `_outcomes` (the kept pools' own `group_pool` seconds, scaled to all 393,479 signatures: 37 s of 124 s) and `_pool_signature` is 84% of `_signatures_of` (R04; 36% and 83% on essences/medium). Applied to the stage table of section 1: 59 s of R04's 303 s (19.5%) and 18 s of essences/medium's 85 s (21%). This share is derived from two runs with different instrumentation, not read from one. R04 makes 514,260 `group_pool` calls for 393,479 signatures: the other 120,000 are a second, plain pool that `_check_type_blind` builds and compares with the action's for an item whose fractured mod is known only by its family type; they are outside the span (and are a cost #827 can drop).

**Computed whole-plan speed-up from the loop alone** (the rest of the plan unchanged; arithmetic on the share above, no plan was run with a candidate inside it): with the loop 17 times faster (flat Python) 1.22; 104 times (Numba) 1.24; 123 times (Cython) 1.24, on R04; 1.24 to 1.26 on essences/medium. A plan of R04 would go from about 305 s to about 250 s on the Linux runner.

**Measured whole plan, the package compiled by Cython as it is** (heavy runs 43465798966 and 43465836850; each row is one runner, the source first, then the compiled copy):

| Case, system | Source | Compiled copy | Ratio | Means equal |
|---|---|---|---|---|
| R04, Linux | 358.3 s | 375.7 s | 0.95 | yes, to the last digit |
| essences/medium, Linux | 123.3 s | 128.0 s | 0.96 | yes |
| R04, Windows | 732.5 s | 751.4 s | 0.97 | yes |
| essences/medium, Windows | 112.5 s | 116.4 s | 0.97 | yes |

The compiled copy is never faster; a 3 to 5% loss is inside what two runs on one runner can differ by, so the honest reading is "no gain". The build took 11 to 18 minutes a runner. Of 164 modules, 143 compiled; a plan loads 225 modules, 136 of them compiled. What did not:

- `abstraction/_kernel.py`, the module this ticket is about, crashes the Cython 3.3.1 compiler (a generator expression inside a conditional `for`, line 1935);
- 19 modules of `solver`, `cli` and `data` use the generic syntax of Python 3.12 (`class Outcome[S]`, `def f[S]`), which Cython does not read;
- `rules/registry.py` compiled but behaved differently (its YAML loader subclass returned no mapping), so the build put it back to its source. The build tries the copy on R13 and reverts any module an error comes from.

So the object-heavy modules that did compile (the items, the actions, the pools, the states: where `_item_of` and `_outcomes` spend their 44% of R04) do not get faster by being compiled as they are: the interpreter's loop is not their cost, the objects are. What this does not show is the kernel module and the search compiled, since neither could be.

**The bound on any compiled generator.** If the key path took no time at all, R04 would run 3.0 times faster (303 s to 100 s) and essences/medium 2.04 times (85 s to 42 s); with the kernel building free as well, 3.7 and 2.6 times. That is the ceiling, not a forecast: the 2 times the owner asks for is inside it only if nearly the whole key path goes, not one loop of it.

## 5. Exactness

- **The signature loop is exact by construction.** It reads no number: labels and weights are ids given by equality, and an id is found by comparing the whole content. The check of section 2 passed on every pool on both systems.
- **Integer weights need big integers.** The weights of a kernel, after `integer_weights` puts its chances on one denominator:

| Bits of the largest weight | R04 (220,710 kernels) | essences/medium (31,677 kernels) |
|---|---|---|
| up to 53 (a float holds them exactly) | 220,576 | 31,625 |
| 54 to 127 | 0 | 0 |
| 128 to 255 | 31 | 0 |
| 256 to 1,023 | 76 | 52 |
| above 1,023 | 27 (the largest 1,595) | 0 (the largest 449) |

  64-bit integers reproduce 99.94% and 99.84% of the kernels, and 128-bit integers not one more. A compiled kernel builder on fixed-width integers would be wrong on 134 and 52 kernels unless it detects the overflow and hands those to arbitrary-precision integers (Python's own, or a big-integer library in the compiled code). The largest weights here have 481 digits; the 4,300-digit crash of #868 did not occur on these two cases. The exact draws themselves stay small (denominators up to 169 and 186 bits, numerators up to 255): where between the draw and the kernel the integers grow I did not trace; #868 asks for that.
- **Floats hold the draws to the solver's tolerance.** Every `exact_distribution` call of both plans (9,018 and 4,624 calls; 116,431 and 74,945 chances) was run again in the planner's own float mode (`actions.draw.floating`). The largest relative error of a chance is 4.5e-16 and 4.6e-16, the same on Linux and Windows; the chances of a draw sum to 1 within 1.1e-16; the outcomes are the same sets. The solver works in float64 with a tolerance of 1e-10. In Python the float mode is 2.4 to 2.7 times faster on the same calls (R04, Linux: 6.4 s against 2.3 s). This is a Python measurement: no compiled float draw was built, and the draw is 2 to 5% of a plan.
- **What floats would change.** A kernel is stored as integers with no common factor, and the search shares kernels by key and checks a share by comparing those integers exactly (`Search._fresh_equal`); the solver lumps states with equal kernels exactly. Float kernels would give the same values to the tolerance but not the same equalities. I did not run a whole plan on float kernels.
- **The compiled package** gave the same mean as the source to the last digit on all four runs.

## 6. What in today's data model stands in the way

1. **The kernel of an action is whatever its Python code returns for an item object.** `Reads` and `Adds` (`actions/contract.py`) declare what an action looks at and what it puts on the item; they are read by the planner to choose kinds and to prune, and they are checked by the contract suite, but they cannot be *executed*: the only way to get a kernel, or even its key, is to build a validated `Item` from the state (`_item_of`: a representative mod for every slot, then the item's own checks) and call `action.outcomes` on it. The planner names 33 kinds of action it can use (the list in its own refusal message, as recorded in `tests/fixtures/family_bench/baseline-main.json`). A compiled generator needs, per kind, the rule as data over flat tables. That is a second implementation of every action, to be kept equal to the first.
2. **States and keys are objects.** A `CompressedState` is a frozen dataclass of tuples of `Slot` dataclasses holding enums and strings; a key is a `frozenset` of nested tuples of them and of `Fraction`s; kernels are `dict[CompressedState, Fraction]`. Hashing and comparing them is cheap per object and adds up (hashes are cached on the objects already). A compiled loop needs states as rows of integers and an intern table, which is the flat state of the original research (`2026-10-30-4-solver-engineering.md`: flat arrays, kernels from integer weights) that ADR-0010 put off.
3. **Weights are `Fraction`s used as identities.** Family types and signatures sort and compare tuples that hold `Fraction` weights (77.6 million `Fraction.__eq__` calls on R04). The weights of one pool table are a few distinct values (6 on R04's pools, 3 on essences/medium's): as ids in a table they cost nothing to compare.
4. **Big integers** (section 5): any compiled kernel *builder* needs an exact fallback. The key path does not.
5. **The cache is per state.** The prepared pair is keyed by the slots of the state the action is given (all of them unless it erases the ordinary mods) and dropped after each state, so the work of section 1 is repeated for states that differ in something the action never reads. This is ticket #827's root (C1 of #812), and it is independent of the language.

## 7. Recommended design

**Do not build a compiled kernel generator now.** The candidates measured on the loop give a computed 1.2 times on a whole plan, the cheap one (compile as it is) gave nothing where it compiled, and the part that would give more is a second implementation of every action.

**Do #827 first, on flat tables, with the seam in place.** #827 is already cut for this root ("a `kernel_key` that never calls `action.outcomes`; the cache keyed by the projection of what the action reads"). This note adds how to build it so that the compiler stays an option:

- **Per action and item context, one table made once:** the candidates with their family, side, weight id, label id and guaranteed flag, and the type of each family (the mods of a family leave the pool together, so within one table a family's type does not depend on the state; an Attack or Caster metamod on the item filters mods by tag, so each set of blocked tags is its own table). Made by today's Python (`pool_candidates`, `_label`), so the game's rules stay where they are.
- **Per state:** which families the item's mods block, the free slots, the mods kept. The signature is the head plus the types of the families left: a count per type, changed only at the blocked families, so the work follows the mods on the item (at most 6), not the 100 to 120 candidates.
- **The seam:** one function, "table, blocked families, head in; signature id out", with its intern tables. Everything above it stays Python (actions, items, the rules registry, the search, the report); the kernel builder, `integer_weights` and the exact draw stay Python and exact (they are 7 to 11% of a plan).
- **Accept it as #827 says** (the generated family of #824; equal kernels on every sampled pair), and measure R04 and essences/medium again with `research/881/profile_plan.py`.

Expected whole-plan effect: computed, 1.22 to 1.24 from the pool loop alone in flat Python. If #827 removes most of the key path, the ceiling is 3.0 (R04) and 2.04 (essences/medium); an estimate from the flat-Python factor of 14 to 17 applied to the whole key path is about 2.7 on R04 and 1.9 on essences/medium. That estimate is an extrapolation: only the pool loop was prototyped.

**Then, only if the profile still shows the loop behind the seam at a fifth of a plan or more, compile that one function.** Between the two candidates the speed is the same within 20%; the difference is how they ship:

| | Numba | Cython (or Rust with PyO3) |
|---|---|---|
| Build | none: `pip install numba` on Windows and Linux; the loop compiles at its first call (2.7 to 3.2 s measured; cached on disk after) | a C (or Rust) compiler at build time; wheels built in CI for Linux and Windows, or the server's image builds its own |
| On the website | a service compiles once at start | a wheel in the image |
| On a developer's Windows PC | works as installed | needs the wheel, or MSVC (the owner's PC has it) |
| Cost | a large dependency (llvmlite), and it follows new Python versions with a delay (0.68.1 ran on Python 3.14.10 here) | a build pipeline to own; the compiled copy must be tested against the Python one |
| Exact big integers in compiled code | no | Cython through Python integers (slow), Rust through a big-integer library |

My pick for one integer loop is **Numba, with the plain-Python function kept as the fallback and as the oracle** (ADR-0010 already names numba for hot loops a profile has found; the solver uses numpy): no build to own, the same on both systems, and the fallback keeps the planner installable without it. Rust or Cython becomes the right tool only if a later profile puts exact big-integer work (the kernel builder, the exact draw) on top, and today it is 7 to 11% of a plan.

## 8. Size of the real change, in tickets

- **Recommended path:** #827 as cut (one ticket, already `ready-for-agent`), built on the flat tables above; then a re-measurement inside its PR. If the loop still matters: **2 tickets** (the compiled function behind the seam with its fallback and an equality test on generated pools on Windows and Linux; then the switch with R04 and the generated family measured again).
- **A full compiled kernel generator** (state, key and kernel compiled, the original research's design): **6 to 8 tickets**: the flat state and its intern table (1); the actions as table rules, by family of kinds in scope B1 to B3 (draws and rerolls; fixed results such as bench crafts, Annulment and the Fracturing Orb; essences, fossils and Harvest: 3); the kernel builder with exact integers and an overflow fallback (1); the exact draw (1); build and shipping on both systems (1); a parity suite against the Python actions on the generated family (1). Each action kind added later would be written twice. I do not recommend it on these numbers.

## 9. What was not measured

- A compiled form of the whole key path (the item, the outcomes, the split): it needs the flat model, so its gain is extrapolated from one loop.
- Rust with PyO3: not built; Cython stands for the ahead-of-time option.
- A compiled kernel builder or exact draw, in fixed-width or exact rationals; a whole plan on float kernels.
- Cython on `abstraction/_kernel.py` (compiler crash) and on the 19 modules with the newer syntax: the "as it is" figure covers 136 of 225 loaded modules.
- **Kernels a second for a candidate.** No candidate builds a kernel or its whole key: the candidates are measured in pools a second on one loop, and their whole-plan effect is computed from the loop's share, not run.
- The equality check covers the pools of two kinds of action (`ApplyEssence`, `ExaltedOrb`), all without a guaranteed tag, a fossil factor or lucky rolls, and no family on both sides: the guaranteed flag of the sort key was never set, and the other kinds of the two plans (`AnnulmentOrb`, `FracturingOrb`, bench crafts) draw from no pool.
- The baseline is not symmetric: today's Python is one pass inside the plan, the candidates the best of 5 on warm tables; making the flat tables (per action and item context) is not timed, and the number of contexts is not reported.
- Two cases only (R04 and essences/medium), three plain runs each per system; runners differ by 20 to 65%. Linux ran Python 3.14.4, Windows 3.14.10. The profiler's table is from the Linux runner only.
- The loop's share of a plan (19.5% and 21%) is derived from two instrumented runs; the keeping of a pool runs inside the `_signatures_of` stopwatch of the instrumented run, which makes the signature's part of it look smaller than it is.
- The flat-Python and compiled loops were given the candidates left after the item's blocks; finding the blocked families from a flat state is argued (at most 6 mods), not measured.

## Files

- `research/881/profile_plan.py`: one plan, plain, with stage stopwatches, or under cProfile. `research/881/bench_kernels.py`: the plan with its pools kept, then the candidates on them. `flat_python.py`, `flat_numba.py`, `flat_cython.pyx`: the loop. `build_cython.py`: the Cython builds. `run_job.sh`: the four jobs of a measurement run. `profile_groups.py`: the profiler's seconds by kind of work. `profile_jobs.txt`, `profile_jobs_windows.txt`: the argument lines of the profile runs.
- `research/881/results/`: the JSON of every run quoted here (`prof-*`: runs 43457009372 and 43457044188; `bench-*`: 43462096163 and 43463173614; `whole-*`: 43465798966 and 43465836850), with the runners' own folders cut from the paths, and in the four `compiled.json` the compiler's message for `abstraction/_kernel.py` written by hand (the runs kept only the end of its traceback; the crash was reproduced locally with the same Cython).
- To repeat sections 3 to 5: `python .github/scripts/heavy_dispatch.py run --no-wait [--os windows-latest] --ref <branch> --runners 4 --command 'bash research/881/run_job.sh $RUNNER_INDEX'`. Section 1: the same with `--runners 6` (Linux) or `--runners 4` and `profile_jobs_windows.txt` (Windows) and `--command 'uv run --no-sync python -u research/881/profile_plan.py $(sed -n "${RUNNER_INDEX}p" research/881/profile_jobs.txt) --out $OUT_DIR'`.
- Open points filed: on #827 (build it on flat tables behind one seam function; the second pool of `_check_type_blind`), on #868 (the counts of kernels past 64 bits on these two cases).
