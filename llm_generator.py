"""LLM generation — Claude Sonnet (primary) + Gemini Flash (judge).

Claude generates empathetic Spanish explanations for error-case transactions.
Gemini validates the output against safety rules before it's shown to the agent.
"""

import json
import logging
import re

import anthropic
import google.generativeai as genai
import streamlit as st

from bucket_classifier import RESOLUTION_PATHS, FRAUD_CODES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un generador de explicaciones de soporte al cliente para Común, una plataforma de banca digital que sirve a inmigrantes hispanos en Estados Unidos. Escribes SOLO en español. Tus explicaciones son leídas o enviadas a los clientes por agentes de CX.

REGLAS — las violaciones son fallos críticos:
1. Escribe SOLO en español claro y empático. Sin inglés. Sin jerga técnica.
2. NUNCA menciones: puntajes de riesgo, códigos de fraude (FRD_VEL, FRD_GEO, RISK_BLOCK), notas internas, nombres de sistemas internos, o identificadores de códigos de error.
3. NUNCA nombres instituciones financieras externas (Chase, Citi, Capital One, JPMorgan, Citibank, o cualquier nombre de banco). Refiere a tarjetas externas como "tu otra tarjeta" o "la tarjeta externa".
4. Para casos de SECURITY_REVIEW: usa SOLO lenguaje genérico de "en revisión". No insinúes fraude, actividad sospechosa o riesgo.
5. Nunca culpes al cliente.
6. Sigue la estructura de salida exacta a continuación.

ESTRUCTURA DE SALIDA:
- **Qué pasó:** Una oración describiendo lo que sucedió.
- **Tu dinero está seguro:** Mensaje de tranquilidad (omitir solo si no aplica).
- **Qué hacer ahora:** Un paso específico y accionable.
- **Tiempo estimado:** Plazo concreto para la resolución."""


def _build_prompt(tx, bucket, resolution_category, bin_data):
    """Build the user message for Claude with transaction context."""
    from templates import _format_spanish_date

    formatted_date = _format_spanish_date(tx.get("timestamp"))
    card_info = "Común" if bin_data.get("is_comun") else "Tarjeta externa"

    lines = [
        "Datos de la transacción:",
        f"- ID: {tx['transaction_id']}",
        f"- Tipo: {tx.get('type', 'N/A')}",
        f"- Monto: ${tx.get('amount', 0)}",
        f"- Comercio/Destinatario: {tx.get('merchant_recipient', 'N/A')}",
        f"- Fecha: {formatted_date}",
        f"- Estado: {tx.get('status', 'N/A')}",
        f"- Tarjeta congelada: {'Sí' if tx.get('card_is_frozen') else 'No'}",
        f"- Tarjeta: {card_info}",
    ]

    # For non-fraud buckets, include internal context to help Claude generate better explanations
    if bucket not in ("SECURITY_REVIEW",):
        if tx.get("error_code"):
            lines.append(f"- Código de error: {tx['error_code']}")
        if tx.get("internal_note"):
            lines.append(f"- Nota interna: {tx['internal_note']}")

    resolution = RESOLUTION_PATHS.get(bucket, {})
    lines.extend([
        "",
        f"Clasificación: Bucket={bucket}, Categoría de resolución={resolution_category}",
        f"Ruta de resolución: {resolution.get('action', 'N/A')}",
        f"Plazo esperado: {resolution.get('timeframe', 'N/A')}",
        "",
        "Genera la explicación para el cliente siguiendo la estructura de salida. Sin preámbulo ni metadatos.",
    ])

    return "\n".join(lines)


def _call_claude(prompt):
    """Call Claude Sonnet to generate the customer explanation."""
    client = anthropic.Anthropic(
        api_key=st.secrets["ANTHROPIC_API_KEY"],
        timeout=30.0,
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


JUDGE_PROMPT_TEMPLATE = """Eres un validador de cumplimiento para una herramienta de soporte al cliente de banca digital. Recibirás una explicación dirigida al cliente en español y los datos originales de la transacción. Tu trabajo es verificar si la explicación viola alguna regla de seguridad.

Verifica TODOS los siguientes puntos. Responde SOLO con un objeto JSON.

