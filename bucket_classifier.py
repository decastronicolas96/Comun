"""Deterministic bucket classification for transactions.

The LLM NEVER decides the bucket. This module classifies based on error_code and status.
"""

FRAUD_CODES = {"FRD_VEL", "FRD_GEO", "RISK_BLOCK"}

RESOLUTION_PATHS = {
    "CARD_LOCK": {
        "action": "Reactivar tarjeta en la app",
        "timeframe": "Inmediato",
    },
    "INSUFFICIENT_FUNDS_EXT": {
        "action": "Verificar fondos o usar otra tarjeta",
        "timeframe": "Reintento inmediato",
    },
    "EXPIRED_CARD_EXT": {
        "action": "Actualizar tarjeta o usar otra",
        "timeframe": "Inmediato",
    },
    "CVV_MISMATCH_EXT": {
        "action": "Verificar código de seguridad",
        "timeframe": "Reintento inmediato",
    },
    "3DS_FAILED_EXT": {
        "action": "Reintentar y completar verificación",
        "timeframe": "Reintento inmediato",
    },
    "R01_INSUFFICIENT": {
        "action": "Agregar fondos a la cuenta",
        "timeframe": "Inmediato después del depósito",
    },
    "NETWORK_TIMEOUT": {
        "action": "Esperar e intentar de nuevo",
        "timeframe": "15-30 minutos",
    },
    "INV_ACC": {
        "action": "Equipo trabajando en resolverlo",
        "timeframe": "1-2 días hábiles",
    },
    "R03": {
        "action": "Equipo revisando el caso",
        "timeframe": "1-2 días hábiles",
    },
    "SECURITY_REVIEW": {
        "action": "Transacción bajo revisión",
        "timeframe": "24-48 horas",
    },
    "UNKNOWN": {
        "action": "Equipo revisando el caso",
        "timeframe": "1-2 días hábiles",
    },
}


def classify_bucket(tx):
    """Deterministic bucket classification. Returns (bucket_name, resolution_category)."""
    error = tx.get("error_code")
    status = tx.get("status")

    # No-error states
    if status == "Completed":
        return "COMPLETED", "none"
    if status == "Pending":
        return "PENDING", "none"

    # Self-service buckets
    if error == "CARD_LOCK":
        return "CARD_LOCK", "self_service"
    if error == "INSUFFICIENT_FUNDS":
        return "INSUFFICIENT_FUNDS_EXT", "self_service"
    if error == "EXPIRED_CARD":
        return "EXPIRED_CARD_EXT", "self_service"
    if error == "CVV_MISMATCH":
        return "CVV_MISMATCH_EXT", "self_service"
    if error == "3DS_FAILED":
        return "3DS_FAILED_EXT", "self_service"
    if error == "R01":
        return "R01_INSUFFICIENT", "self_service"

    # System retry
    if error == "NETWORK_TIMEOUT":
        return "NETWORK_TIMEOUT", "system_retry"

    # Agent escalation
    if error == "INV_ACC":
        return "INV_ACC", "agent_escalation"
    if error == "R03":
        return "R03", "agent_escalation"

    # Security review (fraud) — NEVER expose details
    if error in FRAUD_CODES:
        return "SECURITY_REVIEW", "security_review"

    # Fallback for unknown error codes
    return "UNKNOWN", "agent_escalation"
