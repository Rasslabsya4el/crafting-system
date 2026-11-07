"""An independent naive crafter: plays a guide's route on concrete items and counts what it costs (ticket #555, audit TESTS-22 part 2).

Why it exists. Every cost of a given route today comes from `risk.evaluate` on the planner's own outcomes, so a wrong outcome rule makes the
guide's cost wrong in the same way and "the planner is not dearer than the guide" still passes. This package plays the same route by
Monte Carlo with rules written from the published mechanics and imports nothing of the planner.

It reads, and only this:
  * the raw repoe-fork export of the pinned version, `<CRAFTING_CACHE_DIR>/repoe-fork/<version>/`;
  * the target file (base, item level, requirements, start item) and the guide's route file (`examples/routes/`);
  * the price file, and the hand-written table of start price keys `tests/reconcile/expected_keys.txt`;
  * the owner's rules (`docs/owner-rules.md`), written below as code where they apply (OR-1, OR-2, OR-4 are the goal oracle's).

It imports the standard library, `yaml`, the two shared modules `independent.ladder` and `independent.export`, and the goal oracle
`oracle.goal_oracle` (which judges whether a mod meets a line of the target, and which imports nothing of the planner either).
`test_naive_independence.py` scans every file here for anything else.

The mechanics are the plain spam of the guides: Orbs of Transmutation, Alteration, Augmentation, Regal and Chaos, essences, and a bench craft
of one fixed mod. Each rule they read has its source, URL, quote and date in `rules.py` (OR-22). A route that needs another mechanic is
refused with a message that names it (`Unsupported`): the test file lists those routes.

Modules: `rules.py` (the cited rules), `craft.py` (items and the uses of the orbs), `world.py` (the files and the actions a route names),
`play.py` (the route and one play), `tally.py` (many plays, the mean and its standard error, the verdict), `frequencies.py` (one orb on
one item, counted, for the comparison with Craft of Exile's recorded counts), `__main__.py` (the command for a long simulation on a runner).
"""
