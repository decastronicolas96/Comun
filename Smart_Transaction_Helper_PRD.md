# Smart Transaction Helper — Product Requirements Document

**Author:** Nicolás De Castro | **Date:** April 2026 | **Version:** MVP

---

## 1. Problem Statement

Común's CX team manually investigates dozens of daily inquiries about transaction statuses. Agents dig through raw database logs — error codes, risk scores, internal notes — and must interpret technical data, then translate it into clear, empathetic Spanish explanations. This is slow, inconsistent across agents, and error-prone.

The end customer is a Hispanic immigrant navigating digital banking, often for the first time. Failed or confusing transactions carry high emotional stakes — a bad support experience can erode trust in the entire system.

## 2. Users

**Primary user: CX Agent.** Receives a customer inquiry (call, chat, email), looks up the transaction, verifies the AI-generated explanation against source data, and communicates it to the customer.

**End audience: Común customer.** Spanish-speaking, likely underbanked/unbanked, transitioning from cash-based to digital financial systems. Needs to know: what happened, is my money safe, and what do I do next.

The customer does not interact with this tool directly. This is an agent-facing tool whose output is designed for customer communication.

## 3. Design Principles

1. **The user is a CX agent, the audience is a vulnerable customer.** Every output must be safe to communicate directly to the customer.
2. **Never expose internal risk logic.** Risk scores, fraud flags, and internal notes inform the AI's reasoning but never appear in the customer-facing explanation.
3. **Protect third-party financial information.** BIN enrichment data (external bank names, card types) is for agent diagnostics only.
4. **Trust is the product.** Every explanation must be empathetic, clear, and actionable.
5. **Spanish-first, plain language.** No technical jargon. Written for someone new to digital banking.
6. **Structured buckets over open-ended LLM interpretation.** The AI works within predefined transaction categories to reduce hallucination and ensure consistency.
7. **Agent sees full context, customer sees safe context.** The UI distinguishes diagnostic information from what gets communicated.

## 4. Data Analysis Summary

**Dataset:** 300 transactions across 6 types (Remittance, POS Purchase, Subscription, P2P, ATM Withdrawal, Direct Deposit).

**Status distribution:** Completed (174), Failed (47), Pending (29), Declined (27), Flagged (23).

**Key structural findings:**

- Failed and Declined share identical error codes and internal notes. The distinction is technical (authorization rejected vs. processing failed), not experiential. From the customer's perspective, they are the same.
- Flagged is not exclusively fraud — it includes CARD_LOCK, R01, R03, and INV_ACC alongside FRD_VEL and FRD_GEO. The error code drives the explanation, not the status.
- External cards (BIN present) only appear on P2P and Remittance transactions. All other types use the Común card.
- Completed and Pending transactions have no error codes. Pending transactions all share the same note: "Awaiting clearing house response."

**BIN enrichment (3 external card issuers in dataset):**

| BIN | Issuer | Brand | Type |
|-----|--------|-------|------|
| 517805 | Capital One | Mastercard | Credit |
| 542418 | Citibank | Mastercard | Credit |
| 414720 | JPMorgan Chase | Visa | Credit |
| null | Común card | — | — |

