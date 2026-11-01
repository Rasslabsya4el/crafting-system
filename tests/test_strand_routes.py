"""The strand routes S01, S02 (published, 3.29) and S11, S12, S13 (test routes), ticket #272.

docs/research/2026-11-01-strand-routes.md has the search and the numbers. S01 is the forum guide of Xeverous (a
Crusader + Warlord energy-shield ring), S02 the Reddit showcase of u/DisciplesOfAres (a Helical Ring, fire and all
resistance). S11 to S13 are test routes: R13 on a Remembrance-rolled belt, R05 on a ring with 60 strands, R13 with an
Orb of Unravelling as its finish.

The loader of the given routes does not read strands yet (B5-12, #292, adds the words), so the checks use what the
loader exposes today: its YAML reader and its key lists. They show that

* every file is read by the loader's own YAML reader and uses only the loader's keys plus the strand words;
* every `do` is `restart`, a strand action, an action of the matching route, or a label of the 3.29 data;
* each route names its source (a URL) or says "TEST ROUTE";
* S11's rules are R13's with step 0 added, S12's rule is R05's;
* each target is read by the target loader on the real 3.29.3.3 dump once the strand words are taken out, and each buy
  spec by the buy-spec loader (the target check needs the dump and skips cleanly without it).
"""

import re
from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data

from crafting_system.cli._route import REFUSED_KEYS, RESTART, RULE_KEYS, TOP_KEYS, WHEN_KEYS
from crafting_system.prices.trade_query import load_buy_spec
from crafting_system.targets import parse_target
from crafting_system.targets.lines import LineList, LineMap, load_with_lines

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "examples" / "routes"
TARGETS = ROOT / "examples" / "targets"
BUYS = ROOT / "examples" / "buy"
# The strand files wait outside examples/ until B5-12 (#292): the parse-all tests of examples/ read every file there with
# today's loaders, which do not know the strand words.
FILES = ROOT / "docs" / "research" / "2026-11-01-strand-routes-files"
S_ROUTES, S_TARGETS, S_BUYS = FILES / "routes", FILES / "targets", FILES / "buy"

STRAND_WHEN = ("memory_strands_at_least", "memory_strands_below")
STRAND_ACTIONS = ("Orb of Remembrance", "Orb of Unravelling")
STRAND_KINDS = ("remembrance-orb", "unravelling-orb")

PUBLISHED = {
    "s01-es-ring-forum-guide": "https://www.pathofexile.com/forum/view-thread/3882365",
    "s02-fire-res-ring-showcase": "https://www.reddit.com/r/pathofexile/comments/1vqlc59/",
}
TEST_ROUTES = {
    # route and target stem   built on                strands of the start item
    "s11-remembrance-belt": ("r13-life-resist-belt", 0),
    "s12-stranded-ring": ("r05-strength-ring", 60),
    "s13-unravelling-belt": ("r13-life-resist-belt", 82),
}
STEMS = [*PUBLISHED, *TEST_ROUTES]
BUY_SPECS = {
    "s01-es-ring-forum-guide": "s01-start-ring.yaml",
    "s02-fire-res-ring-showcase": "s02-start-ring.yaml",
    "s12-stranded-ring": "s12-start-ring.yaml",
    "s13-unravelling-belt": "s13-start-belt.yaml",
}

# Labels of actions that the 3.29 data prints and that the published routes use (src/crafting_system/actions).
KNOWN_LABELS = {
    "Regal Orb",
    "Orb of Transmutation",
    "Fossils Dense Fossil",
    "Harvest Reforge Critical",
    "Harvest Reforge Fire",
    "Bench craft +#% to Fire Resistance [EinharMasterFireResist2]",
    "Bench craft Prefixes Cannot Be Changed",
}


def read(path: Path) -> LineMap:
    root = load_with_lines(path.read_text(encoding="utf-8"), str(path))
    assert isinstance(root, LineMap)
    return root


def plain(node):
    """A LineMap or LineList as ordinary dicts and lists."""
    if isinstance(node, LineMap):
        return {key: plain(value) for key, value in node.items()}
    if isinstance(node, LineList):
        return [plain(value) for value in node]
    return node


def actions_of(route: LineMap) -> set[str]:
    return {rule["do"] for rule in route["rules"]}


def families_of(target: LineMap) -> set[str]:
    found: set[str] = set()

    def walk(items):
        for item in items:
            if "of" in item:
                walk(item["of"])
            elif "family" in item:
                found.add(item["family"])

    walk(target["requirements"])
    return found


@pytest.fixture(params=STEMS)
def stem(request):
    return request.param


def test_each_route_is_read_by_the_loaders_yaml_reader_with_known_keys(stem):
    route = read(S_ROUTES / f"{stem}.yaml")
    assert set(route) <= set(TOP_KEYS)
    assert isinstance(route["name"], str) and route["rules"]
    for rule in route["rules"]:
        assert set(rule) <= set(RULE_KEYS)
        when = rule.get("when", {})
        assert set(when) <= {*WHEN_KEYS, *STRAND_WHEN}, set(when) - set(WHEN_KEYS)
        assert not set(when) & set(REFUSED_KEYS)
        for key in STRAND_WHEN:
            if key in when:
                assert isinstance(when[key], int) and not isinstance(when[key], bool) and 1 <= when[key] <= 100


def test_each_action_is_restart_a_strand_action_or_a_known_label(stem):
    allowed = {RESTART, *STRAND_ACTIONS, *KNOWN_LABELS}
    if stem in TEST_ROUTES:
        allowed |= actions_of(read(ROUTES / f"{TEST_ROUTES[stem][0]}.yaml"))
    unknown = actions_of(read(S_ROUTES / f"{stem}.yaml")) - allowed
    assert not unknown, unknown


