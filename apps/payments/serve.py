#!/usr/bin/env python3
"""Serve the IINK test payment UI and its fixed, read-only RPC route."""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
RPC_URL = "http://127.0.0.1:9944"
READ_METHODS = {
    "eth_chainId",
    "system_chain",
    "eth_estimateGas",
    "eth_gasPrice",
    "eth_getBalance",
    "eth_getTransactionReceipt",
    "eth_getBlockByNumber",
}
ORIGINS = {"http://127.0.0.1:8000", "http://localhost:8000"}


class PaymentServer(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/rpc":
            self.send_error(404)
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ORIGINS:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16_384:
                raise ValueError
            body = self.rfile.read(size)
            payload = json.loads(body)
        except (ValueError, OSError):
            self.send_error(400)
            return
        if (
            not isinstance(payload, dict)
            or payload.get("jsonrpc") != "2.0"
            or not isinstance(payload.get("method"), str)
            or payload["method"] not in READ_METHODS
            or not isinstance(payload.get("params"), list)
        ):
            self.send_error(400, "Unsupported RPC request")
            return
        try:
            request = Request(RPC_URL, body, {"Content-Type": "application/json"})
            with urlopen(request, timeout=5) as upstream:
                response = upstream.read(4_194_305)
            if len(response) > 4_194_304:
                raise ValueError
        except (URLError, TimeoutError, ValueError):
            self.send_error(502, "Alice's local RPC is unavailable")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


if __name__ == "__main__":
    handler = partial(PaymentServer, directory=ROOT)
    with ThreadingHTTPServer(("127.0.0.1", 8000), handler) as server:
        print("IINK Payments is running at http://127.0.0.1:8000", flush=True)
        server.serve_forever()
