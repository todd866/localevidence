"""The P1 privacy regression test: the local server must NOT advertise CORS.

A wildcard `Access-Control-Allow-Origin` would let any web page the user has open
read their ledger at 127.0.0.1 cross-origin. The PWA is same-origin and needs no
CORS, so the header must be absent.
"""

import http.client
import json
import threading
from http.server import HTTPServer

import localevidence.server as server


class _FakeLedger:
    entries: list = []

    def stats(self):
        return {"questions": 0, "answered": 0}

    def get(self, _i):
        return None

    def find_similar(self, _q, **_k):
        return []


class _FakeIndex:
    def stats(self):
        return {"papers": 0, "passages": 0}

    def search(self, _q, **_k):
        return []


def test_api_has_no_cors_header(monkeypatch):
    # bypass _boot (no model / index load); inject fakes
    monkeypatch.setattr(server, "_LEDGER", _FakeLedger(), raising=False)
    monkeypatch.setattr(server, "_INDEX", _FakeIndex(), raising=False)
    httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/ledger")
        resp = conn.getresponse()
        body = resp.read()
        assert resp.getheader("Access-Control-Allow-Origin") is None
        assert "answers" in json.loads(body)
    finally:
        t.join(timeout=5)
        httpd.server_close()
