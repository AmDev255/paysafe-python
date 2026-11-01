"""Django view for PaySafe webhooks.

urls.py:  path("paysafe/webhook", paysafe_webhook)
settings.py: PAYSAFE_WEBHOOK_SECRET = os.environ["PAYSAFE_WEBHOOK_SECRET"]
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from paysafe_tz import SignatureVerificationError, construct_event


@csrf_exempt
@require_POST
def paysafe_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = construct_event(settings.PAYSAFE_WEBHOOK_SECRET, request.body, request.headers.get("PaySafe-Signature"))
    except SignatureVerificationError:
        return HttpResponseBadRequest("invalid signature")
    # Store event["id"] (unique) before acting so retried deliveries are no-ops.
    if event["type"] == "payment.succeeded":
        payment = event["data"]["object"]
        _ = payment.get("reference")  # mark the order as paid
    return HttpResponse("ok")
