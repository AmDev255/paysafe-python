"""Minimal webhook receiver on the standard library HTTP server. Verifies the signature before anything else.

Run:  PAYSAFE_WEBHOOK_SECRET=paysafe_webhook_... python examples/verify_webhook.py
Self-test without a secret: python examples/verify_webhook.py
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from paysafe_tz import SignatureVerificationError, construct_event

SECRET = os.environ.get("PAYSAFE_WEBHOOK_SECRET")
if not SECRET:
    vector = json.loads((Path(__file__).parent.parent / "tests" / "fixtures" / "webhook-vector.json").read_text())
    event = construct_event(vector["secret"], vector["body"], vector["header"], now=vector["nowValid"])
    print(f"Self-test ok: {event['type']} {event['data']['object']['id']}")
    sys.exit(0)

seen: set[str] = set()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        raw_body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            event = construct_event(SECRET, raw_body, self.headers.get("PaySafe-Signature"))
        except SignatureVerificationError as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"invalid signature: {e.reason}".encode())
            return
        if event["id"] in seen:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"duplicate")
            return
        seen.add(event["id"])
        if event["type"] == "payment.succeeded":
            obj = event["data"]["object"]
            print(f"paid {obj['id']} {obj['amount']}")
        elif event["type"] in ("payment.failed", "payment.expired"):
            print(f"not paid: {event['type']}")
        else:
            print(f"ignored {event['type']}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


print("Listening on http://localhost:8080")
HTTPServer(("", 8080), Handler).serve_forever()
