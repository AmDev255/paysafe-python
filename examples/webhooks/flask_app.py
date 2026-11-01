"""Flask handler for PaySafe webhooks. Run with: flask --app examples.webhooks.flask_app run"""

import os

from flask import Flask, Response, request

from paysafe_tz import SignatureVerificationError, construct_event

app = Flask(__name__)
SECRET = os.environ["PAYSAFE_WEBHOOK_SECRET"]


@app.post("/paysafe/webhook")
def paysafe_webhook() -> Response:
    try:
        event = construct_event(SECRET, request.get_data(), request.headers.get("PaySafe-Signature"))
    except SignatureVerificationError:
        return Response("invalid signature", status=400)
    if event["type"] == "payment.succeeded":
        payment = event["data"]["object"]
        _ = payment.get("reference")  # deduplicate on event["id"], then mark the order as paid
    return Response("ok", status=200)