VERIFICACIONES:
1. no_risk_scores: ¿La explicación contiene puntajes de riesgo numéricos o referencias a puntuación de riesgo? (true = seguro, false = violación)
2. no_fraud_codes: ¿La explicación contiene FRD_VEL, FRD_GEO, RISK_BLOCK, o palabras como "fraude", "sospechoso", "riesgo"? (true = seguro, false = violación)
3. no_internal_references: ¿La explicación hace referencia a sistemas internos, colas de revisión manual, umbrales de modelos o identificadores de códigos de error? (true = seguro, false = violación)
4. no_bank_names: ¿La explicación nombra alguna institución financiera específica (Chase, Citi, Capital One, JPMorgan, Citibank)? (true = seguro, false = violación)
5. is_spanish: ¿La explicación está escrita en español? (true = sí, false = no)
6. has_structure: ¿La explicación contiene secciones sobre qué pasó, siguiente paso y plazo? (true = sí, false = no)
7. empathetic_tone: ¿El tono es empático y no técnico, sin culpar al cliente? (true = sí, false = no)

EXPLICACIÓN A VALIDAR:
{explanation}

CÓDIGO DE ERROR ORIGINAL: {error_code}
BUCKET ORIGINAL: {bucket}

Responde SOLO con un objeto JSON, sin otro texto:
{{"no_risk_scores": true/false, "no_fraud_codes": true/false, "no_internal_references": true/false, "no_bank_names": true/false, "is_spanish": true/false, "has_structure": true/false, "empathetic_tone": true/false, "passed": true/false, "reason": "string o null"}}

"passed" debe ser true SOLO si TODAS las verificaciones individuales son true. Si alguna es false, "passed" debe ser false y "reason" debe explicar qué verificación(es) fallaron."""


def _call_gemini_judge(explanation, tx, bucket):
    """Call Gemini Flash to validate the generated explanation. Returns (passed, result_json_str)."""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            explanation=explanation,
            error_code=tx.get("error_code", "N/A"),
            bucket=bucket,
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0),
        )

        # Parse JSON from response — handle markdown code blocks and preamble
        response_text = response.text.strip()
        # Try extracting JSON from markdown code block first
        code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
        if code_block_match:
            response_text = code_block_match.group(1).strip()
        else:
            # Try extracting a raw JSON object
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0).strip()

        result = json.loads(response_text)
        return result.get("passed", False), json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"Gemini judge failed: {e}")
        return False, "judge_error"


def _call_haiku_judge(explanation, tx, bucket):
    """Fallback judge using Claude 3.5 Haiku when Gemini fails."""
    try:
        client = anthropic.Anthropic(
            api_key=st.secrets["ANTHROPIC_API_KEY"],
            timeout=15.0,
        )
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            explanation=explanation,
            error_code=tx.get("error_code", "N/A"),
            bucket=bucket,
        )
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        
        response_text = response.content[0].text.strip()
        code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
        if code_block_match:
            response_text = code_block_match.group(1).strip()
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0).strip()

        result = json.loads(response_text)
        return result.get("passed", False), json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Haiku judge fallback failed: {e}")
        return False, "judge_error"


def generate_explanation(tx, bucket, resolution_category, bin_data):
    """Generate a customer explanation using Claude + Gemini judge.

    Returns dict with keys:
        explanation: str or None (None if Claude failed)
        judge_passed: bool or None
        judge_result: str
        prompt_sent: str
        raw_response: str or None
    """
    prompt = _build_prompt(tx, bucket, resolution_category, bin_data)

    # Call Claude Sonnet
    try:
        raw_response = _call_claude(prompt)
    except Exception as e:
        logger.warning(f"Claude generation failed for {tx.get('transaction_id')}: {e}")
        return {
            "explanation": None,
            "judge_passed": None,
            "judge_result": "llm_error",
            "prompt_sent": prompt,
            "raw_response": None,
        }

    # Call Gemini Flash judge
    judge_passed, judge_result = _call_gemini_judge(raw_response, tx, bucket)

    # Fallback to Haiku if Gemini fails
    if judge_result == "judge_error":
        logger.info("Gemini judge failed, falling back to Haiku")
        judge_passed, judge_result = _call_haiku_judge(raw_response, tx, bucket)

    return {
        "explanation": raw_response,
        "judge_passed": judge_passed,
        "judge_result": judge_result,
        "prompt_sent": prompt,
        "raw_response": raw_response,
    }
