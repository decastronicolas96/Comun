# Smart Transaction Helper — Complete Build Context

This document contains EVERYTHING needed to build the Streamlit app. Read it fully before writing any code.

---

## PART 1: SECURITY — READ FIRST

### .gitignore (CREATE BEFORE FIRST COMMIT)
```
.env
.streamlit/secrets.toml
__pycache__/
*.pyc
```

### API Keys Architecture
- `.env` is for local development only, never committed
- `.streamlit/secrets.toml` is for Streamlit deployment, never committed
- In Streamlit Cloud, keys go in Settings > Secrets dashboard

### Keys needed in `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://vxbujnfgyvfnedphidxc.supabase.co"
SUPABASE_KEY = "your_service_role_secret_key"
BIN_API_KEY = "your_api_ninjas_key"
ANTHROPIC_API_KEY = "your_anthropic_key"
GEMINI_API_KEY = "your_gemini_key"
```

Access in code: `st.secrets["SUPABASE_URL"]` — never `os.getenv()` in the Streamlit app.

---

## PART 2: ARCHITECTURE

```
Supabase (PostgreSQL) — ALREADY SET UP, 300 rows loaded
├── transactions table (raw data, BIN enrichment columns null until first lookup)
├── audit_log table (logs every query for KPI tracking)

Streamlit App (TO BUILD)
├── Frontend: two-panel UI (diagnostic panel + AI explanation)
├── Backend logic:
│   ├── Input validation (TX ID format: TX-[alphanumeric])
│   ├── Supabase query (fetch transaction by ID)
│   ├── BIN enrichment (lazy: call API only if bin_issuer is null, cache result in Supabase)
│   ├── Bucket classification (DETERMINISTIC Python if/else — NOT the LLM)
│   ├── Route: Completed/Pending → hardcoded Spanish template (NO LLM)
│   ├── Route: Error cases → Claude Sonnet (primary LLM generation)
│   ├── Judge: Gemini Flash (validate output against safety rules)
│   ├── Log everything to audit_log table
│   └── Display result

External APIs
├── BIN API: https://api.api-ninjas.com/v2/bin?bin={bin} (header: X-Api-Key)
├── Anthropic API: Claude Sonnet — primary LLM for generating Spanish explanations
└── Google Gemini API: Flash — judge LLM for output validation
```

### Supabase Schema (already created and populated)
```sql
CREATE TABLE transactions (
  transaction_id TEXT PRIMARY KEY,
  timestamp TIMESTAMPTZ,
  type TEXT,
  merchant_recipient TEXT,
  amount NUMERIC,
  status TEXT,
  error_code TEXT,
  internal_note TEXT,
  risk_score INTEGER,
  card_is_frozen BOOLEAN,
  bin TEXT,
  bin_issuer TEXT,        -- null until first BIN API lookup
  bin_brand TEXT,         -- null until first BIN API lookup
  bin_type TEXT,          -- null until first BIN API lookup
  bin_country TEXT,       -- null until first BIN API lookup
  bin_is_common_card BOOLEAN DEFAULT TRUE,
  bin_categories TEXT     -- null until first BIN API lookup
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  transaction_id TEXT,
  bucket TEXT,
  prompt_sent TEXT,
  llm_response TEXT,
  judge_result TEXT,
  judge_passed BOOLEAN,
  latency_ms INTEGER,
  agent_id TEXT
);
```

---

## PART 3: BUCKET CLASSIFICATION LOGIC (DETERMINISTIC)

The LLM NEVER decides what bucket a transaction belongs to. Python code does this based on error_code and status. The LLM only generates the empathetic Spanish explanation AFTER we know the bucket.

```python
def classify_bucket(tx):
    """Deterministic bucket classification. Returns bucket name and resolution category."""
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
    if error in ("FRD_VEL", "FRD_GEO", "RISK_BLOCK"):
        return "SECURITY_REVIEW", "security_review"
    
    # Fallback for unknown error codes
    return "UNKNOWN", "agent_escalation"
