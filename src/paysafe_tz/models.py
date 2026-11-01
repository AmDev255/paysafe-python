"""Typed shapes of request parameters. Responses are returned as ApiObject (a dict) with the same snake_case keys."""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import Any, Union

if sys.version_info >= (3, 11):
    from typing import Literal, NotRequired, TypedDict
else:
    from typing_extensions import Literal, NotRequired, TypedDict

Currency = Literal["TZS"]
PaymentChannel = Literal["mpesa", "tigopesa", "airtel", "halopesa"]
PaymentStatus = Literal[
    "created",
    "pending",
    "processing",
    "requires_action",
    "succeeded",
    "failed",
    "cancelled",
    "expired",
    "partially_refunded",
    "refunded",
]
RefundReason = Literal["requested_by_customer", "duplicate", "fraudulent", "other"]
RefundStatus = Literal["pending", "processing", "succeeded", "failed", "rejected"]
PaymentLinkStatus = Literal["active", "paused", "archived"]
ControlNumberStatus = Literal["active", "paid", "expired", "cancelled"]
ControlNumberState = Literal["unpaid", "partial", "paid", "overdue"]
ControlNumberMode = Literal["full", "instalment"]
WebhookEndpointStatus = Literal["ENABLED", "DISABLED"]
DateLike = Union[str, date, datetime]

PAYMENT_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "expired", "partially_refunded", "refunded"})
PAYMENT_SUCCESSFUL_STATUSES = frozenset({"succeeded", "partially_refunded", "refunded"})
REFUND_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "rejected"})
TRANSFER_TERMINAL_STATUSES = frozenset({"completed", "rejected", "reversed"})
CONTROL_NUMBER_TERMINAL_STATUSES = frozenset({"paid", "expired", "cancelled"})

EVENT_TYPES = (
    "payment.pending",
    "payment.processing",
    "payment.requires_action",
    "payment.succeeded",
    "payment.failed",
    "payment.expired",
    "payment.cancelled",
    "refund.pending",
    "refund.succeeded",
    "refund.failed",
    "payout.processing",
    "payout.paid",
    "payout.failed",
    "transfer.sent",
    "transfer.received",
    "transfer.in_review",
    "transfer.rejected",
    "transfer.reversed",
    "control_number.partially_paid",
    "control_number.paid",
    "control_number.expired",
    "control_number.cancelled",
)


def is_payment_terminal(payment: dict[str, Any]) -> bool:
    return payment.get("status") in PAYMENT_TERMINAL_STATUSES


def is_payment_successful(payment: dict[str, Any]) -> bool:
    return payment.get("status") in PAYMENT_SUCCESSFUL_STATUSES


def is_refund_terminal(refund: dict[str, Any]) -> bool:
    return refund.get("status") in REFUND_TERMINAL_STATUSES


def is_transfer_terminal(transfer: dict[str, Any]) -> bool:
    return transfer.get("status") in TRANSFER_TERMINAL_STATUSES


def is_control_number_terminal(number: dict[str, Any]) -> bool:
    return number.get("status") in CONTROL_NUMBER_TERMINAL_STATUSES


def balance_amount(items: list[dict[str, Any]], currency: str = "TZS") -> int:
    for item in items:
        if item.get("currency") == currency and isinstance(item.get("amount"), int):
            return int(item["amount"])
    return 0


class CustomerParams(TypedDict):
    phone: str
    name: NotRequired[str]
    email: NotRequired[str]


class CreatePaymentParams(TypedDict):
    amount: int
    customer: CustomerParams
    currency: NotRequired[Currency]
    reference: NotRequired[str]
    description: NotRequired[str]
    metadata: NotRequired[dict[str, Any]]
    expires_in: NotRequired[int]
    channel: NotRequired[PaymentChannel]


class ListPaymentsParams(TypedDict, total=False):
    limit: int
    cursor: str
    status: PaymentStatus
    reference: str
    customer_phone: str
    created_gte: DateLike
    created_lte: DateLike


class CreatePaymentLinkParams(TypedDict):
    title: str
    description: NotRequired[str]
    amount: NotRequired[int]
    min_amount: NotRequired[int]
    max_amount: NotRequired[int]
    currency: NotRequired[Currency]
    collect_name: NotRequired[bool]
    collect_email: NotRequired[bool]
    max_payments: NotRequired[int]
    expires_at: NotRequired[DateLike]
    success_message: NotRequired[str]
    redirect_url: NotRequired[str]
    logo: NotRequired[str]
    accent_color: NotRequired[str]


class UpdatePaymentLinkParams(TypedDict, total=False):
    title: str
    description: Union[str, None]
    max_payments: Union[int, None]
    expires_at: Union[DateLike, None]
    status: PaymentLinkStatus
    success_message: Union[str, None]
    redirect_url: Union[str, None]
    collect_name: bool
    collect_email: bool
    logo: Union[str, None]
    accent_color: Union[str, None]


class ListPaymentLinksParams(TypedDict, total=False):
    limit: int
    cursor: str
    status: PaymentLinkStatus


class InstalmentParams(TypedDict):
    amount: int
    due_at: DateLike


class CreateControlNumberParams(TypedDict):
    payer_name: str
    title: str
    amount: int
    payer_phone: NotRequired[str]
    payer_email: NotRequired[str]
    payer_reference: NotRequired[str]
    description: NotRequired[str]
    reference: NotRequired[str]
    payment_type: NotRequired[str]
    mode: NotRequired[ControlNumberMode]
    currency: NotRequired[Currency]
    expires_at: NotRequired[DateLike]
    notes: NotRequired[str]
    instalments: NotRequired[list[InstalmentParams]]
    metadata: NotRequired[dict[str, Any]]
    image: NotRequired[str]


class ListControlNumbersParams(TypedDict, total=False):
    limit: int
    cursor: str
    status: ControlNumberStatus
    state: ControlNumberState
    batch: str
    customer: str
    q: str


class CreateRefundParams(TypedDict):
    payment: str
    amount: NotRequired[int]
    reason: NotRequired[RefundReason]
    metadata: NotRequired[dict[str, Any]]


class ListRefundsParams(TypedDict, total=False):
    limit: int
    cursor: str
    payment: str
    status: RefundStatus


class ListParams(TypedDict, total=False):
    limit: int
    cursor: str


class ListCustomersParams(TypedDict, total=False):
    limit: int
    cursor: str
    search: str


class CreateTransferParams(TypedDict):
    to: str
    amount: int
    currency: NotRequired[Currency]
    note: NotRequired[str]


class CreateWebhookEndpointParams(TypedDict):
    url: str
    description: NotRequired[str]
    events: NotRequired[list[str]]


class UpdateWebhookEndpointParams(TypedDict, total=False):
    url: str
    description: Union[str, None]
    events: list[str]
    status: WebhookEndpointStatus


class ListEventsParams(TypedDict, total=False):
    limit: int
    cursor: str
    type: str
    from_: DateLike
    to: DateLike
    resourceId: str
