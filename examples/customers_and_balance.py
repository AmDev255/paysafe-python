"""Reads the balance, the latest ledger entries and recent customers."""

from paysafe_tz import PaySafe, balance_amount

with PaySafe() as client:
    balance = client.balance.get()
    print(f"Available TZS {balance_amount(balance['available']):,}, pending TZS {balance_amount(balance['pending']):,}")

    for tx in client.balance.transactions({"limit": 5}):
        print(f"{tx['created_at']} {tx.direction:<6} {tx.bucket:<9} {tx.amount:>8} → {tx['balance_after']}")

    for customer in client.customers.list({"limit": 5}):
        paid = customer.get("payment_count", 0)
        print(f"{customer.id} {customer.phone} paid {paid} times, TZS {customer.get('total_paid', 0)}")
