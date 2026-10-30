"""The price tests' network guard (tests/conftest.py) is on for every `test_prices_*.py` module and no other (#40)."""

import socket
import subprocess
import sys
from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parent / "conftest.py"

PRICE_MODULE = '''\
import socket

import pytest


def test_guard_is_on_without_an_import():
    with pytest.raises(AssertionError, match="the test used the network"):
        socket.create_connection(("example.com", 80))
'''

OTHER_MODULE = '''\
import socket


def test_guard_is_off_outside_price_tests():
    assert socket.getaddrinfo.__name__ == "getaddrinfo"
    assert socket.getaddrinfo.__module__ != "conftest"
'''


def test_the_guard_is_on_in_a_price_module_that_imports_nothing():
    """Name lookup and connection to a non-loopback host raise before any packet leaves."""
    with pytest.raises(AssertionError, match="the test used the network"):
        socket.getaddrinfo("poe.ninja", 443)
    with pytest.raises(AssertionError, match="the test used the network"):
        socket.create_connection(("poe.ninja", 443))


def test_a_loopback_connection_still_works():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname()) as client:
            connection, _ = server.accept()
            connection.close()
            assert client.getpeername() == server.getsockname()


def test_a_new_price_module_gets_the_guard_and_another_module_does_not(tmp_path):
    (tmp_path / "conftest.py").write_text(CONFTEST.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "test_prices_brand_new.py").write_text(PRICE_MODULE, encoding="utf-8")
    (tmp_path / "test_other_area.py").write_text(OTHER_MODULE, encoding="utf-8")
    ini = tmp_path / "empty.ini"
    ini.write_text("", encoding="utf-8")

    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-c", str(ini), "--rootdir", str(tmp_path), "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert "2 passed" in run.stdout
