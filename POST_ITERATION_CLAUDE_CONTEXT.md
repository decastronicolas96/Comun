# Architecture & Iteration Context — Asistente de Transacciones (Común)

This document contains a comprehensive breakdown of the Común CX Transaction Helper application architecture, including the major iterations applied to its design, UX, and LLM constraints. Provide this file to Claude projects to quickly align the AI to the codebase.

## 1. Project Overview & Structure

The codebase is an agent-facing Streamlit application designed for Customer Experience (CX) agents. It aggregates raw transactional data, fetches API-enriched metadata, evaluates risk statuses via deterministic classification, and uses AI pipelines to translate highly technical and sensitive database records into empathetic, safe, and customer-ready Spanish text.

### Core File Map
- `app.py`: The main Streamlit entry point. Renders the Two-Panel UI (Diagnostic pane for internal data, Explanation pane for the customer-ready output). Handles input validation, layout construction, and the final state routing.
- `bucket_classifier.py`: The **deterministic brain**. LLMs do *not* determine resolution states; instead, this module maps raw error codes (e.g. `FRD_VEL`, `INV_ACC`, `CVV_MISMATCH`) into predefined operational action buckets (e.g., `security_review`, `system_retry`, `agent_escalation`).
- `llm_generator.py`: The dynamic translation layer. Invokes the primary generation model (`claude-sonnet-4`) to draft the copy, followed by an aggressive validation pass by the judge model (`gemini-2.5-flash`), backed by a secondary fallback model (`claude-3-5-haiku`).
- `bin_enrichment.py`: Caches and queries the API-Ninjas BIN endpoint to resolve external card issues, pushing payload metadata to Supabase.
- `templates.py`: A crucial optimization script. Around 67% of benign operations (`Completed` / `Pending`) route straight through this script using static template matching, avoiding LLM generation latency entirely.
- `audit_logger.py`: Commits every single interaction, AI generation context, and latency metric to the PostgreSQL layer for KPI tracking and LLM refinement.

## 2. Iterations & Rationales (Current State)

We implemented several massive architectural changes designed to maximize system uptime and empower human agents without compromising security boundaries.

### A. The "Unblinded Agent" Philosophy (UX Revision)
- **Previous state:** When an internal Común fraud rule (like `FRD_VEL` or `RISK_BLOCK`) triggered, the app purposely blinded the CX agent by wiping the error code and risk score from their screen, replacing it with a generic "🔍 Security Review" badge. 
- **The Issue:** Agents didn't have enough context to manage edge cases or identify the criticality of the block.
- **The Iteration:** We eliminated the frontend masking. The agent dashboard now displays the raw database variables to the CX team. However, to guarantee they follow protocol, the app injects an unmissable red alert banner (`🚨 ALERTA INTERNA: REQUIERE ESCALAMIENTO`) natively inside the diagnostic panel preventing them from modifying the resolution unprompted. The LLM still correctly strips all numerical fraud values from reaching the end customer.

### B. High-Availability LLM Judge (Architecture)
- **Previous state:** Output was graded strictly by `gemini-2.0-flash`. If the model encountered parsing issues or API timeouts, it triggered a hard `judge_error`, frustrating agents with raw JSON debugging data printed into the UI.
- **The Iteration:** Upgraded validation pipelines natively to `gemini-2.5-flash` to skirt deprecation. We then instituted a silent failover directly targeting `claude-3-5-haiku` as a backup judge. If Gemini fails, Haiku intercepts the prompt without dropping the operation, resulting in virtually 100% adherence uptime for our safety requirements. 

### C. UX Refinements (UI)
- **Naming Conventions:** Rebranded the application globally to `🏦 Asistente de Transacciones` aligning with the Hispanic native language requirements of the operations team.
- **Error JSON Removal:** Eliminated deep diagnostic JSON arrays completely from the CX workflow. CX Agents now receive a soft warning prompt (`💡 Esta explicación incluye análisis de IA. Te sugerimos validarla...`) rather than confusing debug data.
- **Regex Relaxation:** Refined validation logic permitting multiple hyphens to successfully parse the `TX-EXT-` database prefixes, restoring functionality for P2P transaction inquiries.

## 3. Operational Rules for Future Adjustments

If further modifications are deployed via this Claude Project, prioritize these rules:
1. **Never breach the LLM wall.** The customer text generation prompts must constantly forbid the mention of risk scores (`80-99`) and internal rules (`FRD_GEO`). 
2. **Deterministic first.** Only pass variables to the LLMs that require translation. Bucket assignments must forever remain mathematically bounded to the `bucket_classifier.py` mapping.
