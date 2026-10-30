"""`python -m crafting_system.prices`: fetch and check, with an injected transport and clock."""

from datetime import UTC, date, datetime

from ninja_support import ninja  # noqa: F401  (a fixture)
from crafting_system.prices import PriceEntry, PriceFile, load_price_file, write_price_file
from crafting_system.prices.__main__ import main
from crafting_system.prices.poe_ninja import SourceError

NOW = datetime(2026, 10, 30, 21, 0, 5, tzinfo=UTC)


def run(argv, tmp_path, ninja=None, today=date(2026, 10, 30), now=NOW):
    env = {"CRAFTING_DATA_DIR": str(tmp_path / "data")}
    return main(argv, get_json=ninja, today=today, now=now, env=env)


def write_wanted(tmp_path, *names):
    path = tmp_path / "wanted.txt"
    path.write_text("\n".join(names) + "\n", encoding="utf-8")
    return str(path)


def test_fetch_writes_the_price_file_into_the_data_folder_and_reports(ninja, tmp_path, capsys):
    code = run(["fetch"], tmp_path, ninja)

    assert code == 0
    saved = load_price_file(tmp_path / "data" / "prices.json")
    assert saved.league == "Allflame"
    assert saved.prices["Hollow Fossil"].chaos == 206.8
    out = capsys.readouterr().out
    assert "Allflame" in out
    assert f"{len(saved.prices)} prices" in out


def test_fetch_takes_a_league_and_a_wanted_file_and_lists_what_stays_missing(ninja, tmp_path, capsys):
    wanted = write_wanted(tmp_path, "Hollow Fossil", "Nonexistent Orb", "", "# a comment", "Zzz Orb")

    code = run(["fetch", "--league", "Standard", "--wanted-file", wanted], tmp_path, ninja)

    assert code == 0
    assert load_price_file(tmp_path / "data" / "prices.json").league == "Standard"
    out = capsys.readouterr().out
    assert "Nonexistent Orb" in out and "Zzz Orb" in out
    assert out.index("Nonexistent Orb") < out.index("Zzz Orb")
    assert "a comment" not in out


def test_fetch_does_not_call_a_name_missing_when_an_override_prices_it(ninja, tmp_path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "price_overrides.toml").write_text(
        '[prices]\n"Nonexistent Orb" = 5\n', encoding="utf-8"
    )
    wanted = write_wanted(tmp_path, "Nonexistent Orb")

    run(["fetch", "--wanted-file", wanted], tmp_path, ninja)

    assert "Nonexistent Orb" not in capsys.readouterr().out


def test_a_failing_category_exits_1_and_leaves_the_existing_file_byte_identical(ninja, tmp_path, capsys):
    path = tmp_path / "data" / "prices.json"
    write_price_file(path, PriceFile("Old", NOW, 100.0, {"Chaos Orb": PriceEntry(1.0, "poe.ninja")}))
    before = path.read_bytes()
    ninja.overviews["Essence"] = SourceError("HTTP 500 for Essence")

    code = run(["fetch"], tmp_path, ninja)

    assert code == 1
    assert path.read_bytes() == before
    assert "Essence" in capsys.readouterr().err


def test_an_empty_category_exits_1_and_writes_no_file(ninja, tmp_path, capsys):
    ninja.overviews["Fossil"]["lines"] = []

    code = run(["fetch"], tmp_path, ninja)

    assert code == 1
    assert not (tmp_path / "data" / "prices.json").exists()
    assert "Fossil" in capsys.readouterr().err


def test_a_blank_league_exits_1_with_the_message(ninja, tmp_path, capsys):
    code = run(["fetch", "--league", ""], tmp_path, ninja)

    assert code == 1
    assert "league" in capsys.readouterr().err
    assert not (tmp_path / "data" / "prices.json").exists()


def test_a_failed_fetch_writes_nothing_and_leaves_the_old_file(ninja, tmp_path, capsys):
    old = PriceFile("Old", NOW, 100.0, {"Chaos Orb": PriceEntry(1.0, "poe.ninja")})
    write_price_file(tmp_path / "data" / "prices.json", old)
    ninja.overviews["Currency"] = SourceError("HTTP 500 for Currency")

    code = run(["fetch"], tmp_path, ninja)

    assert code == 1
    assert load_price_file(tmp_path / "data" / "prices.json") == old
    assert "Currency" in capsys.readouterr().err


def test_check_prints_the_stale_warning_and_the_missing_list(ninja, tmp_path, capsys):
    run(["fetch"], tmp_path, ninja)
    capsys.readouterr()
    wanted = write_wanted(tmp_path, "Hollow Fossil", "Zzz Orb", "Aaa Orb")

    code = run(["check", "--wanted-file", wanted], tmp_path, today=date(2026, 11, 7))

    assert code == 0
    out = capsys.readouterr().out
    assert "8 days" in out and "2026-10-30" in out
    assert "Aaa Orb" in out and "Zzz Orb" in out
    assert out.index("Aaa Orb") < out.index("Zzz Orb")
    assert "Hollow Fossil" not in out


def test_check_on_a_fresh_file_with_nothing_missing_is_quiet_about_both(ninja, tmp_path, capsys):
    run(["fetch"], tmp_path, ninja)
    capsys.readouterr()
    wanted = write_wanted(tmp_path, "Hollow Fossil")

    code = run(["check", "--wanted-file", wanted], tmp_path, today=date(2026, 11, 6))

    assert code == 0
    out = capsys.readouterr().out
    assert "days old" not in out
    assert "No price" not in out


def test_check_counts_overrides_as_priced(ninja, tmp_path, capsys):
    run(["fetch"], tmp_path, ninja)
    (tmp_path / "data" / "price_overrides.toml").write_text(
        '[prices]\n"Zzz Orb" = 5\n', encoding="utf-8"
    )
    capsys.readouterr()
    wanted = write_wanted(tmp_path, "Zzz Orb")

    run(["check", "--wanted-file", wanted], tmp_path)

    assert "Zzz Orb" not in capsys.readouterr().out


def test_check_without_a_price_file_says_to_run_the_fetcher(tmp_path, capsys):
    code = run(["check"], tmp_path)

    assert code == 1
    assert "prices fetch" in capsys.readouterr().err


def test_a_missing_wanted_file_is_an_error_not_a_crash(ninja, tmp_path, capsys):
    code = run(["fetch", "--wanted-file", str(tmp_path / "nope.txt")], tmp_path, ninja)

    assert code == 1
    assert "nope.txt" in capsys.readouterr().err
