"""What a patch touches in this repo: the targets, routes, claims and tests that name a changed id.

`compute_impact(old, new, root)` compares two `GameData` (as `diff` does) and looks in the files of
the repo at `root` for what they name: the mods, families, base items, essences and fossils that
changed, and the mods the changed bench options, essences and fossils hand out. `render_impact`
turns the result into plain text, which `python -m crafting_system.data diff` prints after the
diff. Reading is textual (the data layer imports no other module): an id counts when it stands
alone as a word in a line, a name or a mod text when a quoted string or the value after `key:` is
exactly it (the ranges `(6-11)` of a mod text count as `#`, the way a target may write them).

Listed, from `root`: `examples/**/*.yaml` (targets and routes), the claims in
`src/crafting_system/rules/claims/*.yaml` and `tests/*.py`. A folder that does not exist is empty.
A test file that reads a real dump (`real` as a word of its name, or an import of `real_game_data`) is always
listed, because the numbers it pins move with any patch. The text is deterministic.
"""

import codecs
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, fields
from pathlib import Path

from .model import BenchOption, GameData

EXAMPLES_DIR = "examples"
CLAIMS_DIR = "src/crafting_system/rules/claims"
TESTS_DIR = "tests"
REAL_NAME_WORD = "real"
MIN_PHRASE_LENGTH = 8  # a shorter name or text would match too many unrelated lines
SHOWN_TOKENS = 5

_IDENT = re.compile(r"[A-Za-z0-9_]+")
_DISTINCT = re.compile(r"[A-Za-z][A-Za-z]*[A-Z0-9_]")  # a lone word (family `Nothing`) would match prose
_KEYED = re.compile(r"\b(?:family|mod)\s*:\s*['\"]?([A-Za-z0-9_]+)")  # where a lone word is searched for
_REAL_LOADER = re.compile(r"^\s*from\s+\S+\s+import\s+.*\breal_game_data\b")  # the helper of the tests that read the real cache
_RANGE = re.compile(r"\(-?\d+(?:\.\d+)?-{1,2}\d+(?:\.\d+)?\)")  # (6-11), (-16-16), (-25--10)
_QUOTED = re.compile(r"\"([^\"]*)\"|'([^']*)'")
_VALUE = re.compile(r"^\s*(?:-\s+)*(?:[A-Za-z_][\w-]*:\s+)?(.+?)\s*$")
_CLAIM_ID = re.compile(r"^\s*-?\s*id:\s*['\"]?([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)")

ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class Reference:
    """One line of a target or route that names a changed thing; `kinds` says in what way it changed."""

    path: str
    line: int
    token: str
    kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimReference:
    """One claim (`claim` is its id) whose lines name changed things."""

    path: str
    claim: str
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReferencingTestFile:
    """A test file with `lines` lines that name changed things (`tokens`: the distinct ones, sorted)."""

    path: str
    lines: int
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DataChanges:
    """How many things of each kind changed, and the essences, fossils and bench options in words."""

    mods: int
    families: int
    base_items: int
    essences: int
    fossils: int
    bench_options: int
    actions: tuple[str, ...]

    @property
    def any(self) -> bool:
        return bool(self.mods + self.families + self.base_items + self.essences + self.fossils + self.bench_options)


@dataclass(frozen=True, slots=True)
class Impact:
    """Everything the patch touches in the repo; each list is sorted by path and line."""

    changes: DataChanges
    examples: tuple[Reference, ...]
    claims: tuple[ClaimReference, ...]
    tests: tuple[ReferencingTestFile, ...]
    real_tests: tuple[str, ...]


# --- the repo --------------------------------------------------------------------------------------


def find_repo_root(start: Path | str | None = None) -> Path | None:
    """The checkout this package sits in (a folder with `examples` and the package under `src`), or None.

    Without `start` the search begins at this module, so an installed copy of the package, which has
    no checkout around it, finds nothing. With `start`, it begins there and climbs.
    """
    here = Path(start).resolve() if start is not None else Path(__file__).resolve().parent
    for folder in (here, *here.parents):
        if (folder / EXAMPLES_DIR).is_dir() and (folder / "src" / "crafting_system").is_dir():
            return folder
    return None


# --- what changed ----------------------------------------------------------------------------------


