import pytest
from templates import _format_spanish_date, _format_amount, render_template

def test_format_spanish_date():
    # Valid date format with Z
    assert _format_spanish_date("2026-01-20T12:55:00Z") == "20 de enero de 2026"
    assert _format_spanish_date("2025-12-30T21:51:00Z") == "30 de diciembre de 2025"

    # Valid short strings
    assert _format_spanish_date("2026-04-14") == "14 de abril de 2026"
    
    # Invalid strings fallback gracefully
    assert _format_spanish_date(None) == "fecha no disponible"
    assert _format_spanish_date("") == "fecha no disponible"
    assert _format_spanish_date("invalid_date_format") == "fecha no disponible"

def test_format_amount():
    assert _format_amount(1022.76) == "1,022.76"
    assert _format_amount("500") == "500.00"
    assert _format_amount(0) == "0.00"
    assert _format_amount("invalid") == "0.00"
    assert _format_amount(None) == "0.00"

def test_render_template():
    tx = {
        "amount": 141.75,
        "merchant_recipient": "Employer Payroll LLC",
        "timestamp": "2025-12-15T21:51:00Z"
    }

    # Completed template
    completed_res = render_template("COMPLETED", tx)
    assert "fue procesada exitosamente el 15 de diciembre de 2025" in completed_res
    assert "$141.75" in completed_res
    assert "Employer Payroll LLC" in completed_res

    # Pending template
    pending_res = render_template("PENDING", tx)
    assert "está siendo procesada" in pending_res
    assert "$141.75" in pending_res

    # Missing bucket gives None
    assert render_template("UNKNOWN_BUCKET", tx) is None

    # Fallback to zeros and 'desconocido'
    tx_empty = {}
    empty_res = render_template("COMPLETED", tx_empty)
    assert "$0.00" in empty_res
    assert "desconocido" in empty_res
    assert "fecha no disponible" in empty_res