```

---

## PART 4: HARDCODED TEMPLATES (NO LLM — for Completed and Pending)

These bypass the LLM entirely. 67% of all transactions use these.

```python
TEMPLATES = {
    "COMPLETED": "Tu transacción de ${amount} a {merchant} fue procesada exitosamente el {date}. No se requiere ninguna acción.",
    "PENDING": "Tu transacción de ${amount} a {merchant} está siendo procesada. Esto es normal y no requiere ninguna acción de tu parte. Tu dinero está seguro. El tiempo estimado de procesamiento es de 1 a 3 días hábiles."
}
```

---

## PART 5: LLM PROMPT STRATEGY (for error cases only)

### Primary LLM: Claude Sonnet
The prompt receives the full transaction data (including risk scores and internal notes) but is instructed to NEVER include them in the output.

The prompt must:
1. Receive the bucket classification (already determined by Python)
2. Receive the transaction data as context
3. Generate a customer explanation in Spanish following this template:
   - What happened (1 sentence, plain Spanish)
   - Is my money safe (reassurance where applicable)
   - What to do next (specific actionable step)
   - When to expect resolution (concrete timeframe)
4. NEVER mention: risk scores, fraud codes, internal notes, external bank names
5. For SECURITY_REVIEW bucket: use ONLY generic "under review" language
6. Tone: empathetic, clear, no jargon, no blame

### Resolution paths per bucket (include in prompt context):
- CARD_LOCK → "Reactivar tarjeta en la app" / Immediate
- INSUFFICIENT_FUNDS_EXT → "Verificar fondos o usar otra tarjeta" / Immediate retry
- EXPIRED_CARD_EXT → "Actualizar tarjeta o usar otra" / Immediate
- CVV_MISMATCH_EXT → "Verificar código de seguridad" / Immediate retry
- 3DS_FAILED_EXT → "Reintentar y completar verificación" / Immediate retry
- R01_INSUFFICIENT → "Agregar fondos a la cuenta" / Immediate after deposit
- NETWORK_TIMEOUT → "Esperar e intentar de nuevo" / 15-30 minutes
- INV_ACC → "Equipo trabajando en resolverlo" / 1-2 business days
- R03 → "Equipo revisando el caso" / 1-2 business days
- SECURITY_REVIEW → "Transacción bajo revisión" / 24-48 hours

### Judge LLM: Gemini Flash
Runs AFTER primary generation. Binary checks:
1. No risk score numbers in output?
2. No fraud codes (FRD_VEL, FRD_GEO, RISK_BLOCK) in output?
3. No internal system references in output?
4. No external bank names (Chase, Citi, Capital One, JPMorgan) in output?
5. Output is in Spanish?
6. Template sections present (what happened, next step, timeframe)?
7. Tone is empathetic and non-technical?

If ANY check fails → flag the explanation. Show agent: "La explicación generada requiere revisión manual."

---

## PART 6: UI ARCHITECTURE

### Two-panel layout:

**Panel 1: Diagnostic Panel (Agent's source data)**
Shows for ALL transactions:
- Transaction ID, timestamp, type, amount, merchant/recipient
- Status (Completed, Pending, Failed, Declined, Flagged)
- Card frozen: yes/no

Shows for non-fraud error codes (CARD_LOCK, INSUFFICIENT_FUNDS, EXPIRED_CARD, CVV_MISMATCH, 3DS_FAILED, NETWORK_TIMEOUT, R01, R03, INV_ACC):
- Raw error code
- Internal note

Shows for fraud/security cases (FRD_VEL, FRD_GEO, RISK_BLOCK):
- Error category: "Security Review" (NOT the raw code)
- NO risk scores, NO fraud model codes, NO internal notes with thresholds

Shows for external card transactions (bin is not null):
- BIN issuer, brand, type (from BIN API / cached)

**Panel 2: AI-Generated Explanation (Customer-facing)**
- Spanish text following the explanation template
- Copy button for the agent to grab the text
- Visual distinction from the diagnostic panel (different background, clear label like "Explicación para el cliente")

### Fallback states:
- LLM fails → diagnostic panel shows normally, explanation area shows: "Explicación automática no disponible. Usa la información de diagnóstico para responder al cliente."
- Judge fails validation → diagnostic panel shows normally, explanation area shows: "La explicación generada requiere revisión manual."
- Invalid TX ID → error message, no panels shown

---

## PART 7: BIN ENRICHMENT FLOW (RUNTIME)

```python
def get_bin_data(tx, supabase_client):
    """Lazy BIN enrichment with Supabase caching."""
    if tx["bin"] is None:
        return {"issuer": "Común", "brand": None, "type": None, "is_comun": True}
    
    # Already cached?
    if tx["bin_issuer"] is not None:
        return {"issuer": tx["bin_issuer"], "brand": tx["bin_brand"], 
                "type": tx["bin_type"], "is_comun": False}
    
    # Call BIN API
    result = call_bin_api(tx["bin"])  # uses st.secrets["BIN_API_KEY"]
    
    # Cache in Supabase
    supabase_client.table("transactions").update({
        "bin_issuer": result["issuer"],
        "bin_brand": result["brand"],
        "bin_type": result["type"],
        "bin_country": result["country"],
        "bin_categories": result["categories"],
        "bin_is_common_card": False
    }).eq("transaction_id", tx["transaction_id"]).execute()
    
    return {"issuer": result["issuer"], "brand": result["brand"], 
            "type": result["type"], "is_comun": False}
```

---

## PART 8: AUDIT LOGGING

Every transaction lookup logs to the audit_log table:

```python
def log_query(supabase_client, tx_id, bucket, prompt, response, judge_result, judge_passed, latency_ms):
    supabase_client.table("audit_log").insert({
        "transaction_id": tx_id,
        "bucket": bucket,
        "prompt_sent": prompt,
        "llm_response": response,
        "judge_result": judge_result,
        "judge_passed": judge_passed,
        "latency_ms": latency_ms,
    }).execute()
```

For template-routed transactions (Completed/Pending), log with prompt_sent=None and judge_result="template_bypass".

---

## PART 9: AGENT VISIBILITY RULES — CRITICAL

This is the most important security rule in the app:

**For fraud/security error codes (FRD_VEL, FRD_GEO, RISK_BLOCK):**
- Agent sees error category as "Security Review" — NOT the raw code
- Agent does NOT see risk_score
- Agent does NOT see internal_note
- The diagnostic panel actively hides these fields for security cases

**For all other error codes:**
- Agent sees everything: raw error code, internal note, risk score, all transaction details

Implement this as a sanitization step BEFORE rendering the diagnostic panel, not as a CSS/display trick.

---

## PART 10: FILE STRUCTURE

```
comun-cx/
├── .gitignore              # MUST include .env and .streamlit/secrets.toml
├── .streamlit/
│   └── secrets.toml        # local secrets (gitignored)
├── app.py                  # main Streamlit app
├── bucket_classifier.py    # deterministic bucket logic
├── llm_generator.py        # Claude Sonnet prompt + Gemini judge
├── bin_enrichment.py       # BIN API + Supabase caching
├── audit_logger.py         # audit log writes
├── templates.py            # hardcoded Spanish templates for Completed/Pending
├── load_transactions.py    # data load script (already done)
├── comun_transactions__Sheet1.csv  # source data
├── requirements.txt        # pandas, supabase, streamlit, anthropic, google-generativeai, requests
└── README.md
```