def test_each_route_names_its_source_or_says_it_is_a_test_route(stem):
    text = (S_ROUTES / f"{stem}.yaml").read_text(encoding="utf-8")
    assert "docs/research/2026-11-01-strand-routes.md" in text
    if stem in PUBLISHED:
        assert "SOURCE (published, 3.29)" in text and PUBLISHED[stem] in text
        assert "TEST ROUTE" not in text
    else:
        assert "TEST ROUTE" in text and "SOURCE: none" in text


def test_the_status_conditions_name_requirements_of_the_target(stem):
    families = families_of(read(S_TARGETS / f"{stem}.yaml"))
    for rule in read(S_ROUTES / f"{stem}.yaml")["rules"]:
        for entry in rule.get("when", {}).get("requirements", []):
            assert entry["family"] in families


def test_the_start_item_has_a_rule(stem):
    """The route starts from a normal item (a normal ring or belt) or from a rare one (S12's ring)."""
    rules = plain(read(S_ROUTES / f"{stem}.yaml"))["rules"]
    start = plain(read(S_TARGETS / f"{stem}.yaml")).get("start_item", {}).get("rarity", "normal")
    assert any(rule.get("when", {}).get("rarity", start) == start for rule in rules)


def test_s11_is_r13_with_step_zero():
    s11 = plain(read(S_ROUTES / "s11-remembrance-belt.yaml"))["rules"]
    r13 = plain(read(ROUTES / "r13-life-resist-belt.yaml"))["rules"]
    assert r13[-1] == {"when": {"rarity": "normal"}, "do": "Orb of Transmutation"}
    assert s11[: len(r13) - 1] == r13[:-1]
    assert s11[len(r13) - 1 :] == [
        {"when": {"rarity": "normal", "memory_strands_below": 40}, "do": "Orb of Remembrance"},
        r13[-1],
    ]


def test_s12_is_r05s_rule():
    s12 = plain(read(S_ROUTES / "s12-stranded-ring.yaml"))["rules"]
    assert s12 == plain(read(ROUTES / "r05-strength-ring.yaml"))["rules"]


def test_s13_unravels_only_with_strands_left_and_ends_in_a_restart():
    rules = plain(read(S_ROUTES / "s13-unravelling-belt.yaml"))["rules"]
    unravel = [rule for rule in rules if rule["do"] == "Orb of Unravelling"]
    assert len(unravel) == 3
    for rule in unravel:
        assert rule["when"]["rarity"] == "rare" and rule["when"]["memory_strands_at_least"] == 1
    index = [rule["do"] for rule in rules].index("Orb of Unravelling")
    assert all(rule["do"].startswith("Bench craft") for rule in rules[:index])
    assert {"when": {"rarity": "rare"}, "do": RESTART} in rules


def test_the_published_routes_unravel_only_with_strands_left_and_remembrance_only_on_a_normal_item():
    for stem in PUBLISHED:
        words = [rule for rule in plain(read(S_ROUTES / f"{stem}.yaml"))["rules"] if rule["do"] in STRAND_ACTIONS]
        assert words
        for rule in words:
            when = rule["when"]
            if rule["do"] == "Orb of Unravelling":
                assert when["memory_strands_at_least"] >= 1 and when["rarity"] == "rare"
            else:
                assert when["rarity"] == "normal"


def test_each_test_target_asks_what_the_base_target_asks_and_the_start_strands_match_the_buy_spec():
    for stem, (base_stem, strands) in TEST_ROUTES.items():
        target = plain(read(S_TARGETS / f"{stem}.yaml"))
        base = plain(read(TARGETS / f"{base_stem}.yaml"))
        for key in ("base", "item_level", "requirements"):
            assert target[key] == base[key], (stem, key)
        # a target never asks for strands: no requirement names them
        assert "strand" not in yaml.safe_dump(target["requirements"]).lower()
        if not strands:
            assert "start_item" not in target and target["start_price"] == base["start_price"]
            assert "remembrance-orb" in target["actions"]
            continue
        assert target["start_item"]["memory_strands"] == strands
        assert plain(read(S_BUYS / BUY_SPECS[stem]))["memory_strands"] == strands


def test_each_target_names_the_price_of_its_buy_spec():
    for stem, name in BUY_SPECS.items():
        target = plain(read(S_TARGETS / f"{stem}.yaml"))
        assert plain(read(S_BUYS / name))["name"] == target["start_price"]


def without_strand_words(text: str) -> str:
    """The file as today's loaders read it: no `memory_strands:` line and no proposed strand kind."""
    text = re.sub(r"(?m)^\s*memory_strands:.*\n", "", text)
    return re.sub(r"\b(?:%s)\b,? ?" % "|".join(STRAND_KINDS), "", text)


def test_each_target_is_read_by_the_target_loader_on_the_real_dump(stem):
    data = real_game_data()
    text = without_strand_words((S_TARGETS / f"{stem}.yaml").read_text(encoding="utf-8"))
    assert parse_target(text, data, source=f"{stem}.yaml").requirements


def test_each_buy_spec_is_read_by_the_buy_spec_loader(tmp_path):
    for name in BUY_SPECS.values():
        path = tmp_path / name
        path.write_text(without_strand_words((S_BUYS / name).read_text(encoding="utf-8")), encoding="utf-8")
        assert load_buy_spec(path).name