def _change_kinds[V](old: Mapping[str, V], new: Mapping[str, V]) -> dict[str, str]:
    kinds = {key: ADDED for key in new.keys() - old.keys()}
    kinds |= {key: REMOVED for key in old.keys() - new.keys()}
    kinds |= {key: CHANGED for key in old.keys() & new.keys() if old[key] != new[key]}
    return kinds


def _short(item_id: str) -> str:
    return item_id.rsplit("/", 1)[-1]


def _bench_identity(option: BenchOption) -> tuple:
    return option.master, option.actions


def _bench_text(option: BenchOption) -> str:
    parts = [
        f"{field.name} {value}"
        for field in fields(option.actions)
        if (value := getattr(option.actions, field.name)) is not None
    ]
    return f"{option.master}: {'; '.join(parts) or 'no action'}"


def _class_changes(before: BenchOption, after: BenchOption) -> str:
    gained = sorted(set(after.item_classes) - set(before.item_classes))
    lost = sorted(set(before.item_classes) - set(after.item_classes))
    changes = [f"+{name}" for name in gained] + [f"-{name}" for name in lost]
    return f"; item classes {', '.join(changes)}" if changes else ""


def _bench_changes(old: GameData, new: GameData) -> list[tuple[str, str, BenchOption]]:
    """(text, kind, option) of the options that differ.

    Options have no id, so one is told by its master and actions. Where both versions have options
    with the same master and actions but different item classes, cost or tier, they are paired and
    reported as `changed`; the rest are `added` or `removed`.
    """
    before, after = Counter(old.bench_options), Counter(new.bench_options)
    gone, came = before - after, after - before
    found: list[tuple[str, str, BenchOption]] = []
    for identity in sorted({_bench_identity(o) for o in (*gone, *came)}, key=lambda i: (i[0], repr(i[1]))):
        left = sorted((o for o in gone.elements() if _bench_identity(o) == identity), key=repr)
        right = sorted((o for o in came.elements() if _bench_identity(o) == identity), key=repr)
        for one, other in zip(left, right):
            found.append((_bench_text(other) + _class_changes(one, other), CHANGED, other))
        for extra in right[len(left):]:
            found.append((_bench_text(extra), ADDED, extra))
        for extra in left[len(right):]:
            found.append((_bench_text(extra), REMOVED, extra))
    return found


class _Tokens:
    """What the repo's files are searched for: ids (whole words) and phrases (names, mod texts)."""

    def __init__(self) -> None:
        self.ids: dict[str, set[str]] = defaultdict(set)
        self.phrases: dict[str, set[str]] = defaultdict(set)
        self.keyed: dict[str, set[str]] = defaultdict(set)  # lone words, found only after `family:` or `mod:`

    def add_id(self, token: str, kind: str) -> None:
        if _DISTINCT.search(token):
            self.ids[token].add(kind)
        elif token:
            self.keyed[token].add(kind)

    def add_phrase(self, text: str | None, kind: str) -> None:
        for part in (text or "").split("\n"):
            part = _RANGE.sub("#", part).strip()
            if len(part) >= MIN_PHRASE_LENGTH:
                self.phrases[part].add(kind)

    def __bool__(self) -> bool:
        return bool(self.ids or self.phrases or self.keyed)


