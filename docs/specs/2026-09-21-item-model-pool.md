# Spec: bounded ordinary item model and PoB mod-pool resolver

Worktree: `.worktrees/item-model-pool` (branch `w-item-model-pool`).

You may touch ONLY:
`src/craftoracle/item_model.py`, `tests/test_item_model.py`; acceptance correction also permits
`pytest.ini` and `.gitignore` solely to keep pytest temporary directories under `.pytest_tmp/`.

## Why

The night goal needs a real ordinary helmet pool for the vertical slice. Implement the small
state and pool boundary used by later workers. This is a data-driven resolver, not a complete
Path of Exile item simulator.

## Sources and fixed provisional decisions

- `data/pob_bases.json` is the accepted literal projection of S27 base data.
- `data/pob_mod_families.json` is the accepted literal projection of S24/S25/S59-S62. Use only
  records whose `source_path` ends with `ModExplicit.lua`; do not treat veiled, corrupted,
  eldritch, Delve or synthesis rows as ordinary explicit candidates.
- `docs/mechanics/pool_resolution.md`, `docs/mechanics/affix_generation.md`, and GOAL's
  `lead-provisional 2026-09-20` decisions are the rule contract. Use PoB `group` literally for
  exclusion, first matching base tag in ordered `weightKey`/`weightVal`, and no generated tags
  or weight multipliers.
- Out-of-slice flags are Q9: corrupted, influenced, fractured, synthesised, mirrored or split.
  They must raise exactly `NotImplementedError("out of tonight's slice: Q9")` when a pool is
  requested. Do not infer eligibility.

## Required API

Implement plain dataclasses and small pure functions (no framework):

```python
@dataclass(frozen=True)
class ModRef:
    id: str
    type: str                 # Prefix or Suffix
    group: str

@dataclass(frozen=True)
class ItemState:
    base_name: str
    item_level: int
    rarity: str               # normal, magic, rare
    mods: tuple[ModRef, ...] = ()
    corrupted: bool = False
    influenced: bool = False
    fractured: bool = False
    synthesised: bool = False
    mirrored: bool = False
    split: bool = False

@dataclass(frozen=True)
class PoolEntry:
    mod_id: str
    type: str
    group: str
    weight: int
    level: int

def load_item_data(base_json: Path, mods_json: Path) -> tuple[dict[str, dict], dict[str, dict]]
def resolve_pool(item: ItemState, base_rows: dict[str, dict], mod_rows: dict[str, dict],
                 side: str | None = None) -> tuple[PoolEntry, ...]
def pool_totals(... ) -> dict[str, int]
```

`load_item_data` must reject duplicate source occurrences and duplicate explicit IDs.
Repeated base names are already documented in D9: use `name@source.path:source.line` keys
for every base, and a plain-name alias only when that name occurs once. An ambiguous plain
name must raise ValueError, never silently select one. Only true-valued base tags are active. `resolve_pool`
must preserve source order, return only positive-weight eligible rows, and accept `side=None`
for both sides or `Prefix`/`Suffix` for one side. A base tag weight is the value at the first
key present in the base's `tags`; if no key matches, weight is zero. Eligibility is:

1. explicit source row, level <= item level;
2. requested side and available side slots (normal has no explicit pool; magic max 1 per side;
   rare max 3 per side);
3. no existing `ModRef.group` match;
4. positive resolved weight.

Keep a deterministic source order and do not collapse equal groups. Unknown base or mod IDs,
invalid rarity/side or malformed required row data raise `ValueError` with a useful message.
An item with an out-of-slice flag raises the exact Q9 error before reading pools.

## Numbers a test must reproduce

For `Royal Burgonet` (tags include armour, helmet, str_armour, default, item level 86) and the
accepted explicit projection:

- `IncreasedLife9` resolves to Prefix weight 1000; `IncreasedLife10` and `IncreasedLife11`
  resolve to weight 0 because their first matching key is default (the helmet has neither shield nor body_armour).
- `ChaosResist6`, `FireResist8`, `ColdResist8`, `LightningResist8`, and `Strength8` resolve
  to Suffix weights 250, 1000, 1000, 1000, and 1000 respectively.
- An empty rare has 41 positive prefix entries totaling 39275 and 84 positive suffix entries
  totaling 78400. These totals are checks of the provisional first-match/group/level rule,
  not game-wide probability claims.
- With existing `IncreasedLife9`, prefix pool excludes group `IncreasedLife`; with existing
  `ChaosResist6`, suffix pool excludes group `ChaosResistance`.
- With an existing two-prefix rare, a third prefix may still be added; with three prefixes none may be added; with an existing one-prefix
  magic, prefix entries are empty. An existing 3-prefix rare still yields suffixes.
- All six Q9 flags raise the exact error. Magic and rare are accepted; normal has no explicit
  side capacity and is the initial state for Transmutation/Alchemy; those actions change rarity before pool resolution.
- Further item-level 86 totals (Prefix/Suffix): Iron Ring 60250/103600; Simple Robe
  61000/58200; Iron Gauntlets 46000/77000; Crude Bow 54658/59100.
- FireResist7 and ColdResist7: 1000 each on Royal Burgonet. These complete ten single-mod checks.
- Snapshot tests use committed own JSON; do not copy raw snapshots or execute older builder tests
  in this worktree. Full regression runs happen on main after merge.

## Tests and report

Write tests first for the API, all numbers above, first-match zero behavior, level gate, group
exclusion, side caps, malformed input, ordering, and all Q9 flags. Do not add tests for blocked
families. Run `python -m pytest -q tests/test_item_model.py` and report the exact line. Commit
only the two allowed files. Final report begins `=== FINAL REPORT ===` and includes commits,
tests, each number above, files, and QUESTIONS FOR THE LEAD.

## Acceptance correction 1
Reject forged ModRef side/group, duplicate existing groups/IDs, over-cap/normal-with-mods
states, bool/nonpositive item levels, bool/negative weights. Add input regression tests and
source pointers in module/tests. Configure pytest --basetemp=.pytest_tmp and ignore that path;
no tests may create fixtures outside crafting. Lead's first focused run:16 passed.
