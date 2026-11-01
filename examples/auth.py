"""Proves the key works with a read-only call and prints the rate-limit budget.

Usage: PAYSAFE_SECRET_KEY=paysafe_test_... python examples/auth.py
"""

import sys

from paysafe_tz import ApiError, PaySafe, PaySafeError, balance_amount

try:
    with PaySafe() as client:
        balance = client.balance.get()
        rate = balance.last_response.rate_limit if balance.last_response else None
        print(f"Environment : {client.environment}")
        print(f"Available   : TZS {balance_amount(balance['available']):,}")
        print(f"Pending     : TZS {balance_amount(balance['pending']):,}")
        print(f"Rate limit  : {rate.remaining if rate else '?'} remaining of {rate.limit if rate else '?'}")
        print(f"Request id  : {balance.request_id}")
except ApiError as e:
    print(f"API error {e.code} ({e.status}): {e.message} [{e.request_id}]", file=sys.stderr)
    sys.exit(1)
except PaySafeError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