def _collect(old: GameData, new: GameData) -> tuple[DataChanges, _Tokens]:
    tokens = _Tokens()
    mod_kinds = _change_kinds(old.mods, new.mods)
    families: set[str] = set()
    for mod_id, kind in mod_kinds.items():
        tokens.add_id(mod_id, f"mod {kind}")
        for data in (old, new):
            mod = data.mods.get(mod_id)
            if mod is not None:
                families.update(mod.families)
                tokens.add_phrase(mod.text, f"mod {kind}")
    for family in families:
        tokens.add_id(family, "family of a changed mod")

    base_kinds = _change_kinds(old.base_items, new.base_items)
    for base_id, kind in base_kinds.items():
        tokens.add_id(_short(base_id), f"base item {kind}")
        tokens.add_phrase(base_id, f"base item {kind}")  # a full id may be written, with its slashes
        for data in (old, new):
            if base_id in data.base_items:
                tokens.add_phrase(data.base_items[base_id].name, f"base item {kind}")

    actions: list[str] = []
    essence_kinds = _change_kinds(old.essences, new.essences)
    for essence_id, kind in sorted(essence_kinds.items()):
        tokens.add_id(_short(essence_id), f"essence {kind}")
        actions.append(f"essence {_short(essence_id)} ({kind})")
        before = {entry.item_class: entry.mod_id for entry in old.essences[essence_id].mods} if essence_id in old.essences else {}
        after = {entry.item_class: entry.mod_id for entry in new.essences[essence_id].mods} if essence_id in new.essences else {}
        for item_class in before.keys() | after.keys():
            if before.get(item_class) != after.get(item_class):
                for mod_id in (before.get(item_class), after.get(item_class)):
                    tokens.add_id(mod_id or "", "mod of a changed essence")
        for data in (old, new):
            if essence_id in data.essences:
                tokens.add_phrase(data.essences[essence_id].name, f"essence {kind}")

    fossil_kinds = _change_kinds(old.fossils, new.fossils)
    for fossil_id, kind in sorted(fossil_kinds.items()):
        tokens.add_id(_short(fossil_id), f"fossil {kind}")
        actions.append(f"fossil {_short(fossil_id)} ({kind})")
        before_fossil, after_fossil = old.fossils.get(fossil_id), new.fossils.get(fossil_id)
        for attribute in ("added_mods", "forced_mods"):
            before_mods = set(getattr(before_fossil, attribute, ()))
            after_mods = set(getattr(after_fossil, attribute, ()))
            for mod_id in before_mods ^ after_mods:
                tokens.add_id(mod_id, "mod of a changed fossil")
        for fossil in (before_fossil, after_fossil):
            if fossil is not None:
                tokens.add_phrase(fossil.name, f"fossil {kind}")

    bench = _bench_changes(old, new)
    for text, kind, option in bench:
        actions.append(f"bench {text} ({kind})")
        for mod_id in (option.actions.add_explicit_mod, option.actions.add_enchant_mod):
            tokens.add_id(mod_id or "", "mod of a changed bench option")

    changes = DataChanges(
        mods=len(mod_kinds),
        families=len(families),
        base_items=len(base_kinds),
        essences=len(essence_kinds),
        fossils=len(fossil_kinds),
        bench_options=len(bench),
        actions=tuple(actions),
    )
    return changes, tokens


# --- looking in the files --------------------------------------------------------------------------


def _phrase_candidates(line: str) -> Iterator[str]:
    """The strings of a line that could be a whole name or text: quoted ones and the value after `key:`."""
    for match in _QUOTED.finditer(line):
        yield match.group(1) if match.group(1) is not None else match.group(2)
    value = _VALUE.match(line)
    if value is not None:
        text = value.group(1)
        yield text
        if " #" in text:  # a trailing comment
            yield text.split(" #", 1)[0].rstrip()


def _hits(line: str, tokens: _Tokens) -> dict[str, tuple[str, ...]]:
    """token -> kinds, for each changed thing the line names."""
    found: dict[str, tuple[str, ...]] = {}
    for word in dict.fromkeys(_IDENT.findall(line)):
        if word in tokens.ids:
            found[word] = tuple(sorted(tokens.ids[word]))
    if tokens.keyed:
        for word in _KEYED.findall(line):
            if word in tokens.keyed:
                found[word] = tuple(sorted(tokens.keyed[word]))
    if tokens.phrases:
        for candidate in _phrase_candidates(line):
            candidate = _RANGE.sub("#", candidate).strip()
            if candidate in tokens.phrases:
                found[candidate] = tuple(sorted(tokens.phrases[candidate]))
    return found


def _files(folder: Path, patterns: Iterable[str]) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted({path for pattern in patterns for path in folder.glob(pattern) if path.is_file()})


def _lines(path: Path) -> list[str]:
    """The lines of a text file (UTF-8 with or without a BOM, or UTF-16 with one); none if it cannot be read."""
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace").splitlines()
    return data.decode("utf-8-sig", errors="replace").splitlines()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan_examples(root: Path, tokens: _Tokens) -> tuple[Reference, ...]:
    found = []
    for path in _files(root / EXAMPLES_DIR, ("**/*.yaml", "**/*.yml")):
        for number, line in enumerate(_lines(path), start=1):
            for token, kinds in sorted(_hits(line, tokens).items()):
                found.append(Reference(_relative(path, root), number, token, kinds))
    return tuple(sorted(found, key=lambda r: (r.path, r.line, r.token)))


