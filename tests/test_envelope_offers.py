"""#1337: a node's offers not realized yet are held compact (`_envelope.Offers`) and give the same entries in the same order as the list of
(la, position) tuples they replaced, under every operation the search makes on them."""

import bisect
import random

import numpy as np

from crafting_system.planner._envelope import SLACK, Offers, Search, _sorted_arrays


class _ListOffers:
    """The list the search held before #1337, the least `la` last, with the operations it made on it."""

    def __init__(self, entries):
        listed = sorted(entries, key=lambda c: (c[0], c[1]), reverse=True)
        self.items = [(la * (1.0 - SLACK), position) for la, position in listed]

    def __len__(self):
        return len(self.items)

    def tail(self, count):
        return list(reversed(self.items[-count:])) if count else []

    def least(self):
        return self.items[-1][0]

    def last(self):
        return self.items[-1]

    def pop(self):
        return self.items.pop()

    def take(self, position):
        held = [c for c in self.items if c[1] == position]
        if not held:
            return None
        self.items.remove(held[0])
        return held[0]

    def insort(self, entry):
        bisect.insort(self.items, entry, key=lambda c: -c[0])


def _entries(rng, count):
    # few distinct values, so that ties are many; some differ by an ulp, which the slack can make equal
    values = [rng.choice([0.5, 1.0, 1.0 + 2**-52, 2.0, 3.0, float("inf")]) for _ in range(count)]
    positions = rng.sample(range(10 * count), count)
    return list(zip(values, positions))


def test_the_compact_offers_give_the_lists_entries_in_its_order_under_every_operation():
    rng = random.Random(1337)
    for trial in range(300):
        entries = _entries(rng, rng.randint(0, 40))
        own = [e for e in entries if rng.random() < 0.4]
        rest = [e for e in entries if e not in own]
        reference = _ListOffers(entries)
        offers = Offers(_sorted_arrays(own), _sorted_arrays(rest) if rest else None)
        taken: list[tuple[float, int]] = []
        for _ in range(80):
            assert len(offers) == len(reference) and bool(offers) == bool(reference)
            if not reference.items:
                if taken:
                    entry = taken.pop(rng.randrange(len(taken)))
                    reference.insort(entry)
                    offers.insort(entry)
                    continue
                break
            assert offers.least() == reference.least() and offers.last() == reference.last()
            count = rng.randint(1, 5)
            assert offers.tail(count) == reference.tail(count), trial
            move = rng.random()
            if move < 0.4:
                got = reference.pop()
                assert offers.pop() == got
                taken.append(got)
            elif move < 0.6:
                position = rng.choice([p for _, p in reference.items] + [None, -1])
                got = reference.take(position)
                assert offers.take(position) == got
                if got is not None:
                    taken.append(got)
            elif taken:
                entry = taken.pop(rng.randrange(len(taken)))
                if rng.random() < 0.5:  # raised, as `tighten` raises an offer and puts it back
                    entry = (entry[0] * 1.5 + 0.25, entry[1])
                reference.insort(entry)
                offers.insort(entry)
        while reference.items:
            assert offers.pop() == reference.pop()
        assert not offers


def test_nodes_that_list_the_same_shared_offers_hold_one_copy_of_them():
    search = Search.__new__(Search)
    search.bases = {}
    rest = [(2.0, 5), (1.0, 7), (3.0, 1)]
    first = search.intern_offers(rest)
    second = search.intern_offers(list(reversed(rest)))
    assert first[0] is second[0] and first[1] is second[1]
    assert first[0].tolist() == [3.0, 2.0, 1.0] and first[1].tolist() == [1, 5, 7]
    assert not first[0].flags.writeable
    other = search.intern_offers([(2.0, 5), (1.0, 8)])
    assert other[0] is not first[0] and len(search.bases) == 2
    assert np.array_equal(other[1], [5, 8])
