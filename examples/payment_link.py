"""Creates a hosted payment link, lists links, then pauses and archives the new one."""

from datetime import datetime, timedelta, timezone

from paysafe_tz import PaySafe

with PaySafe() as client:
    link = client.payment_links.create(
        {
            "title": "Workshop ticket",
            "description": "One seat, Saturday session",
            "amount": 25000,
            "collect_name": True,
            "collect_email": True,
            "max_payments": 50,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=14),
        }
    )
    print(f"Share this: {link.url} ({link.id})")

    for item in client.payment_links.list({"status": "active", "limit": 10}):
        print(f"{item.id} {item.title} paid {item['paid_count']}/{item.get('max_payments') or '∞'}")

    paused = client.payment_links.pause(link.id)
    print(f"Paused: {paused.status} state={paused.state}")
    archived = client.payment_links.archive(link.id)
    print(f"Archived: {archived.status}")
