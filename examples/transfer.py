"""Sends TZS 5,000 to another PaySafe project by handle and lists recent transfers.

Usage: python examples/transfer.py <recipient handle>
"""

import sys
from datetime import date

from paysafe_tz import InsufficientFundsError, PaySafe, RequestOptions, is_transfer_terminal

if len(sys.argv) < 2:
    print("usage: python examples/transfer.py <recipient handle>", file=sys.stderr)
    sys.exit(2)
to = sys.argv[1]

with PaySafe() as client:
    try:
        transfer = client.transfers.create(
            {"to": to, "amount": 5000, "note": "Shared delivery cost"},
            RequestOptions(idempotency_key=f"transfer-{to}-{date.today().isoformat()}"),
        )
        print(
            f"Transfer {transfer.id} {transfer.status} to {transfer['to']['name']} ({transfer['to']['organization']})"
        )
        if not is_transfer_terminal(transfer):
            transfer = client.transfers.wait_for_terminal(transfer.id)
            print(f"Review finished: {transfer.status}")
    except InsufficientFundsError as e:
        print(f"Not enough available balance (have {e.available})")

    for item in client.transfers.list({"limit": 5}):
        print(f"{item['created_at']} {item.direction} {item.amount} {item.status}")
