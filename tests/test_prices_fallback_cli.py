"""`fetch` end to end with the real fallback chain: poe.ninja, poe.watch and the previous league, all recorded."""

from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit

from ninja_support import FakeNinja
from watch_support import FakeWatch

from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
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


def test_a_wanted_base_with_influences_in_the_wrong_order_is_matched_under_the_game_order(tmp_path, capsys):
    ninja, watch = FakeNinja(), FakeWatch()  # the recorded Warlord/Hunter Vise is a thin line (count 2)

    code, saved, out = run(tmp_path, ["Stygian Vise (ilvl 85, Warlord/Hunter)"], Both(ninja, watch), capsys)

    assert code == 0
    assert "Stygian Vise (ilvl 85, Hunter/Warlord): current line is too thin" in out
    assert "No price for 1 wanted resources:\n  Stygian Vise (ilvl 85, Hunter/Warlord)" in out


# -- names a hand override or a same-league trade price already covers spend no request (#47) --


def chain_requests(ninja, watch):
    """Every request that only the fallback chain makes: histories, details and anything sent to poe.watch."""
    return [*ninja.stash_history_requests(), *ninja.detail_requests(), *watch.requests]


def thin_vise_run(tmp_path, capsys, name=HUNTER_VISE, overrides=None, old_file=None):
    ninja, watch = FakeNinja(), FakeWatch()
    ninja.set_stash_line("BaseType", 34026, count=2)  # Stygian Vise 85 Hunter becomes thin
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    if overrides is not None:
        (data / "price_overrides.toml").write_text(overrides, encoding="utf-8")
    if old_file is not None:
        write_price_file(data / "prices.json", old_file)
    code, saved, out = run(tmp_path, [name], Both(ninja, watch), capsys)
    return code, saved, out, chain_requests(ninja, watch)


def trade_file(league="Allflame", detail=None):
    entry = PriceEntry(750.0, "trade-api", "median of 5", detail if detail is not None else {"league": league})
    return PriceFile(league, NOW, 359.7, {HUNTER_VISE: entry})


def test_a_thin_wanted_name_is_normally_sent_down_the_chain(tmp_path, capsys):
    code, saved, out, requests = thin_vise_run(tmp_path, capsys)

    assert code == 0 and requests  # the baseline the zero-request tests below are measured against
    assert "different economy" in out


def test_a_wanted_name_with_a_hand_override_sends_no_request(tmp_path, capsys):
    overrides = f'[prices]\n"{HUNTER_VISE}" = 900\n'

    code, saved, out, requests = thin_vise_run(tmp_path, capsys, overrides=overrides)

    assert code == 0
    assert requests == []
    assert "different economy" not in out and "poe.watch" not in out
    assert "No price for" not in out


def test_a_hand_override_with_influences_in_another_order_covers_the_wanted_name(tmp_path, capsys):
    reordered = "Stygian Vise (ilvl 85, Warlord/Hunter)"

    code, saved, out, requests = thin_vise_run(
        tmp_path, capsys, name=reordered, overrides=f'[prices]\n"{reordered}" = 900\n'
    )

    assert code == 0
    assert requests == []
    assert "No price for" not in out


def test_a_wanted_name_with_a_same_league_trade_price_sends_no_request_and_keeps_the_price(tmp_path, capsys):
    code, saved, out, requests = thin_vise_run(tmp_path, capsys, old_file=trade_file())

    assert code == 0
    assert requests == []
    assert saved.prices[HUNTER_VISE].source == "trade-api" and saved.prices[HUNTER_VISE].chaos == 750.0
    assert "No price for" not in out


def test_a_trade_price_of_another_league_does_not_cover_the_name(tmp_path, capsys):
    code, saved, out, requests = thin_vise_run(tmp_path, capsys, old_file=trade_file(league="Mirage"))

    assert code == 0 and requests
    assert saved.prices[HUNTER_VISE].source == "poe.ninja-previous-league"


def test_a_trade_price_stamped_with_another_league_does_not_cover_the_name(tmp_path, capsys):
    stamped = trade_file(league="Allflame", detail={"league": "Mirage"})

    code, saved, out, requests = thin_vise_run(tmp_path, capsys, old_file=stamped)

    assert code == 0 and requests
    assert saved.prices[HUNTER_VISE].source == "poe.ninja-previous-league"


def test_a_non_trade_price_in_the_old_file_does_not_cover_the_name(tmp_path, capsys):
    old = PriceFile("Allflame", NOW, 359.7, {HUNTER_VISE: PriceEntry(700.0, "poe.ninja")})

    code, saved, out, requests = thin_vise_run(tmp_path, capsys, old_file=old)

    assert code == 0 and requests
