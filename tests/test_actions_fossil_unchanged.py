"""The fossil sets without a Bloodstained Fossil answer exactly as they did before it was lifted from `OutOfScopeError` (ticket #261).

"Existing fossil kernels are byte-identical." `fossil_digest.digest()` writes down, in a fixed text, everything 319 (item, set) pairs
of the fossil test world answer (labels, resources, declarations, twin keys, claims, refusals, every component of the outcomes with
its exact pool, the distributions, the chances, and the kernel of the compressed state) and hashes it. `EXPECTED` was computed on the
code of `main` before the ticket (commit d511a32), with the same function; it does not move unless an ordinary fossil set changes.

If this test fails after a deliberate change to the fossil sets, work the new value out with `python tests/fossil_digest.py` and say in
the ticket why the answer of an ordinary set moved.
"""

from fossil_digest import digest

EXPECTED = "7f1c4c2958ffc3a7bf84a2670a27801af6fb52c45e4ec3e9638530be46a24e93"
PAIRS = 319


def test_the_answers_of_the_sets_without_a_bloodstained_fossil_are_unchanged():
    found, pairs = digest()

    assert pairs == PAIRS
    assert found == EXPECTED
