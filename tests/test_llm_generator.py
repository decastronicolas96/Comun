import pytest
import google.generativeai as genai
import streamlit as st
import llm_generator
import json

# Set up mock secrets
st.secrets = {
    "ANTHROPIC_API_KEY": "dummy",
    "GEMINI_API_KEY": "dummy_or_real"
}

def test_build_prompt():
    tx = {
        "transaction_id": "TX-123456",
        "type": "POS Purchase",
        "amount": 100.50,
        "merchant_recipient": "Walmart",
        "timestamp": "2025-12-16T21:51:00Z",
        "status": "Failed",
        "card_is_frozen": False,
        "error_code": "INSUFFICIENT_FUNDS",
        "internal_note": "A note",
    }
    bin_data = {"is_comun": False}
    bucket = "INSUFFICIENT_FUNDS_EXT"
    resolution_category = "self_service"

    prompt = llm_generator._build_prompt(tx, bucket, resolution_category, bin_data)
    
    assert "TX-123456" in prompt
    assert "Walmart" in prompt
    assert "Tarjeta externa" in prompt
    assert "INSUFFICIENT_FUNDS" in prompt
    assert "A note" in prompt
    assert "Verificar fondos o usar otra tarjeta" in prompt

def test_build_prompt_security_review():
    tx = {
        "transaction_id": "TX-999",
        "type": "POS Purchase",
        "amount": 500,
        "merchant_recipient": "BestBuy",
        "timestamp": "2025-12-16T21:51:00Z",
        "status": "Flagged",
        "card_is_frozen": False,
        "error_code": "FRD_VEL",
        "internal_note": "High risk score (98).",
        "risk_score": 98
    }
    bin_data = {"is_comun": True}
    bucket = "SECURITY_REVIEW"
    resolution_category = "security_review"

    prompt = llm_generator._build_prompt(tx, bucket, resolution_category, bin_data)
    
    auth_check = True
    assert "TX-999" in prompt
    assert "Común" in prompt
    
    # Critical Check: Fraud codes and internal notes MUST be excluded from prompt
    assert "FRD_VEL" not in prompt
    assert "High risk score" not in prompt
    assert "98" not in prompt
    assert "Transacción bajo revisión" in prompt

# Mock the _call_claude block to use a dummy successful execution for rapid unit testing
def test_generate_explanation_mocked(mocker):
    mocker.patch('llm_generator._call_claude', return_value="Tu transacción falló. Tu dinero está seguro. Revisa tu saldo. Inmediato.")
    mocker.patch('llm_generator._call_gemini_judge', return_value=(True, '{"passed": true}'))

    tx = {"transaction_id": "TX-A12", "timestamp": "2025-10-10"}
    res = llm_generator.generate_explanation(tx, "INSUFFICIENT_FUNDS_EXT", "self_service", {})
    
    assert res["explanation"] == "Tu transacción falló. Tu dinero está seguro. Revisa tu saldo. Inmediato."
    assert res["judge_passed"] is True
    assert res["judge_result"] == '{"passed": true}'

def test_gemini_judge_json_parsing(mocker):
    # Test valid JSON extraction with markdown blocks
    class DummyResponse:
        def __init__(self, text):
            self.text = text

    # Simulate Gemini returning padded output
    mocked_gemini_text = "Aquí está mi evaluación.\n```json\n{\"passed\": true, \"reason\": \"Todo correcto\"}\n```\nFin de la comunicación."
    mock_model = mocker.MagicMock()
    mock_model.generate_content.return_value = DummyResponse(mocked_gemini_text)
    mocker.patch('google.generativeai.GenerativeModel', return_value=mock_model)

    passed, result_str = llm_generator._call_gemini_judge("Test", {"error_code":"R01"}, "R01_INSUFFICIENT")
    
    assert passed is True
    parsed = json.loads(result_str)
    assert parsed["passed"] is True
    assert parsed["reason"] == "Todo correcto"

def test_gemini_judge_json_parsing_invalid(mocker):
    # Test invalid json extraction (fallback)
    class DummyResponse:
        def __init__(self, text):
            self.text = text

    mocked_gemini_text = "Not a json block anywhere"
    mock_model = mocker.MagicMock()
    mock_model.generate_content.return_value = DummyResponse(mocked_gemini_text)
    mocker.patch('google.generativeai.GenerativeModel', return_value=mock_model)

    passed, result_str = llm_generator._call_gemini_judge("Test", {}, "UNKNOWN")
    
    # Expected to fail since json.loads will fail
    assert passed is False
    assert result_str == "judge_error"

