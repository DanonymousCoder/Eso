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


def update_baseline_from_transaction(transaction: Transaction) -> BehaviorBaseline:
    """
    Expand the user's learned profile after a transfer completes safely
    (auto-approved or user-confirmed after a flag).
    """
    baseline = get_or_create_baseline(transaction.user_id)
    amount = float(transaction.amount)
    changed = False

    recipient = transaction.recipient.strip()
    if recipient and recipient not in baseline.typical_recipients:
        recipients = list(baseline.typical_recipients) + [recipient]
        baseline.typical_recipients = recipients[-25:]
        changed = True

    if transaction.device_id and transaction.device_id not in baseline.known_devices:
        devices = list(baseline.known_devices) + [transaction.device_id]
        baseline.known_devices = devices[-10:]
        changed = True

    current_min = float(baseline.typical_amount_min)
    current_max = float(baseline.typical_amount_max)
    if amount < current_min or current_min == 0:
        baseline.typical_amount_min = amount
        changed = True
    if amount > current_max:
        baseline.typical_amount_max = amount
        changed = True

    hour = (
        transaction.created_at.hour
        if transaction.created_at
        else datetime.now(timezone.utc).hour
    )
    if hour not in baseline.typical_hours:
        baseline.typical_hours = sorted(set(baseline.typical_hours) | {hour})
        changed = True

    if changed:
        baseline.save(update_fields=[
            "typical_recipients",
            "known_devices",
            "typical_amount_min",
            "typical_amount_max",
            "typical_hours",
            "updated_at",
        ])
        logger.info("Baseline updated for user %s", transaction.user_id)

    return baseline


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

    # Tier 1: fast local heuristic/pkl (always runs — gives us a score immediately)
    tier1 = _tier1_local_pkl(transaction, baseline)

    # Tier 2: Groq LLM — runs for EVERY transaction to get real, specific reasoning.
    # We always try Groq so approved transactions don't get generic messages either.
    groq_result = _tier2_groq(transaction, baseline)

    if groq_result:
        # Use Groq's score if it agrees directionally, otherwise blend: Groq
        # reasoning with the fast tier-1 score as a sanity anchor.
        result = groq_result
        if tier1 and abs(groq_result["risk_score"] - tier1["risk_score"]) > 0.35:
            # Large disagreement — average them to avoid runaway LLM scores
            blended = (groq_result["risk_score"] + tier1["risk_score"]) / 2
            result = {**groq_result, "risk_score": round(blended, 4)}
    elif tier1:
        result = tier1
    else:
        # Both tier 1 and Groq failed — fall through to external ML
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

    if groq_result:
        source = "groq"
    elif risk_model.is_loaded():
        source = "pkl"
    else:
        source = "heuristic"

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="flagged" if transaction.status == Transaction.Status.FLAGGED else "scored",
        detail=f"[{source}] risk_score={result['risk_score']:.2f}; {result['reason']}",
    )

    if transaction.status == Transaction.Status.APPROVED:
        update_baseline_from_transaction(transaction)

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

    if decision == "confirm":
        update_baseline_from_transaction(transaction)

    return transaction
