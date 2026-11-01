"""The same payment flow with the asyncio client.

Usage: python examples/async_payment.py [+255712340000]
"""

import asyncio
import secrets
import sys

from paysafe_tz import AsyncPaySafe, RequestOptions, is_payment_successful


async def main() -> None:
    phone = sys.argv[1] if len(sys.argv) > 1 else "+255712340000"
    order_id = f"order-{secrets.token_hex(4)}"
    async with AsyncPaySafe() as client:
        payment = await client.payments.create(
            {"amount": 10000, "customer": {"phone": phone}, "reference": order_id},
            RequestOptions(idempotency_key=f"{order_id}-attempt-1"),
        )
        print(f"Created {payment.id} {payment.status}")
        final = await client.payments.wait_for_terminal(payment.id, on_update=lambda p: print(f"  {p.status}"))
        print("Paid" if is_payment_successful(final) else f"Not paid: {final.status}")

        async for p in await client.payments.list({"limit": 3}):
            print(f"{p.id} {p.status}")


asyncio.run(main())
