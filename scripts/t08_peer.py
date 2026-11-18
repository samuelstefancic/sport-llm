"""Pair HTTP réservé aux tests T08, avec propositions issues du parseur local."""

from collections import defaultdict
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Event, Lock, Thread
from uuid import UUID

from fastapi import Response
from verify_t04 import HOST, ROOT


@contextmanager
def controlled_peer(port):
    # The real FastAPI handler is invoked with the same input envelope and correlation.
    import sys
    sys.path.insert(0, str(ROOT / "python"))
    try:
        from app import ProposalInput, propose
    finally:
        sys.path.pop(0)

    class Peer:
        def __init__(self):
            self.gates = {}
            self.faults = {}
            self.calls = defaultdict(int)
            self.guard = Lock()

        def gate(self, entry, revision):
            reached, release = Event(), Event()
            self.gates[(entry, revision)] = (reached, release)
            return reached, release

        def count(self, entry, revision):
            with self.guard:
                return self.calls[(entry, revision)]

        def respond(self, body, correlation):
            key = (body["entry_id"], body["entry_revision"])
            with self.guard:
                self.calls[key] += 1
            response = propose(ProposalInput.model_validate(body), Response(), UUID(correlation))
            if key == ("MEAL-001", 1):
                response["proposal_id"] = "PROP-OLD"
            if key in self.gates:
                reached, release = self.gates[key]
                reached.set()
                assert release.wait(5), key
            fault = self.faults.get(key)
            if fault == "shape":
                return {"kind": "not_a_proposal"}
            if fault == "quantity":
                response["food_mentions"][0]["quantity"]["value"] = 999
            return response

    peer = Peer()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/internal/proposals"
            correlation = self.headers["X-Correlation-ID"]
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result = json.dumps(peer.respond(body, correlation)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.send_header("X-Correlation-ID", correlation)
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, message, *args):
            pass

    with ThreadingHTTPServer((HOST, port), Handler) as server:
        server_thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        server_thread.start()
        try:
            yield peer
        finally:
            for _, release in peer.gates.values():
                release.set()
            server.shutdown()
            server_thread.join()
