# PaySafe Python SDK

Official Python library for the [PaySafe](https://paysafe.co.tz) payments API. Accept mobile-money payments in Tanzania, issue refunds, control numbers and payment links, move money between projects, and receive signed webhooks.

Part of the [PaySafe SDK directory](https://github.com/AmDev255/paysafe-sdks). API reference: https://paysafe.co.tz/docs.

## Features

- Every served PaySafe API operation (29 operations, 10 resources) with typed request and response models
- Sandbox and production selected automatically from the key prefix
- Safe retries that honour `Retry-After`, idempotency keys that survive retries, cursor pagination helpers
- Polling helpers that wait for a payment, refund or transfer to reach a terminal state
- Webhook signature verification with secret rotation support and constant-time comparison
- One structured exception per documented error code, every error carries the request id
- Configurable timeouts, base URL, logger and HTTP client

## Installation

```bash
pip install paysafe-tz
```

## Requirements

Python 3.9 or newer. Depends on `httpx`; the async client uses `asyncio`.

## Authentication

Create a secret key in the dashboard under API keys. Test keys start with `paysafe_test_`, live keys with `paysafe_live_`. Keep keys on the server; never ship them in browsers or mobile apps. The SDK reads `PAYSAFE_SECRET_KEY` when no key is passed.

## Sandbox setup

Use a `paysafe_test_` key. The sandbox is the same API with a simulated provider; the last four digits of the customer phone choose the outcome (`0000` succeeds, `1111` is declined, `4444` expires, see the [Sandbox guide](https://paysafe.co.tz/docs/sandbox)).

## Production setup

Switch to a `paysafe_live_` key once your organisation is verified. Register a live webhook endpoint and add your server's address to the project's IP allowlist. Nothing else changes.

## Quickstart

```python
import os
from paysafe_tz import PaySafe, RequestOptions, is_payment_successful

client = PaySafe(os.environ["PAYSAFE_SECRET_KEY"])  # paysafe_test_… selects the sandbox

payment = client.payments.create(
    {
        "amount": 10000,  # TZS, integer
        "customer": {"phone": "+255712340000", "name": "Amina Juma"},
        "reference": "order-8812",
    },
    RequestOptions(idempotency_key="order-8812-attempt-1"),  # persist the key before calling
)
print(payment.id, payment.status)  # 202 Accepted: still pending

final = client.payments.wait_for_terminal(payment.id)  # or wait for the webhook
if is_payment_successful(final):
    print("Paid, net TZS", final.net)
```

## Supported API resources

| Resource | Operations |
|---|---|
| Payments | create, list, get, cancel, waitForTerminal |
| Payment links | create, list, get, update |
| Control numbers | create, list, get, cancel |
| Refunds | create, list, get, waitForTerminal |
| Balance | get, transactions |
| Customers | list, get |
| Transfers | create, list, get, waitForTerminal |
| Webhook endpoints | list, create, get, update, delete |
| Events | list, get |
| Webhooks | verifySignature, constructEvent |

Planned by PaySafe and not yet served (not included): `ping`, payouts (`createPayout`, `getPayout`), `rotateWebhookEndpointSecret`.

## Usage examples

Runnable programs live in [`examples/`](examples/): authentication, creating and polling a payment, listing with pagination, refunds, payment links, control numbers, transfers, webhook endpoints, events and webhook verification, plus framework handlers under `examples/webhooks/`.

Every resource follows the same shape: `create`, `list`, `get`, plus resource-specific actions. Objects come back as `ApiObject`, a `dict` with the API's snake_case keys that also allows attribute access (`payment.status` or `payment["status"]`) and carries `last_response`. Lists return a `Page`; iterate it for its items or call `auto_paging_iter()` to walk every page.

```python
# Pagination
for payment in client.payments.list({"status": "succeeded", "limit": 100}).auto_paging_iter():
    ...

# Refunds
refund = client.refunds.create({"payment": payment.id, "amount": 5000, "reason": "requested_by_customer"})

# Payment links and control numbers
link = client.payment_links.create({"title": "Workshop ticket", "amount": 25000})
number = client.control_numbers.create({"payer_name": "Amina Juma", "title": "Term 2 fees", "amount": 450000})

# Transfers, balance, customers, events
transfer = client.transfers.create({"to": "merchant_shop", "amount": 5000})
balance = client.balance.get()
customer = client.customers.get("cus_…")
event = client.events.get("evt_…")

# Webhook endpoints (the secret is returned once)
endpoint = client.webhook_endpoints.create({"url": "https://example.com/paysafe", "events": ["payment.succeeded"]})
```

Async: `AsyncPaySafe` has the same surface with awaitable methods and `AsyncPage` (`async for item in page`). Both clients are context managers; pass your own `httpx.Client`/`httpx.AsyncClient` to reuse connection pools. `date`/`datetime` values are accepted wherever the API takes RFC 3339 timestamps.

Per-request options: `RequestOptions(idempotency_key=…, request_id=…, timeout=…, max_retries=…, headers={…})`. Retries: 429 and 503 wait for `Retry-After`; `idempotency_in_progress` waits one second; 5xx and network errors are retried only when the request is idempotent (GET, PATCH, DELETE, or a POST with an idempotency key). The SDK generates a UUID key for `payments.create`, `refunds.create`, `transfers.create` and `payments.cancel` when you do not pass one and exposes it on `obj.last_response.idempotency_key`; pass your own key derived from the order to survive process restarts.

Security: ids, filters, headers and amounts are validated before any request; path and query values are percent-encoded; the base URL must be https (plain http only for localhost); redirects are never followed; TLS verification stays on; response bodies are capped at 16 MB; the key never appears in exceptions or logs.

## Error handling

Every non-2xx response raises a subclass of `ApiError` chosen by the error code, with `status`, `code`, `request_id`, `param`, `details`, `doc_url`, `retry_after` and `rate_limit`:

```python
from paysafe_tz import (
    ApiConnectionError,
    ApiError,
    InvalidRequestError,
    InvalidStateError,
    RateLimitError,
    ValidationError,
)

try:
    client.payments.cancel(payment_id)
except ValidationError as e:  # 400: fix the request (e.param names the field)
    ...
except InvalidStateError as e:  # 409: read the object and decide again
    ...
except RateLimitError as e:  # 429 after retries: back off e.retry_after seconds
    ...
except ApiError as e:  # anything else from the API
    print(e)  # code (status) message [request_id]
except ApiConnectionError as e:  # no response at all (DNS, TLS, timeout)
    ...
except InvalidRequestError as e:  # rejected locally before any request was sent
    ...
```

Classes: ValidationError, AuthenticationError, PermissionDeniedError (`is_ip_not_allowed`, `observed_ip`), FeatureDisabledError, NotFoundError, InsufficientFundsError, ConflictError, IdempotencyConflictError, IdempotencyInProgressError, InvalidStateError, RateLimitError, ProviderError, ProviderUnavailableError, ServiceUnavailableError, InternalError, ApiConnectionError, ApiTimeoutError, ResponseTooLargeError, SignatureVerificationError, PollingTimeoutError, ConfigurationError, InvalidRequestError. Unknown codes map by HTTP status.

## Webhook integration

Verify the raw body before parsing it. `construct_event` checks the `PaySafe-Signature` header (HMAC-SHA256 over `t.body`, 300 s tolerance, constant-time comparison, several `v1=` values during rotation) and returns the event:

```python
from paysafe_tz import SignatureVerificationError, construct_event

try:
    event = construct_event(os.environ["PAYSAFE_WEBHOOK_SECRET"], raw_body, request.headers.get("PaySafe-Signature"))
except SignatureVerificationError:
    return Response(status=400)
if event["type"] == "payment.succeeded":
    mark_paid(event["data"]["object"]["reference"])  # deduplicate on event["id"] first
```

`verify_signature(...)` returns a boolean instead of raising; both accept a list of secrets. Handlers for FastAPI, Django and Flask are in `examples/webhooks/`, and `examples/verify_webhook.py` is a complete receiver on the standard library server.

## Testing

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
ruff check . && ruff format --check . && mypy && pytest
```

Unit, contract, network, security, webhook and async suites run offline against the fixtures in `tests/fixtures/` that are shared by every PaySafe SDK (HTTP is mocked with `httpx.MockTransport`). The integration suite runs only when `PAYSAFE_SECRET_KEY` holds a `paysafe_test_` key (and optionally `PAYSAFE_BASE_URL`); it refuses live keys and uses the sandbox phone suffixes documented at https://paysafe.co.tz/docs/sandbox.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report security issues as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
