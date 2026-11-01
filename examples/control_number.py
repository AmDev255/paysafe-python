"""Issues a control number for an invoice, reads it back with its payment entries, then cancels it."""

from paysafe_tz import PaySafe

with PaySafe() as client:
    number = client.control_numbers.create(
        {
            "payer_name": "Amina Juma",
            "payer_phone": "+255712340000",
            "payer_reference": "STU-2024-0091",
            "title": "Term 2 school fees",
            "reference": "INV-2026-0042",
            "payment_type": "fees",
            "mode": "instalment",
            "amount": 450000,
            "expires_at": "2026-12-31",
            "instalments": [
                {"amount": 225000, "due_at": "2026-11-30T00:00:00Z"},
                {"amount": 225000, "due_at": "2026-12-31T00:00:00Z"},
            ],
        }
    )
    print(f"Control number {number.formatted} ({number.id}) pay at {number['pay_url']}")

    detail = client.control_numbers.get(number.id)
    print(f"Balance TZS {detail.balance}, {len(detail['entries'])} entries, {detail['payment_status']}")
    for entry in detail["entries"]:
        print(f"  {entry['paid_at']} {entry['status']} {entry['amount']} via {entry['method']}")

    for item in client.control_numbers.list({"state": "unpaid", "limit": 5}):
        print(f"{item.formatted} {item['payer']['name']} owes {item.balance}")

    cancelled = client.control_numbers.cancel(number.id, "Issued in error during SDK example")
    print(f"Cancelled: {cancelled.status}")
