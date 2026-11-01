"""Lists succeeded payments from the last 7 days, walking every page."""

from datetime import datetime, timedelta, timezone

from paysafe_tz import PaySafe

with PaySafe() as client:
    page = client.payments.list(
        {"status": "succeeded", "created_gte": datetime.now(timezone.utc) - timedelta(days=7), "limit": 50}
    )
    total = 0
    for payment in page.auto_paging_iter():
        print(f"{payment['created_at']} {payment.id} TZS {payment.amount} {payment.get('reference') or ''}")
        total += payment.amount
    print(f"Total: TZS {total:,}")
