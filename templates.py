"""Hardcoded Spanish templates for Completed and Pending transactions.

These bypass the LLM entirely — 67% of transactions use these.
"""

from datetime import datetime

SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

TEMPLATES = {
    "COMPLETED": "Tu transacción de ${amount} a {merchant} fue procesada exitosamente el {date}. No se requiere ninguna acción.",
    "PENDING": "Tu transacción de ${amount} a {merchant} está siendo procesada. Esto es normal y no requiere ninguna acción de tu parte. Tu dinero está seguro. El tiempo estimado de procesamiento es de 1 a 3 días hábiles.",
}


def _format_spanish_date(timestamp_str):
    """Format a timestamp string into a readable Spanish date."""
    if not timestamp_str:
        return "fecha no disponible"
    try:
        dt = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
        month_name = SPANISH_MONTHS[dt.month]
        return f"{dt.day} de {month_name} de {dt.year}"
    except (ValueError, TypeError):
        return "fecha no disponible"


def _format_amount(amount):
    """Format amount as currency string."""
    try:
        return f"{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "0.00"


def render_template(bucket, tx):
    """Render a hardcoded template for the given bucket. Returns None if bucket has no template."""
    template = TEMPLATES.get(bucket)
    if template is None:
        return None

    return template.format(
        amount=_format_amount(tx.get("amount", 0)),
        merchant=tx.get("merchant_recipient", "desconocido"),
        date=_format_spanish_date(tx.get("timestamp")),
    )
