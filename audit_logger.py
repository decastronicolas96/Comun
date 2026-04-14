"""Audit logging — writes every query to the audit_log table.

Never crashes the main flow. Failures are logged as warnings.
"""

import logging

logger = logging.getLogger(__name__)


def log_query(supabase_client, tx_id, bucket, prompt_sent, llm_response, judge_result, judge_passed, latency_ms, agent_id="unknown_agent"):
    """Log a transaction query to the audit_log table."""
    try:
        supabase_client.table("audit_log").insert({
            "transaction_id": tx_id,
            "bucket": bucket,
            "prompt_sent": prompt_sent,
            "llm_response": llm_response,
            "judge_result": judge_result,
            "judge_passed": judge_passed,
            "latency_ms": latency_ms,
            "agent_id": agent_id,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to write audit log for {tx_id}: {e}")