def _scan_claims(root: Path, tokens: _Tokens) -> tuple[ClaimReference, ...]:
    found = []
    for path in _files(root / CLAIMS_DIR, ("*.yaml", "*.yml")):
        claim = None
        named: dict[str, set[str]] = {}
        for line in _lines(path):
            match = _CLAIM_ID.match(line)
            if match is not None:
                for name, words in named.items():
                    found.append(ClaimReference(_relative(path, root), name, tuple(sorted(words))))
                claim, named = match.group(1), {}
                continue
            if claim is not None:
                words = _hits(line, tokens)
                if words:
                    named.setdefault(claim, set()).update(words)
        for name, words in named.items():
            found.append(ClaimReference(_relative(path, root), name, tuple(sorted(words))))
    return tuple(sorted(found, key=lambda c: (c.path, c.claim)))


def _scan_tests(root: Path, tokens: _Tokens) -> tuple[tuple[ReferencingTestFile, ...], tuple[str, ...]]:
    found, real = [], []
    for path in _files(root / TESTS_DIR, ("*.py",)):
        relative = _relative(path, root)
        lines = _lines(path)
        if REAL_NAME_WORD in path.stem.split("_") or any(_REAL_LOADER.match(line) for line in lines):
            real.append(relative)
        words: set[str] = set()
        count = 0
        for line in lines:
            hits = _hits(line, tokens)
            if hits:
                count += 1
                words.update(hits)
        if count:
            found.append(ReferencingTestFile(relative, count, tuple(sorted(words))))
    return tuple(found), tuple(real)


def compute_impact(old: GameData, new: GameData, root: Path) -> Impact:
    """What the change from `old` to `new` touches in the repo at `root` (see the module text)."""
    changes, tokens = _collect(old, new)
    root = Path(root)
    tests, real = _scan_tests(root, tokens)
    if not tokens:
        return Impact(changes, (), (), (), real)
    return Impact(changes, _scan_examples(root, tokens), _scan_claims(root, tokens), tests, real)


# --- text ------------------------------------------------------------------------------------------


def _shown(tokens: tuple[str, ...]) -> str:
    more = f", and {len(tokens) - SHOWN_TOKENS} more" if len(tokens) > SHOWN_TOKENS else ""
    return ", ".join(tokens[:SHOWN_TOKENS]) + more


def render_impact(impact: Impact, old_label: str = "old", new_label: str = "new") -> str:
    """The report as plain text, lines separated by `\\n`, without a final newline."""
    lines = [f"Impact of the patch on this repo: {old_label} -> {new_label}"]
    changes = impact.changes
    if not changes.any:
        lines.append("No changes in the data.")
    else:
        lines.append(
            f"Changed in the data: {changes.mods} mods, {changes.families} families, "
            f"{changes.base_items} base items, {changes.essences} essences, {changes.fossils} fossils, "
            f"{changes.bench_options} bench options"
        )
        if not (impact.examples or impact.claims or impact.tests):
            lines += ["", "Nothing in the targets, routes, claims or tests names a changed id."]
    if impact.examples:
        lines += ["", "Targets and routes (examples/):"]
        lines += [f"  {r.path}:{r.line}  {r.token} ({'; '.join(r.kinds)})" for r in impact.examples]
    if impact.claims:
        lines += ["", f"Claims ({CLAIMS_DIR}/):"]
        lines += [f"  {c.claim} ({c.path.rsplit('/', 1)[-1]}): {_shown(c.tokens)}" for c in impact.claims]
    if impact.tests:
        lines += ["", f"Tests that name changed things ({TESTS_DIR}/):"]
        lines += [
            f"  {t.path}: {t.lines} line{'s' if t.lines != 1 else ''}: {_shown(t.tokens)}" for t in impact.tests
        ]
    if impact.real_tests:
        lines += ["", "Tests that read the real cache, to re-run in full:"]
        lines += [f"  {path}" for path in impact.real_tests]
    if changes.actions:
        lines += ["", "Essences, fossils and bench options that changed (their actions):"]
        lines += [f"  {action}" for action in changes.actions]
    return "\n".join(lines)
