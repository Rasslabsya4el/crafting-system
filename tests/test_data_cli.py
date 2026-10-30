"""`python -m crafting_system.data fetch|verify`: output lines, exit codes, errors on stderr."""

import os
import subprocess
import sys
import urllib.error

import pytest
from repoe_support import (
    FILE_NAMES,
    FakeOpener,
    fixture_bytes,
    fixture_pin_and_opener,
    no_network,  # noqa: F401
)

from crafting_system.data import fetch as fetch_module
from crafting_system.data.__main__ import main
from crafting_system.data.fetch import cache_folder


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The configured cache directory, redirected into `tmp_path`."""
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)
    monkeypatch.setenv("CRAFTING_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def lines(text):
    return text.splitlines()


def test_fetch_prints_one_line_per_file_and_returns_zero(cache, capsys):
    pin, opener = fixture_pin_and_opener()

    code = main(["fetch"], pin=pin, open_url=opener)

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert len(lines(captured.out)) == len(FILE_NAMES)
    for line, pinned in zip(lines(captured.out), pin.files, strict=True):
        assert line == f"{pinned.name}: downloaded, {pinned.size} bytes, sha256 {pinned.sha256[:12]}"
    assert (cache_folder(pin) / "mods.json").is_file()


def test_a_second_fetch_says_cached_and_downloads_nothing(cache, capsys):
    pin, opener = fixture_pin_and_opener()
    main(["fetch"], pin=pin, open_url=opener)
    capsys.readouterr()
    downloads = len(opener.urls)

    code = main(["fetch"], pin=pin, open_url=opener)

    assert code == 0
    assert all(": cached, " in line for line in lines(capsys.readouterr().out))
    assert len(opener.urls) == downloads


def test_fetch_uses_the_default_downloader_when_none_is_given(cache, monkeypatch, capsys):
    pin, opener = fixture_pin_and_opener()
    monkeypatch.setattr(fetch_module, "default_open_url", opener)

    assert main(["fetch"], pin=pin) == 0
    assert len(opener.urls) == len(FILE_NAMES)


def test_verify_after_a_fetch_prints_ok_for_each_file(cache, capsys):
    pin, opener = fixture_pin_and_opener()
    main(["fetch"], pin=pin, open_url=opener)
    capsys.readouterr()

    code = main(["verify"], pin=pin)

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert [line.split(":")[0] for line in lines(captured.out)] == list(FILE_NAMES)
    assert all(": ok, " in line for line in lines(captured.out))


def test_verify_without_a_cache_exits_one_and_names_the_fetch_command(cache, capsys):
    pin, _ = fixture_pin_and_opener()

    code = main(["verify"], pin=pin)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "python -m crafting_system.data fetch" in captured.err


def test_verify_of_a_tampered_file_exits_one_and_names_the_file(cache, capsys):
    pin, opener = fixture_pin_and_opener()
    main(["fetch"], pin=pin, open_url=opener)
    capsys.readouterr()
    (cache_folder(pin) / "fossils.json").write_bytes(b"tampered")

    code = main(["verify"], pin=pin)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error: ")
    assert "fossils.json" in captured.err
    assert captured.out == ""


def test_fetch_of_a_download_that_differs_from_the_pin_exits_one(cache, capsys):
    pin, _ = fixture_pin_and_opener()
    payloads = fixture_bytes()
    payloads["mods.json"] = payloads["mods.json"][:-1]

    code = main(["fetch"], pin=pin, open_url=FakeOpener(pin, payloads))

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error: ")
    assert "mods.json" in captured.err
    assert "nothing was kept" in captured.err
    assert not (cache_folder(pin) / "mods.json").exists()


def test_fetch_with_a_network_failure_exits_one_and_names_the_url(cache, capsys):
    pin, _ = fixture_pin_and_opener()

    def failing(url):
        raise urllib.error.URLError("no route to host")

    code = main(["fetch"], pin=pin, open_url=failing)

    captured = capsys.readouterr()
    assert code == 1
    assert pin.url_for("mods.json") in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("command", ["fetch", "verify"])
def test_a_broken_config_file_exits_one_with_an_error_line(tmp_path, monkeypatch, capsys, command):
    broken = tmp_path / "crafting.toml"
    broken.write_text("[paths\ncache_dir = ", encoding="utf-8")
    monkeypatch.setenv("CRAFTING_CONFIG", str(broken))
    pin, opener = fixture_pin_and_opener()

    code = main([command], pin=pin, open_url=opener)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "not valid TOML" in captured.err
    assert "Traceback" not in captured.err
    assert opener.urls == []


@pytest.mark.parametrize("command", ["fetch", "verify"])
def test_a_config_file_that_does_not_exist_exits_one_with_an_error_line(tmp_path, monkeypatch, capsys, command):
    monkeypatch.setenv("CRAFTING_CONFIG", str(tmp_path / "missing.toml"))
    pin, opener = fixture_pin_and_opener()

    code = main([command], pin=pin, open_url=opener)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error: ")
    assert "does not exist" in captured.err


def test_a_file_where_the_cache_folder_should_be_exits_one(cache, capsys):
    pin, opener = fixture_pin_and_opener()
    folder = cache_folder(pin)
    folder.parent.mkdir(parents=True)
    folder.write_bytes(b"a file")

    code = main(["fetch"], pin=pin, open_url=opener)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error: ")
    assert str(folder) in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("argv", [[], ["bogus"], ["fetch", "extra"], ["--nope"]])
def test_wrong_usage_returns_two_and_prints_usage_to_stderr(argv, capsys):
    code = main(argv)

    captured = capsys.readouterr()
    assert code == 2
    assert "usage:" in captured.err
    assert captured.out == ""


def test_help_returns_zero(capsys):
    assert main(["--help"]) == 0
    assert "fetch" in capsys.readouterr().out


def test_main_reads_the_process_arguments_by_default(cache, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["data", "verify"])

    assert main() == 1  # the real pin, and an empty cache folder
    assert "python -m crafting_system.data fetch" in capsys.readouterr().err


def test_running_the_module_as_a_command_works(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "crafting_system.data", "verify"],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "CRAFTING_CACHE_DIR": str(tmp_path / "empty")},
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("error: ")
    assert "python -m crafting_system.data fetch" in result.stderr
