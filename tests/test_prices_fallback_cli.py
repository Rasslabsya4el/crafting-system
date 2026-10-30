"""`fetch` end to end with the real fallback chain: poe.ninja, poe.watch and the previous league, all recorded."""

from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit

from ninja_support import FakeNinja
from watch_support import FakeWatch

from crafting_system.prices import load_price_file
from crafting_system.prices.__main__ import main
from crafting_system.prices.poe_ninja import BASE_URL

NOW = datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)
HUNTER_VISE = "Stygian Vise (ilvl 85, Hunter)"


class Both:
    """One `get_json` for every host: the current league of poe.ninja from `FakeNinja`, the rest from `FakeWatch`."""

    def __init__(self, ninja, watch):
        self.ninja, self.watch = ninja, watch

    def __call__(self, url):
        league = parse_qs(urlsplit(url).query).get("league", ["Allflame"])[0]
        if url.startswith(BASE_URL) and league == "Allflame":
            return self.ninja(url)
        return self.watch(url)


def run(tmp_path, names, both, capsys, extra=()):
    wanted = tmp_path / "wanted.txt"
    wanted.write_text("\n".join(names) + "\n", encoding="utf-8")
    env = {"CRAFTING_DATA_DIR": str(tmp_path / "data")}
    code = main(
        ["fetch", "--wanted-file", str(wanted), *extra],
        get_json=both, today=date(2026, 10, 30), now=NOW, env=env,
    )
    return code, load_price_file(tmp_path / "data" / "prices.json"), capsys.readouterr().out


def test_each_missing_price_falls_to_the_next_source_and_is_flagged(tmp_path, capsys):
    ninja, watch = FakeNinja(), FakeWatch()
    ninja.drop_line("Fossil", "prismatic-fossil")
    ninja.set_stash_line("BaseType", 34026, count=2)  # Stygian Vise 85 Hunter becomes thin
    names = ["Prismatic Fossil", HUNTER_VISE, "Unlisted Orb"]

    code, saved, out = run(tmp_path, names, Both(ninja, watch), capsys)

    assert code == 0
    fossil = saved.prices["Prismatic Fossil"]
    assert (fossil.source, fossil.detail["league"], fossil.detail["date"]) == ("poe.watch", "Allflame", "2026-10-30")
    vise = saved.prices[HUNTER_VISE]
    assert vise.source == "poe.ninja-previous-league"
    assert vise.detail["league"] == "Mirage" and vise.detail["age_days"] == 98
    assert "Prismatic Fossil: no usable poe.ninja price; used poe.watch" in out
    assert f"{HUNTER_VISE}:" in out and "Mirage" in out and "different economy" in out
    assert "Unlisted Orb" in out.split("No price for")[1]
    assert "Unlisted Orb" not in saved.prices


def test_a_wanted_price_that_poe_ninja_has_never_reaches_a_fallback(tmp_path, capsys):
    ninja, watch = FakeNinja(), FakeWatch()

    code, saved, out = run(tmp_path, ["Hollow Fossil"], Both(ninja, watch), capsys)

    assert code == 0 and saved.prices["Hollow Fossil"].source == "poe.ninja"
    assert watch.requests == []
    assert "too thin" in out  # the recorded thin base and beast lines are reported
