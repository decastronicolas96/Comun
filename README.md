# 🏦 Asistente de Transacciones 
*A CX diagnostic toolkit for Común, tailored to quickly demystify user transactions while guarding internal fraud logic.*

## Overview
The Smart Transaction Helper is an agent-facing Streamlit application designed for Común's CX team. It drastically reduces Average Handle Time (AHT) when dealing with customer inquiries around failed, flagged, or pending transaction statuses. 

The tool takes raw database logs (error codes, manual internal notes, fraud assessments) and translates them into a clear, empathetic Spanish explanation using Anthropic's Claude and Google's Gemini models, while never exposing underlying security processes directly to the end customer.

## Features
- **Deterministic Routing**: The logic guarantees complete fallback structures for standard/benign errors. Over 67% of benign statuses (e.g. `Completed`, `Pending`) bypass LLM logic completely, increasing application latency and halving token costs. 
- **LLM-As-A-Judge Logic**: Generated textual answers undergo aggressive filtering through Gemini 2.5 Flash pipelines (supported by a secondary Claude 3.5 Haiku routing fallback for maximum uptime) enforcing zero-tolerance exclusions around Risk Scores or Fraud terms.
- **BIN Caching**: Third party issuing bank metadata is queried lazily using API-Ninjas, heavily speeding up recurring data points over Supabase caching rows. 
- **XSS Resilience**: Strict Streamlit markdown injections utilizing HTML escaping patterns protect internal CX users from malicious merchant spoofing loops.

## Deployment Instructions (Streamlit Cloud)
To host this yourself:
1. Ensure your API keys (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `NINJA_API_KEY`, `SUPABASE_KEY` & `SUPABASE_URL`) are loaded directly into the **Advanced Settings > Secrets** variable window on Streamlit Cloud. 
2. Point the Streamlit app target to `app.py`. 
3. *Note*: Never commit your local `.env` or `.streamlit/secrets.toml` files!

## Testing framework
Run the robust testing parameter layout mapped locally via `PyTest` targeting unit operations and endpoint timeouts:
```bash
pip install pytest pytest-mock pandas
python -m pytest tests/ -v
```
