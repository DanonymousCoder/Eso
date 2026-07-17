"""
Service layer: keeps business logic and external calls out of views.

Tiered AI scoring pipeline:
  1. Local pickle model (fast, always available, tiny)
  2. Groq API (rich reasoning for flagged/edge cases)
  3. External ML service (team-mate's FastAPI endpoint, original default)

Each tier falls through to the next if unavailable.
"""
import logging
from datetime import datetime, timezone

import requests
from django.conf import settings

from .models import Transaction, BehaviorBaseline, LedgerEntry
from .ml_model import risk_model
from . import groq_client

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 0.7


class ScoringServiceError(Exception):
    """Raised when all scoring tiers are unreachable."""


def get_or_create_baseline(user_id: str) -> BehaviorBaseline:
    baseline, _created = BehaviorBaseline.objects.get_or_create(
        user_id=user_id,
        defaults={
            "typical_recipients": [],
            "typical_amount_min": 0,
            "typical_amount_max": 50000,
            "typical_hours": list(range(7, 22)),
            "known_devices": [],
        },
    )
    return baseline


def _recent_transaction_count(user_id: str) -> int:
    return Transaction.objects.filter(user_id=user_id).count()


def _tier1_local_pkl(transaction, baseline) -> dict | None:
    try:
        recent_count = _recent_transaction_count(transaction.user_id)
        result = risk_model.predict(transaction, baseline, recent_count)
        logger.info("Tier 1 (pkl): score=%.4f", result["risk_score"])
        return result
    except Exception as e:
        logger.warning("Tier 1 (pkl) failed: %s", e)
        return None


def _tier2_groq(transaction, baseline) -> dict | None:
    if not settings.GROQ_API_KEY:
        return None
    try:
        result = groq_client.analyze_transaction(transaction, baseline)
        if result:
            logger.info("Tier 2 (Groq): score=%.4f reason=%s", result["risk_score"], result["reason"])
        return result
    except Exception as e:
        logger.warning("Tier 2 (Groq) failed: %s", e)
        return None


def _tier3_external_ml(transaction, baseline) -> dict:
    payload = {
        "user_id": transaction.user_id,
        "recipient": transaction.recipient,
        "amount": float(transaction.amount),
        "device_id": transaction.device_id,
        "hour_of_day": datetime.now(timezone.utc).hour,
        "baseline": {
            "typical_recipients": baseline.typical_recipients,
            "typical_amount_min": float(baseline.typical_amount_min),
            "typical_amount_max": float(baseline.typical_amount_max),
            "typical_hours": baseline.typical_hours,
            "known_devices": baseline.known_devices,
        },
    }

    try:
        response = requests.post(
            settings.ML_SCORING_SERVICE_URL,
            json=payload,
            timeout=settings.ML_SERVICE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("Tier 3 (external ML) failed: %s", exc)
        raise ScoringServiceError(str(exc)) from exc

    if "risk_score" not in data:
        raise ScoringServiceError(f"Unexpected response from ML service: {data}")

    logger.info("Tier 3 (external ML): score=%.4f", float(data["risk_score"]))
    return {"risk_score": float(data["risk_score"]), "reason": data.get("reason", "")}


def score_transaction(transaction: Transaction) -> Transaction:
    baseline = get_or_create_baseline(transaction.user_id)

    result = _tier1_local_pkl(transaction, baseline)

    if result and result["risk_score"] >= RISK_THRESHOLD:
        groq_result = _tier2_groq(transaction, baseline)
        if groq_result:
            result = groq_result

    if result is None:
        try:
            result = _tier2_groq(transaction, baseline)
        except Exception:
            result = None

    if result is None:
        try:
            result = _tier3_external_ml(transaction, baseline)
        except ScoringServiceError:
            result = {
                "risk_score": 1.0,
                "reason": "Unable to verify this transaction automatically. Flagged for manual review.",
            }

    transaction.risk_score = result["risk_score"]
    transaction.risk_reason = result["reason"]
    transaction.scored_at = datetime.now(timezone.utc)
    transaction.status = (
        Transaction.Status.FLAGGED if result["risk_score"] >= RISK_THRESHOLD else Transaction.Status.APPROVED
    )
    transaction.save()

    source = "pkl" if risk_model.is_loaded() else "heuristic"
    if result.get("red_flags"):
        source = "groq"

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="flagged" if transaction.status == Transaction.Status.FLAGGED else "scored",
        detail=f"[{source}] risk_score={result['risk_score']:.2f}; {result['reason']}",
    )

    return transaction


def apply_user_decision(transaction: Transaction, decision: str) -> Transaction:
    if transaction.status != Transaction.Status.FLAGGED:
        raise ValueError("Only flagged transactions can be decided on.")

    transaction.status = (
        Transaction.Status.CONFIRMED if decision == "confirm" else Transaction.Status.CANCELLED
    )
    transaction.decided_at = datetime.now(timezone.utc)
    transaction.save()

    explanation = groq_client.explain_decision(transaction) if settings.GROQ_API_KEY else None
    detail = explanation or f"User chose to {decision} after being flagged."

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="overridden" if decision == "confirm" else "cancelled",
        detail=detail,
    )

    return transaction
