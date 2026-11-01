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

Neither moves unless an ordinary fossil set changes. If one fails after a deliberate change, work the new value out with
`python tests/fossil_digest.py` and say in the ticket why the answer of an ordinary set moved.
"""

from abstraction_support import real_game_data
from fossil_digest import digest, real_digest

EXPECTED = "320bde1cfcd37649b6dfb03fb282a4187aad2d5deee7cb80ea21146b30724c71"
PAIRS = 319
REAL_EXPECTED = "27f9ecdf88b56413595ea03343033f3aff60673f33d16e2a6db433a1aa40b26d"
REAL_PAIRS = 44


def test_the_answers_of_the_sets_without_a_bloodstained_fossil_are_unchanged():
    found, pairs = digest()

    assert pairs == PAIRS
    assert found == EXPECTED


def test_the_answers_of_the_real_sets_without_a_bloodstained_fossil_are_unchanged():
    found, pairs = real_digest(real_game_data())

    assert pairs == REAL_PAIRS
    assert found == REAL_EXPECTED
