"""Lists recent payment events and shows the delivery attempts for the newest one."""

from datetime import datetime, timedelta, timezone

from paysafe_tz import PaySafe

with PaySafe() as client:
    events = client.events.list(
        {"type": "payment.succeeded", "from_": datetime.now(timezone.utc) - timedelta(days=1), "limit": 10}
    )
    for event in events:
        print(f"{event['created_at']} {event.id} {event['data']['object'].get('id', '')}")

    if events.data:
        detail = client.events.get(events.data[0].id)
        for d in detail["deliveries"]:
            status = d.get("response_status") or "-"
            print(f"  attempt {d['attempt']} {d['status']} HTTP {status} {d.get('latency_ms') or '-'}ms")
