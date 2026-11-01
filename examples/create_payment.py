"""Creates a TZS 10,000 payment with a persisted idempotency key, then polls until it is terminal.

Usage: python examples/create_payment.py [+255712340000]
Sandbox suffixes: 0000 succeeds, 1111 is declined, 4444 expires.
"""

import secrets
import sys
import tempfile
from pathlib import Path

from paysafe_tz import ApiError, PaySafe, PollingTimeoutError, RequestOptions, is_payment_successful

phone = sys.argv[1] if len(sys.argv) > 1 else "+255712340000"
order_id = f"order-{secrets.token_hex(4)}"

# Store the key with the order before sending, so a crash and restart reuses it instead of charging twice.
key_file = Path(tempfile.gettempdir()) / f"paysafe-{order_id}.key"
idempotency_key = key_file.read_text() if key_file.exists() else f"{order_id}-attempt-1"
key_file.write_text(idempotency_key)

try:
    with PaySafe() as client:
        payment = client.payments.create(
            {
                "amount": 10000,
                "currency": "TZS",
                "customer": {"phone": phone, "name": "Amina Juma"},
                "reference": order_id,
                "description": f"Order {order_id}",
                "metadata": {"order_id": order_id},
            },
            RequestOptions(idempotency_key=idempotency_key),
        )
        response = payment.last_response
        replayed = ", replayed" if response and response.idempotent_replayed else ""
        print(f"Created {payment.id} status={payment.status} (HTTP {response.status if response else '?'}{replayed})")

        final = client.payments.wait_for_terminal(payment.id, on_update=lambda p: print(f"  {p.status}"))
        if is_payment_successful(final):
            print(f"Paid: amount {final.amount} fee {final.fee} net {final.net}")
        else:
            failure = final.get("failure") or {}
            print(f"Not paid: {final.status} {failure.get('code') or ''}")
except PollingTimeoutError as e:
    print(f"Still {e.last_seen.get('status') if e.last_seen else 'unknown'} after the timeout; rely on the webhook")
except ApiError as e:
    print(f"API error {e.code} ({e.status}): {e.message} [{e.request_id}]", file=sys.stderr)
    sys.exit(1)
finally:
    key_file.unlink(missing_ok=True)
