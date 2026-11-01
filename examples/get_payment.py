"""Retrieves a payment by id and waits for a terminal state.

Usage: python examples/get_payment.py pay_01J7A9Q0K3M4N5P6R7S8T9V0W1
"""

import sys

from paysafe_tz import NotFoundError, PaySafe, is_payment_terminal

if len(sys.argv) < 2:
    print("usage: python examples/get_payment.py <payment id>", file=sys.stderr)
    sys.exit(2)

with PaySafe() as client:
    try:
        payment = client.payments.get(sys.argv[1])
        print(f"{payment.id} {payment.status} TZS {payment.amount} for {payment['customer']['phone']}")
        if not is_payment_terminal(payment):
            payment = client.payments.wait_for_terminal(payment.id)
            print(f"Final status: {payment.status}")
    except NotFoundError:
        print("No such payment in this project and environment", file=sys.stderr)
        sys.exit(1)
