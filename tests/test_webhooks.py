from __future__ import annotations

import pytest

from paysafe_tz import SignatureVerificationError, construct_event, sign, verify_signature

from .conftest import load

V = load("webhook-vector")
NOW = V["nowValid"]


def test_valid_signature_verifies() -> None:
    assert verify_signature(V["secret"], V["body"], V["header"], now=NOW)
    assert verify_signature(V["secret"], V["body"].encode(), V["header"], now=NOW)


def test_legacy_docs_vector_only_with_its_own_secret() -> None:
    header = f"t={V['timestamp']},v1={V['legacy']['signature']}"
    assert verify_signature(V["legacy"]["secret"], V["body"], header, now=NOW)
    assert not verify_signature(V["secret"], V["body"], header, now=NOW)


def test_wrong_secret_tampered_body_and_bad_headers_fail() -> None:
    assert not verify_signature("paysafe_webhook_test_wrong", V["body"], V["header"], now=NOW)
    assert not verify_signature(V["secret"], V["tamperedBody"], V["header"], now=NOW)
    assert not verify_signature(V["secret"], V["body"], None, now=NOW)
    assert not verify_signature(V["secret"], V["body"], "", now=NOW)
    assert not verify_signature(V["secret"], V["body"], f"v1={V['signature']}", now=NOW)
    assert not verify_signature(V["secret"], V["body"], f"t=abc,v1={V['signature']}", now=NOW)
    assert not verify_signature(V["secret"], V["body"], f"t={V['timestamp']}", now=NOW)


def test_tolerance_in_both_directions() -> None:
    assert not verify_signature(V["secret"], V["body"], V["header"], now=V["nowExpired"])
    assert not verify_signature(V["secret"], V["body"], V["header"], now=V["nowFuture"])
    assert verify_signature(V["secret"], V["body"], V["header"], tolerance=1000, now=V["nowExpired"])


def test_rotation_and_secret_lists() -> None:
    assert verify_signature(V["secret"], V["body"], V["rotation"]["header"], now=NOW)
    header = f"t={V['timestamp']},v1={V['secondSecret']['signature']}"
    assert verify_signature([V["secret"], V["secondSecret"]["secret"]], V["body"], header, now=NOW)
    assert not verify_signature([V["secret"]], V["body"], header, now=NOW)


def test_construct_event() -> None:
    event = construct_event(V["secret"], V["body"], V["header"], now=NOW)
    assert event.id == "evt_01J7A9R5VKM4N5P6R7S8T9V0B6"
    assert event["type"] == "payment.succeeded"
    assert event.livemode is False
    assert event["data"]["object"]["id"] == "pay_01J7A9Q0K3M4N5P6R7S8T9V0W1"


def test_construct_event_errors_carry_reason_without_secret() -> None:
    with pytest.raises(SignatureVerificationError) as info:
        construct_event(V["secret"], V["tamperedBody"], V["header"], now=NOW)
    assert info.value.reason == "signature_mismatch"
    assert V["secret"] not in str(info.value) and V["signature"] not in str(info.value)
    with pytest.raises(SignatureVerificationError) as info:
        construct_event(V["secret"], V["body"], V["header"], now=V["nowExpired"])
    assert info.value.reason == "timestamp_outside_tolerance"
    body = "[1,2,3]"
    with pytest.raises(SignatureVerificationError):
        construct_event(V["secret"], body, sign(V["secret"], body, V["timestamp"]), now=NOW)


def test_sign_matches_documented_header() -> None:
    assert sign(V["secret"], V["body"], V["timestamp"]) == V["header"]
