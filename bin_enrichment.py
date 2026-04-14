"""BIN enrichment — lazy API lookup with Supabase caching.

Calls the BIN API only when a transaction has a non-null BIN that hasn't been enriched yet.
Results are cached in Supabase to avoid repeated API calls.
"""

import logging
import requests
import streamlit as st

logger = logging.getLogger(__name__)


def _call_bin_api(bin_code):
    """Call the api-ninjas BIN API. Returns enrichment dict or None on failure."""
    try:
        response = requests.get(
            f"https://api.api-ninjas.com/v2/bin?bin={bin_code}",
            headers={"X-Api-Key": st.secrets["BIN_API_KEY"]},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "issuer": data.get("issuer", "Unknown"),
            "brand": data.get("brand"),
            "type": data.get("type"),
            "country": data.get("country"),
            "categories": data.get("categories"),
        }
    except Exception as e:
        logger.warning(f"BIN API call failed for {bin_code}: {e}")
        return None


def get_bin_data(tx, supabase_client):
    """Lazy BIN enrichment with Supabase caching.

    Returns dict with keys: issuer, brand, type, country, is_comun
    """
    # No BIN → Común card
    if tx.get("bin") is None:
        return {"issuer": "Común", "brand": None, "type": None, "country": None, "is_comun": True}

    # Already cached in Supabase?
    if tx.get("bin_issuer") is not None:
        return {
            "issuer": tx["bin_issuer"],
            "brand": tx.get("bin_brand"),
            "type": tx.get("bin_type"),
            "country": tx.get("bin_country"),
            "is_comun": False,
        }

    # Call BIN API
    result = _call_bin_api(tx["bin"])

    if result is None:
        # API failed — return fallback, do NOT cache bad data
        return {"issuer": "Unknown", "brand": None, "type": None, "country": None, "is_comun": False}

    # Cache in Supabase
    try:
        supabase_client.table("transactions").update({
            "bin_issuer": result["issuer"],
            "bin_brand": result["brand"],
            "bin_type": result["type"],
            "bin_country": result["country"],
            "bin_categories": result.get("categories"),
            "bin_is_common_card": False,
        }).eq("transaction_id", tx["transaction_id"]).execute()
    except Exception as e:
        logger.warning(f"Failed to cache BIN data for {tx['transaction_id']}: {e}")

    return {
        "issuer": result["issuer"],
        "brand": result["brand"],
        "type": result["type"],
        "country": result["country"],
        "is_comun": False,
    }
