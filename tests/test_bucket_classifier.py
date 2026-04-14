import pytest
from bucket_classifier import classify_bucket, FRAUD_CODES

def test_classify_bucket_no_error():
    # Test Completed
    bucket, auth = classify_bucket({"status": "Completed"})
    assert bucket == "COMPLETED"
    assert auth == "none"
    
    # Test Pending
    bucket, auth = classify_bucket({"status": "Pending"})
    assert bucket == "PENDING"
    assert auth == "none"

def test_classify_bucket_self_service():
    # CARD_LOCK
    bucket, auth = classify_bucket({"status": "Failed", "error_code": "CARD_LOCK"})
    assert bucket == "CARD_LOCK"
    assert auth == "self_service"

    # INSUFFICIENT_FUNDS
    bucket, auth = classify_bucket({"status": "Failed", "error_code": "INSUFFICIENT_FUNDS"})
    assert bucket == "INSUFFICIENT_FUNDS_EXT"
    
    # 3DS_FAILED
    bucket, auth = classify_bucket({"status": "Failed", "error_code": "3DS_FAILED"})
    assert bucket == "3DS_FAILED_EXT"

    # R01
    bucket, auth = classify_bucket({"status": "Declined", "error_code": "R01"})
    assert bucket == "R01_INSUFFICIENT"

def test_classify_bucket_system_retry():
    bucket, auth = classify_bucket({"status": "Failed", "error_code": "NETWORK_TIMEOUT"})
    assert bucket == "NETWORK_TIMEOUT"
    assert auth == "system_retry"

def test_classify_bucket_agent_escalation():
    bucket, auth = classify_bucket({"status": "Declined", "error_code": "INV_ACC"})
    assert bucket == "INV_ACC"
    assert auth == "agent_escalation"

def test_classify_bucket_fraud():
    # Test all fraud codes
    for code in FRAUD_CODES:
        bucket, auth = classify_bucket({"status": "Flagged", "error_code": code})
        assert bucket == "SECURITY_REVIEW"
        assert auth == "security_review"

def test_classify_bucket_fallback():
    bucket, auth = classify_bucket({"status": "Failed", "error_code": "WEIRD_ERROR_CODE_90X"})
    assert bucket == "UNKNOWN"
    assert auth == "agent_escalation"
