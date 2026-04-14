"""Smart Transaction Helper — Streamlit app for Común's CX team.

Agent-facing tool: input a Transaction ID, see diagnostic data + AI-generated Spanish explanation.
"""

import html
import re
import time

import streamlit as st
from supabase import create_client

from bucket_classifier import classify_bucket, FRAUD_CODES, RESOLUTION_PATHS
from templates import render_template
from bin_enrichment import get_bin_data
from llm_generator import generate_explanation
from audit_logger import log_query

# --- Page config ---
st.set_page_config(
    page_title="Smart Transaction Helper",
    page_icon="🏦",
    layout="wide",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .explanation-box {
        background-color: #f0f7ff;
        color: #333;
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #1a73e8;
        margin-top: 0.5rem;
    }
    .diagnostic-header {
        color: #333;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 0.5rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
        margin-bottom: 0.1rem;
    }
    .metric-value {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .status-completed { color: #0a8f3c; }
    .status-pending { color: #b8860b; }
    .status-failed { color: #d32f2f; }
    .status-declined { color: #d32f2f; }
    .status-flagged { color: #e65100; }
    .security-badge {
        background-color: #fff3e0;
        color: #e65100;
        padding: 0.3rem 0.8rem;
        border-radius: 4px;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# --- Supabase client (cached) ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# --- Helper: sanitize transaction for diagnostic display ---
def sanitize_for_display(tx, bucket):
    """Return a display-safe copy of the transaction. Hides fraud details."""
    display = dict(tx)
    if bucket == "SECURITY_REVIEW":
        display["error_code"] = "Security Review"
        display["risk_score"] = None
        display["internal_note"] = None
    return display


def esc(value):
    """HTML-escape a value for safe rendering in st.markdown with unsafe_allow_html."""
    if value is None:
        return "N/A"
    return html.escape(str(value))


def get_status_class(status):
    """Return CSS class for status coloring."""
    return f"status-{status.lower()}" if status else ""


# --- UI ---
st.title("🏦 Smart Transaction Helper")
st.caption("Herramienta de diagnóstico para el equipo CX de Común")

# Input form
with st.form("tx_form"):
    tx_id_input = st.text_input(
        "Transaction ID",
        placeholder="TX-ABC123",
        help="Formato: TX- seguido de caracteres alfanuméricos",
    )
    submitted = st.form_submit_button("Buscar transacción", use_container_width=True)

if submitted:
    tx_id = tx_id_input.strip()

    # --- Input validation ---
    if not tx_id:
        st.error("Por favor ingresa un Transaction ID.")
        st.stop()

    if not re.match(r"^TX-[A-Za-z0-9]+$", tx_id):
        st.error("Formato inválido. El ID debe comenzar con TX- seguido de caracteres alfanuméricos.")
        st.stop()

    # --- Query Supabase ---
    with st.spinner("Consultando transacción..."):
        start_time = time.time()

        try:
            supabase = init_supabase()
            response = supabase.table("transactions").select("*").eq("transaction_id", tx_id).execute()
        except Exception as e:
            st.error(f"Error de conexión con la base de datos. Intenta de nuevo.")
            st.stop()

        if not response.data:
            st.warning(f"Transacción **{tx_id}** no encontrada.")
            st.stop()

        tx = response.data[0]

        # --- Classify bucket ---
        bucket, resolution_category = classify_bucket(tx)

        # --- BIN enrichment ---
        bin_data = get_bin_data(tx, supabase)

        # --- Generate explanation ---
        is_template = False
        template_text = render_template(bucket, tx)

        if template_text is not None:
            # Template route — no LLM
            is_template = True
            explanation_text = template_text
            judge_passed = True
            judge_result = "template_bypass"
            prompt_sent = None
            raw_response = template_text
        else:
            # LLM route
            result = generate_explanation(tx, bucket, resolution_category, bin_data)
            explanation_text = result["explanation"]
            judge_passed = result["judge_passed"]
            judge_result = result["judge_result"]
            prompt_sent = result["prompt_sent"]
            raw_response = result["raw_response"]

        # --- Calculate latency ---
        latency_ms = int((time.time() - start_time) * 1000)

        # --- Audit log ---
        log_query(
            supabase_client=supabase,
            tx_id=tx_id,
            bucket=bucket,
            prompt_sent=prompt_sent,
            llm_response=raw_response,
            judge_result=judge_result,
            judge_passed=judge_passed,
            latency_ms=latency_ms,
        )

    # --- Render two-panel layout ---
    st.divider()
    col1, col2 = st.columns(2, gap="large")

    # === LEFT: Diagnostic Panel ===
    with col1:
        st.subheader("📋 Panel de Diagnóstico")

        display_tx = sanitize_for_display(tx, bucket)

        # Transaction info
        st.markdown("**Información de la transacción**")

        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown(f'<div class="metric-label">Transaction ID</div><div class="metric-value">{esc(display_tx["transaction_id"])}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Tipo</div><div class="metric-value">{esc(display_tx.get("type"))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Monto</div><div class="metric-value">${display_tx.get("amount", 0):,.2f}</div>', unsafe_allow_html=True)
        with info_col2:
            status = display_tx.get("status", "N/A")
            status_class = get_status_class(status)
            st.markdown(f'<div class="metric-label">Estado</div><div class="metric-value {status_class}">{esc(status)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Comercio/Destinatario</div><div class="metric-value">{esc(display_tx.get("merchant_recipient"))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Fecha</div><div class="metric-value">{esc(display_tx.get("timestamp"))}</div>', unsafe_allow_html=True)

        # Card info
        st.markdown("---")
        st.markdown("**Información de tarjeta**")
        card_frozen = "🔒 Sí" if display_tx.get("card_is_frozen") else "✅ No"
        st.markdown(f'<div class="metric-label">Tarjeta congelada</div><div class="metric-value">{card_frozen}</div>', unsafe_allow_html=True)

        if not bin_data.get("is_comun"):
            bin_col1, bin_col2, bin_col3 = st.columns(3)
            with bin_col1:
                st.markdown(f'<div class="metric-label">Emisor</div><div class="metric-value">{esc(bin_data.get("issuer"))}</div>', unsafe_allow_html=True)
            with bin_col2:
                st.markdown(f'<div class="metric-label">Marca</div><div class="metric-value">{esc(bin_data.get("brand"))}</div>', unsafe_allow_html=True)
            with bin_col3:
                st.markdown(f'<div class="metric-label">Tipo</div><div class="metric-value">{esc(bin_data.get("type"))}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-label">Tarjeta</div><div class="metric-value">Común</div>', unsafe_allow_html=True)

        # Error info (sanitized for fraud)
        if display_tx.get("error_code"):
            st.markdown("---")
            st.markdown("**Información del error**")

            if bucket == "SECURITY_REVIEW":
                st.markdown('<div class="security-badge">🔍 Security Review</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-label">Código de error</div><div class="metric-value">{esc(display_tx.get("error_code"))}</div>', unsafe_allow_html=True)
                if display_tx.get("internal_note"):
                    st.markdown(f'<div class="metric-label">Nota interna</div><div class="metric-value">{esc(display_tx.get("internal_note"))}</div>', unsafe_allow_html=True)
                if display_tx.get("risk_score") is not None:
                    st.markdown(f'<div class="metric-label">Risk Score</div><div class="metric-value">{esc(display_tx.get("risk_score"))}</div>', unsafe_allow_html=True)

        # Resolution info
        resolution = RESOLUTION_PATHS.get(bucket, {})
        if resolution:
            st.markdown("---")
            st.markdown("**Resolución**")
            st.markdown(f'<div class="metric-label">Categoría</div><div class="metric-value">{resolution_category}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Acción</div><div class="metric-value">{resolution.get("action", "N/A")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">Plazo</div><div class="metric-value">{resolution.get("timeframe", "N/A")}</div>', unsafe_allow_html=True)

        # Latency info
        st.markdown("---")
        st.caption(f"⏱️ Latencia: {latency_ms}ms | 🪣 Bucket: {bucket} | {'📄 Template' if is_template else '🤖 LLM'}")

    # === RIGHT: Explanation Panel ===
    with col2:
        st.subheader("💬 Explicación para el Cliente")

        if explanation_text is None:
            # LLM failed
            st.warning("⚠️ Explicación automática no disponible. Usa la información de diagnóstico para responder al cliente.")
        elif judge_passed is False and not is_template:
            # Judge failed or flagged
            st.warning("⚠️ La explicación generada requiere revisión manual.")
            with st.expander("Ver explicación generada (no validada)", expanded=False):
                st.markdown(f'<div class="explanation-box">{esc(explanation_text)}</div>', unsafe_allow_html=True)
        else:
            # Success — show explanation
            st.markdown(f'<div class="explanation-box">{esc(explanation_text)}</div>', unsafe_allow_html=True)
            st.text("")
            # Copy-friendly version
            st.text_area(
                "Copiar texto (selecciona todo y copia):",
                value=explanation_text,
                height=200,
                label_visibility="collapsed",
            )

        # Judge details (collapsed by default)
        if not is_template and judge_result and judge_result not in ("template_bypass",):
            with st.expander("🔍 Detalles de validación"):
                st.json(judge_result if isinstance(judge_result, dict) else {"result": judge_result})
