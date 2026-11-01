"""Refunds part of a succeeded payment and waits for the result.

Usage: python examples/refund.py pay_... [amount]
"""

import sys

from paysafe_tz import InsufficientFundsError, InvalidStateError, PaySafe, RequestOptions

if len(sys.argv) < 2:
    print("usage: python examples/refund.py <payment id> [amount]", file=sys.stderr)
    sys.exit(2)
payment_id = sys.argv[1]
params = {"payment": payment_id, "reason": "requested_by_customer"}
if len(sys.argv) > 2:
    params["amount"] = int(sys.argv[2])

with PaySafe() as client:
    try:
        refund = client.refunds.create(params, RequestOptions(idempotency_key=f"refund-{payment_id}-1"))
        print(f"Refund {refund.id} {refund.status}")
        final = client.refunds.wait_for_terminal(refund.id)
        print(f"Final: {final.status} {final.get('failure_reason') or ''}")
    except InsufficientFundsError as e:
        print(f"Not enough available balance: have {e.available}, need {e.requested}")
    except InvalidStateError as e:
        print(f"Cannot refund: {e.message}")
