"""Registers a webhook endpoint, stores its secret, disables it and deletes it again.

Usage: python examples/webhook_endpoints.py https://your-server.example/paysafe/webhook
"""

import sys

from paysafe_tz import PaySafe

if len(sys.argv) < 2:
    print("usage: python examples/webhook_endpoints.py <https url>", file=sys.stderr)
    sys.exit(2)

with PaySafe() as client:
    endpoint = client.webhook_endpoints.create(
        {
            "url": sys.argv[1],
            "description": "Order fulfilment",
            "events": ["payment.succeeded", "payment.failed", "refund.succeeded"],
        }
    )
    # The secret is returned once. Put it in your secret store as PAYSAFE_WEBHOOK_SECRET.
    print(f"Endpoint {endpoint.id} created; secret starts with {endpoint.secret[:20]}…")

    for item in client.webhook_endpoints.list():
        print(f"{item.id} {item.status} {item.url} streak={item['failure_streak']}")

    disabled = client.webhook_endpoints.update(endpoint.id, {"status": "DISABLED"})
    print(f"Now {disabled.status}")
    client.webhook_endpoints.delete(endpoint.id)
    print("Deleted")
