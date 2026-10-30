"""Shared pytest setup: the network guard of the price tests."""

import socket
from fnmatch import fnmatch

import pytest

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
PRICE_TEST_FILES = "test_prices_*.py"


@pytest.fixture(autouse=True)
def network_guard(request, monkeypatch):
    """Any connection (or name lookup) to a host other than loopback fails with AssertionError.

    Scoped to price tests: it runs for every `test_prices_*.py` module, with no import, and for no
    other module. The local `http.server` tests of the real transport still work; the pathofexile.com
    host never gets a packet, not even a DNS question.
    """
    if not fnmatch(request.node.path.name, PRICE_TEST_FILES):
        return

    def check(host) -> None:
        if isinstance(host, bytes):
            host = host.decode("ascii", errors="replace")
        if host not in LOOPBACK_HOSTS:
            raise AssertionError(f"the test used the network: {host!r}")

    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_getaddrinfo, real_create_connection = socket.getaddrinfo, socket.create_connection

    def connect(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if isinstance(address, tuple):
            check(address[0])
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        check(address[0])
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", create_connection)
