# State — 2026-09-21

## Current progress (night goal active; not DONE)

1. Phase 0 remains accepted; ordinary PoE 3.29 target is confirmed.
2. GOAL.md now requires the working helmet planner plus stretch work; this goal is active.
3. Ordinary item/pool model is merged (d07a1b5), 21 focused tests passed.
4. Exact grouped distributions are merged (4ee0641), 17 focused tests passed.
5. Royal Burgonet86 has 41 eligible prefixes / 84 suffixes, weights39275/78400.
6. Model Chaos target chance is0.0000242820884551; Deafening Envy0.00259406068444.
7. Ordinary actions (51b386f,15 tests) and exact loop costs (8eeee53,13 tests) are merged.
8. MC and input workers are running; policy evaluator and direct CLI remain next.
9. Source uncertainties are provisionally bounded by GOAL/D14; blocked special families stay out.
10. The required plan command does not exist yet; do not claim the morning demo is complete.

## Working commands / evidence

- `python -m pytest -q tests/test_item_model.py`:21 passed on accepted branch.
- `python -m pytest -q tests/test_distributions.py`:17 passed on accepted branch.
- `python -m pytest -q tests/test_actions.py`:15 passed on accepted branch.
- `python -m pytest -q tests/test_costs.py`:13 passed on accepted branch.
- Existing Phase0 suite was78 tests; full combined suite will be run after integration.
- Exact six-draw helmet distribution:14 classes,mass0.9999999999999984,target0.0000535457934229.
- Exact mixture count4/5/6 weights8/3/1:Chaos p0.000024282088455126466; Envy
  p0.0025940606844434217; suffix preparation p0.05567530208498237; final life slam1000/39275.
  These are predictions under the declared provisional model, not independent game measurements.

The exact DP retains group-removal state internally and projects to labelled terminal classes
only after the whole draw schedule. It does not turn junk into a reusable aggregate weight.
Outcome classes must not be reused for arbitrary transitions requiring lost group identities.

## Implementation and evidence boundaries

See docs/GOAL.md, D14/D15 and docs/design/night-policies.md. Prices are invented caller inputs;
rare count assumptions and PoB group/first-match weights will be printed on every plan.
Generated tags and multipliers are deliberately omitted per the owner's provisional decision.
No third-party code/data copied into src/data. Existing own projections and cached source
acceptance remain in SOURCES, WORKERS and research/phase0-coverage.md (62 sources/20 sheets).
No new fact sheets or broad research tonight; no record-by-record re-verification.

The first nightly focused acceptance inherited pytest's default temporary-directory setting.
It has now been corrected: pytest.ini sets --basetemp=.pytest_tmp and that repository-local
path is ignored. All subsequent fixture runs must use that setting; no external cleanup/read.

## Workers / current work

At most two workers: monte-carlo and plan-inputs, each in its own ignored worktree. Their
25-minute budgets cover independent sampling validation and strict input fixtures; no individual
command may exceed10minutes. Item-model, exact-distributions, actions and cost trees were accepted
and removed without force. Initial item worker's service429 retry succeeded; no duplicate worker
was launched. Dependent policy and CLI work waits for merged APIs.

Prepared specs: ordinary-actions, monte-carlo, loop-costs, plan-inputs, policy-evaluation, plan-cli.
All are bounded and include acceptance numbers. Work continues through DONE and unblocked stretch;
completion of one task is not a stopping condition. Corrections capped at two per task.

## Next three actions

1. Accept independent Monte Carlo on five real pools and cost p90 estimation.
2. Accept validated item/price/loadout inputs and delegate the policy evaluator.
3. Evaluate the designed real policies, wire direct module CLI, validate the helmet and bow,
   then execute the stretch list; record final ten-line morning summary and full-suite timing.

## Night log

- 00:05 — read GOAL and rules; item-model spec prepared, worker launch next.
- 08:18 CEST — item model merged d07a1b5; exact DP in progress; goal/demo incomplete.
- 08:28 CEST — exact DP merged4ee0641; actions/costs running; all downstream specs prepared.
