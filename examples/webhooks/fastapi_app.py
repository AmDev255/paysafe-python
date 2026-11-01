"""FastAPI handler for PaySafe webhooks. Run with: uvicorn examples.webhooks.fastapi_app:app"""

import os

from fastapi import FastAPI, Header, HTTPException, Request, Response

from paysafe_tz import SignatureVerificationError, construct_event

app = FastAPI()
SECRET = os.environ["PAYSAFE_WEBHOOK_SECRET"]


@app.post("/paysafe/webhook")
async def paysafe_webhook(request: Request, paysafe_signature: str = Header(default="")) -> Response:
    raw_body = await request.body()  # exact bytes, never the parsed JSON
    try:
        event = construct_event(SECRET, raw_body, paysafe_signature)
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid signature") from None
    # Persist event["id"] first and skip duplicates; deliveries can repeat and arrive out of order.
    if event["type"] == "payment.succeeded":
        payment = event["data"]["object"]
        _ = payment.get("reference")  # mark the order as paid
    return Response("ok", status_code=200)
