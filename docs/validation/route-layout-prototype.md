# Layout and original modifier text acceptance — 2026-09-21

Scope: owner-approved work on DESIGN PROPOSALS, no crafting recalculation. Recipe and
saved numbers are in docs/design/route-layout-proposals.md. Owner selection pendingQ31.

PRODUCT REVIEW: owner rejected the initial A/B/C layout after these technical checks.
The passing checks below do NOT mean accepted usability. D27 replaces this interface.

## Prototype cd8df6c

Worker commits83f517d,ee738db,6340fbe, Terra/high. Lead read whole initial and correction
diffs; independently extracted inline script and passed it to `node --check`.
4 actions;10 states; every state6 slots.0 external resources. All three modes dark,
one-decimal display, original English modifier text. Complete source labels retained.

Browser acceptance on localhost, lead:
- A: four cards; desired preparation state shown first; six slots each; early-finish
  button reveals a finished card. Fresh-base example collapsed.
- B: SVG arrows legible and connected; Scour node click and Exalt node Enter update
  detail. Envy retry, direct finish, preparation and three-miss return visible.
- C: preparation -> bench -> Scour -> Exalt. Success at Exalt1/2/3 finishes in the
  correct prefix slot and preserves prior arbitrary prefixes. Three misses show full
  prefixes and only return to Envy, not an impossible prefix bench. Envy repeat and
  direct finish work; reset/history work.
- Mobile viewport390px: each mode document/client width375px; no page overflow.
  Temporary viewport override reset. Browser script errors0.
- Whole-route evidence explicitly unvalidated; same-base3 component cases named;
  global12 cases/5 bases in a closed disclosure. Historical proof not rerun.

## English labels 9b0ab99

Worker285cc34, Luna/medium. Lead read full3-line production diff and ran:
`python -m pytest -q tests/test_report.py tests/test_report_template.py` ->13 passed
in under0.1minute.2 route title locations and1 helper changed; no game logic changed.
Expected helper output:`Life T1 (+(130-144) to maximum Life)`, fallback:`Life T1`.
Route title:`Fractured Life T1 → Envy`.

Saved report HTML refreshed with `build_report`/`render_report` from each existing
plan, embedded context and copied proof.12 helmet and14 bow routes. All route fields
except title/search_text/instructions compared equal before/after. Existing plan bytes
unchanged, SHA256:
- helmet:e0a9c7ca0bea9251707bf25ef283397bd2d6554f913e8b030e43e34a73271f4f
- bow:91bcf97c00ebceeeaa15e3167b5adbfeaa35790262126823cebea440d02e27da

Historical423-test/12-CoE proof is still evidence for02bceff calculations, not a new
full run for these presentation commits.0 crafting runs in this session.

## Replacement D27 direct flow

Worker66a8c4c,9723cef,bab7b7d; lead0e4491d explicitly says minimum2 free prefixes,
preserving both zero-prefix and one-prefix passing inputs. Full final HTML read by
lead. Python HTML parser accepted;3 steps,4 actions,2 item cards,12 slot rows,
1 closed disclosure,0 scripts/tabs. No generic preparation/state-search labels.
No before/after pairs. Mod names/stat text English; explanation Russian.

Lead browser:desktop screenshot inspected; pass link1->2,2->3 and full-prefix reset
3->1 verified from actual URL hashes.390px viewport:client/scroll width375/375,
no document overflow; viewport reset.0 browser script errors. Final owner tab reloaded
with minimum2-open-prefix wording. Temporary server stopped, worktree removed.
Technical acceptance only: owner readability reviewQ31 remains pending.