**BIN API rationale:** Primary value is the agent diagnostic panel — issuer name, card brand, and type help agents verify customer claims and troubleshoot. No value for the customer-facing explanation (Principle #3). Secondary value is operational pattern detection in future iterations.

**BIN enrichment architecture:** Enrichment happens at runtime (lazy), not at data load. When an agent looks up a transaction with a non-null BIN: if the BIN has already been enriched (cached in Supabase), use the cached data. If not, call the BIN API, store the result in Supabase, and display it. This means the system handles new BINs it has never seen before without re-running a batch process. The BIN API key lives only in Streamlit secrets — it never touches the codebase or the data load pipeline.

## 5. Transaction Buckets and Resolution Paths

The error code is the primary driver of the customer explanation, not the transaction status. Each bucket maps to a resolution category.

### Self-Service — Customer can resolve immediately

**CARD_LOCK** — Customer's Común card is frozen in the app. 100% correlation with card_is_frozen = TRUE, risk score = 0. Resolution: reactivate in the app. Timeframe: immediate.

**INSUFFICIENT_FUNDS (external card)** — External card lacks sufficient balance. Resolution: check balance on the funding card or use a different one. Timeframe: immediate retry.

**EXPIRED_CARD (external card)** — External card has expired. Resolution: update card or use a different one. Timeframe: immediate.

**CVV_MISMATCH (external card)** — Security code entered incorrectly. Resolution: re-enter the correct 3-digit code. Timeframe: immediate retry.

**3DS_FAILED (external card)** — 3D Secure verification not completed. Resolution: retry and complete the verification step. Timeframe: immediate retry.

**R01 (Común card)** — ACH return: insufficient funds in the Común account. Resolution: add funds to the account. Timeframe: immediate after deposit.

### System Retry — Temporary issue, no customer action needed

**NETWORK_TIMEOUT (external card)** — Connection timed out between Común and the external card network. Not the customer's fault. Resolution: wait and retry. Timeframe: 15-30 minutes.

### Agent Escalation — Requires internal team intervention

**INV_ACC (Común card)** — Banking partner cannot validate the account. Agent escalates to ops/banking team. Customer message: "Our team is working on resolving this." Timeframe: 1-2 business days.

**R03 (Común card)** — ACH return: account not found at the banking layer. Agent escalates to ops/banking team. Timeframe: 1-2 business days.

### Security Review — Fraud team handles internally

**FRD_VEL (Común card)** — Velocity fraud detection. Risk scores 80-99. Always Flagged status. Customer told: "Your transaction is under review." Never mention fraud detection. Timeframe: 24 hours.

**FRD_GEO (Común card)** — Geographic fraud detection. Risk scores 81-99. Always Flagged status. Same customer communication as FRD_VEL. Timeframe: 24 hours.

**RISK_BLOCK (external card)** — Internal risk engine blocked the transaction. Customer told: "This transaction could not be processed. Our team is reviewing it." Timeframe: 24-48 hours.

### No Error — Normal states

**PENDING** — Transaction awaiting clearing house. Normal processing, no error. Customer message: "Your transaction is being processed, no action needed." Timeframe: 1-3 business days.

**COMPLETED** — Transaction settled. Confirmation message only.

## 6. Agent Visibility Rules

For **non-fraud error codes** (CARD_LOCK, INSUFFICIENT_FUNDS, EXPIRED_CARD, CVV_MISMATCH, 3DS_FAILED, NETWORK_TIMEOUT, R01, R03, INV_ACC): agents see the raw error code, internal note, and all transaction details. Full transparency — this is their diagnostic source.

For **fraud/security cases** (FRD_VEL, FRD_GEO, RISK_BLOCK): agents now see FULLY UNMASKED diagnostics including raw risk scores, fraud model codes, and internal notes. Instead of blinding the agent, the diagnostic panel injects a prominent `🚨 ALERTA INTERNA: REQUIERE ESCALAMIENTO` banner that forces them to follow Level 2 fraud routing. The LLM still safely protects the customer-facing text, maintaining our security boundary.

The agent uses the diagnostic panel as a citation source — they compare the raw data against the AI-generated explanation before communicating it. This is the same verification pattern as a human reviewing RAG output against source documents.

## 7. UI Architecture

### Agent Flow (single flow, all paths)

1. Agent receives customer inquiry.
2. Agent inputs Transaction ID into the Smart Transaction Helper.
3. Tool displays two sections simultaneously:
   - **Diagnostic Panel:** Transaction ID, timestamp, type, amount, merchant/recipient, status, error code (sanitized for fraud), card info (Común or external + BIN data), card frozen status.
   - **AI-Generated Explanation:** Customer-facing message in Spanish following the explanation template.
4. Agent verifies the AI output against the diagnostic data.
5. Agent communicates the explanation to the customer (copy button for MVP).

### Customer Explanation Template

Every AI-generated message follows a consistent structure with variable content per bucket:

1. **What happened** — One sentence describing the outcome in plain Spanish.
2. **Is my money safe** — Reassurance where applicable.
3. **What to do next** — Specific, actionable step (self-service instruction or "our team is handling it").
4. **When to expect resolution** — Concrete timeframe.

Not every bucket requires all four parts. Completed transactions only need part 1. The structure gives the LLM a consistent framework while allowing appropriate variation.

## 8. Prompt Strategy

The LLM receives the full transaction data (including risk scores and internal notes) as input but is instructed to generate output only within the customer explanation template. The prompt enforces:

- Bucket identification based on error code and status.
- Explanation generated in Spanish, plain language, empathetic tone.
- Never surface risk scores, fraud codes, internal notes, or external bank names in the output.
- Always include the appropriate resolution path and timeframe for the identified bucket.
- For fraud/security cases, use only the generic "under review" language.

The structured bucket approach means the LLM is not doing open-ended interpretation of raw logs. It identifies which bucket the transaction falls into and generates the explanation within that bucket's constraints. This reduces hallucination risk and ensures consistency.

## 9. Guardrails

### 9.1 Output Validation (LLM-as-Judge)

A fast, cheap LLM (e.g., Gemini 2.5 Flash, supported by a secondary Claude 3.5 Haiku fallback) runs as a validation layer between the primary LLM's output and what the agent sees. It checks every generated explanation against a set of binary rules before the response is displayed:

- **No risk score leakage.** Does the explanation contain any numeric risk values or references to scoring?
- **No fraud code leakage.** Does the explanation mention FRD_VEL, FRD_GEO, RISK_BLOCK, or any variation of fraud detection terminology?
- **No internal note leakage.** Does the explanation reference internal systems, manual review queues, or risk engine logic?
- **No external bank name leakage.** Does the explanation name a specific financial institution (Chase, Citi, Capital One, etc.)?
- **Language compliance.** Is the output in Spanish?
- **Template completeness.** Does the output include the required sections for its bucket (what happened, money safety, next step, timeframe)?
- **Tone check.** Is the tone empathetic and non-technical? No jargon, no blame.

If any check fails, the judge flags the explanation. The agent sees the diagnostic panel normally but the AI explanation is preceded with a soft warning: "💡 Esta explicación incluye análisis de IA. Te sugerimos validarla brevemente con el panel de diagnóstico antes de enviarla." The agent can still compose their own response using the diagnostic data, but the json outputs are stripped to minimize confusion. This ensures the tool never degrades the customer experience — worst case, it falls back to the pre-tool workflow.

The judge adds minimal latency (~300-500ms) and costs a fraction of the primary generation call. The Haiku fallback protects the system against downstream API errors.

### 9.2 Deterministic Override for Simple Cases

Completed and Pending transactions produce the same explanation every time. There is no ambiguity for the LLM to resolve. These bypass the LLM entirely and use hardcoded templates populated with transaction variables (amount, merchant, date). This eliminates hallucination risk for 67% of the dataset, reduces cost, and improves latency.

The LLM is only invoked for Failed, Declined, and Flagged transactions where the error code and context require interpretation and the empathetic framing benefits from natural language generation.

### 9.3 Input Validation

Transaction IDs must match the expected format (TX-[alphanumeric]) before any database query is executed. Invalid inputs return an immediate error to the agent without hitting the database or the LLM.

### 9.4 Fallback Handling

If the LLM call fails (timeout, rate limit, service outage), the agent still sees the full diagnostic panel. The AI explanation section displays: "Explicación automática no disponible. Usa la información de diagnóstico para responder al cliente." The tool degrades gracefully — the agent has all the source data they need to compose a response manually.

### 9.5 Audit Logging

Every AI-generated explanation is logged alongside: the transaction ID, the raw data passed to the LLM, the full prompt, the generated output, the judge's validation result, and a timestamp. If a customer disputes what they were told, Común can trace the exact explanation that was generated and the data it was based on. This also provides the training data for future model improvements.

### 9.6 Prompt Injection Protection

The LLM receives only structured transaction data from the database — never raw user input. The Transaction ID is validated and used only as a database lookup key. The agent cannot modify or append to the LLM prompt. This design eliminates the prompt injection surface by construction.

## 10. Success Metrics

### 10.1 Business Metrics — Is this creating value?

**Average Handle Time (AHT) reduction.** Primary business metric. Measures the time from when an agent starts investigating a transaction inquiry to when the customer receives an explanation. Target: 40-60% reduction from current baseline. Measured by comparing pre-tool and post-tool AHT for transaction status inquiries.

**Customer Satisfaction (CSAT) for transaction inquiries.** Post-interaction survey score for conversations where the tool was used. Target: improvement over current baseline. Isolate to transaction status inquiries specifically, not overall CSAT.

**First Contact Resolution (FCR) rate.** Percentage of transaction inquiries resolved without follow-up. The tool should increase FCR because explanations include actionable next steps and timeframes, reducing "what do I do now?" callbacks. Target: 80%+ FCR for self-service error buckets.

**Inquiry volume deflection (V2).** Once the tool is proven with agents, self-service can deflect a portion of transaction inquiries entirely. Not measurable in MVP but establishes the baseline.

### 10.2 Operational Metrics — Is the agent workflow working?

**Tool adoption rate.** Percentage of transaction status inquiries where the agent uses the tool vs. manual investigation. Target: 90%+ within 30 days of launch. Low adoption signals UX friction or trust issues.

**Explanation acceptance rate.** How often the agent uses the AI-generated explanation as-is (copy) vs. modifying it. High modification rates signal prompt quality issues or bucket misclassification.

**Escalation accuracy.** For agent-escalation buckets (INV_ACC, R03), does the agent escalate to the correct team? For security-review buckets (FRD_VEL, FRD_GEO, RISK_BLOCK), does the agent follow the protocol (no disclosure)? Measured through escalation logs and QA review.

**Guardrail flag rate.** How often the LLM-as-judge blocks an explanation. A high flag rate means the primary prompt needs tuning. A zero flag rate after stabilization means the guardrail is working but should be periodically tested with adversarial inputs. Target: <5% flag rate after the first iteration.

### 10.3 Technical Metrics — Is the system healthy?

**End-to-end latency.** Time from TX ID input to full result displayed (diagnostic panel + AI explanation). Target: <3 seconds. Breakdown: database lookup (<200ms), BIN API call if uncached (~350ms, cached <100ms), LLM generation (~1-2s), judge validation (~300ms).

**LLM cost per query.** Total cost of primary generation + judge validation per transaction lookup. Track separately for LLM-routed queries (error cases) vs. template-routed queries (Completed/Pending). Target: establish baseline in first week, optimize from there.

**Uptime and error rate.** Tool availability and percentage of queries that result in a system error (not a guardrail flag — actual failures). Target: 99.5% uptime, <1% error rate.

**Fallback activation rate.** How often the LLM fails and the agent sees the fallback message. Target: <2%. A rising rate signals infrastructure or provider issues.

## 11. Assumptions

- **SLA timeframes are estimated.** Actual clearing times, escalation SLAs, and fraud review turnaround times are assumptions based on industry standards. These should be validated with Común's operations team.
- **No existing compliance language for fraud cases.** We designed a conservative "generic under review" approach. If Común has specific disclosure policies, the prompt should be updated.
- **Agent cannot override fraud decisions.** The tool assumes fraud-flagged transactions are handled exclusively by the fraud/compliance team.
- **MVP scope is explanation only.** Follow-up question handling, decision-tree scripts for agents, and auto-send integrations are out of scope. The agent copies the explanation manually.
- **BIN enrichment is lazy and cached.** The system calls the BIN API on first lookup for each unique BIN and caches the result in Supabase. This avoids batch pre-processing and handles new BINs automatically.

## 12. Out of Scope (V2 Considerations)

- Customer self-service portal (direct transaction lookup without agent).
- Follow-up script generation for common customer questions.
- Operational dashboards: error patterns by issuer, decline rate trends, fraud flag volume.
- Auto-detection of stale pending transactions (pending beyond expected clearing time).
- Agent feedback loop on AI explanation quality.
- Multi-channel delivery (auto-send via chat, email, SMS).
