"""The fossil sets without a Bloodstained Fossil answer exactly as they did before it was lifted from `OutOfScopeError` (ticket #261).

"Existing fossil kernels are byte-identical." `fossil_digest` writes down, in a fixed text, everything a set answers (labels,
resources, declarations, twin keys, refusals, every component of the outcomes with its exact pool) and hashes it:

* `digest()`: 319 (item, set) pairs of the small fossil test world, with the claims, the exact distributions, the chances and the
  kernel of the compressed state. `EXPECTED` was computed with the same function on the source of `main` without the ticket (`origin/main` at
  bc0d98d, 2026-11-01). It moved once while the ticket was open (7f1c4c29...) because another
  merged ticket changed a claim an ordinary set names; `main`'s own source gave the new value and so does the ticket's.
* `real_digest()`: 22 sets on an empty Sorcerer Boots and an empty Iron Ring of the real 3.29.3.3 dump (the Tangled, Glyphic,
  Hollow, Fractured, Sanctified, Opulent, Faceted and Gilded Fossils among them), components and pools only. It needs the cached dump
  and skips without it. `REAL_EXPECTED` was computed on the source of `main` just before this change; a new data pin moves it.

Both moved once with ticket #484, and only because the text writes the items: an `ExplicitMod` has no `tier` field any more and an item
carries the implicits of its base. No pool, weight, chance or kernel changed; the values before were 320bde1c... and 27f9ecdf....

Neither moves unless an ordinary fossil set changes. If one fails after a deliberate change, work the new value out with
`python tests/fossil_digest.py` and say in the ticket why the answer of an ordinary set moved.
"""

from abstraction_support import real_game_data
from fossil_digest import digest, real_digest

EXPECTED = "27f035e9794b130db1785278064f137af2da332c7ee788e3cceb2db380754f88"
PAIRS = 319
REAL_EXPECTED = "466e83b64d5935ee8826e6c1488c7d7fe2be4bd566e2e37431c093a00269e305"
REAL_PAIRS = 44


def test_the_answers_of_the_sets_without_a_bloodstained_fossil_are_unchanged():
    found, pairs = digest()

    assert pairs == PAIRS
    assert found == EXPECTED


def test_the_answers_of_the_real_sets_without_a_bloodstained_fossil_are_unchanged():
    found, pairs = real_digest(real_game_data())

    assert pairs == REAL_PAIRS
    assert found == REAL_EXPECTED
