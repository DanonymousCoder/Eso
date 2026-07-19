"""
Service layer: keeps business logic and external calls out of views.

Tiered AI scoring pipeline:
  1. Local pickle model (fast, always available, tiny) — runs first for a quick signal.
  2. Groq LLM (rich, data-driven reasoning) — runs for EVERY transaction so even
     safe transfers get a human-readable explanation, not a generic heuristic string.
  3. External ML service (team-mate's FastAPI endpoint) — fallback if both above fail.

Each tier falls through to the next if unavailable.
"""
import logging
import math
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone

from django.utils import timezone as django_timezone
from django.db import transaction as db_transaction

import requests
from django.conf import settings

from .models import (
    Transaction,
    BehaviorBaseline,
    LedgerEntry,
    RecipientReport,
    SecurityReview,
)
from .ml_model import risk_model
from . import groq_client

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 0.7
CRITICAL_RISK_THRESHOLD = 0.9
DEMO_COOLDOWN_SECONDS = 30

REFLECTION_PROMPTS = [
    "In your own words, what is this payment for?",
    "Has anyone contacted you today asking you to send this money? Explain what happened.",
    "How do you personally know the person or business receiving this payment?",
]

REFLECTION_RED_FLAG_PHRASES = [
    "someone told me",
    "someone asked me",
    "he told me",
    "she told me",
    "he said",
    "she said",
    "asked me to",
    "instructed me",
    "on the phone",
    "phone call",
    "whatsapp",
    "investment return",
    "urgent transfer",
]


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


def recipient_report_summary(recipient_account_id: str) -> dict:
    account_id = (recipient_account_id or "").strip()
    if not account_id:
        return {"report_count": 0, "reasons": []}

    reports = RecipientReport.objects.filter(recipient_account_id=account_id)
    reason_counts = Counter(reports.values_list("reason", flat=True))
    return {
        "report_count": reports.count(),
        "reasons": [
            {"reason": reason, "count": count}
            for reason, count in reason_counts.most_common()
        ],
    }


def _apply_recipient_network_signal(result: dict, transaction: Transaction) -> dict:
    summary = recipient_report_summary(transaction.recipient_account_id)
    report_count = summary["report_count"]
    score = float(result["risk_score"])
    reason = result.get("reason", "").strip()

    if report_count >= 3:
        score = max(score, 0.92)
        network_reason = (
            f"Eso's shared safety network has {report_count} independent reports "
            "about this beneficiary account"
        )
    elif report_count == 2:
        score = min(1.0, score + 0.30)
        network_reason = "Two other Eso users have reported this beneficiary account"
    elif report_count == 1:
        score = min(1.0, score + 0.18)
        network_reason = "Another Eso user has reported this beneficiary account"
    else:
        network_reason = ""

    if network_reason:
        reason = f"{reason}; {network_reason}" if reason else network_reason

    return {
        **result,
        "risk_score": round(min(max(score, 0.0), 1.0), 4),
        "reason": reason,
        "network_report_count": report_count,
        "network_report_reasons": summary["reasons"],
    }


def _risk_tier(score: float) -> str:
    if score >= CRITICAL_RISK_THRESHOLD:
        return Transaction.RiskTier.CRITICAL
    if score >= RISK_THRESHOLD:
        return Transaction.RiskTier.HIGH
    return Transaction.RiskTier.LOW


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
        django_timezone.localtime(transaction.created_at).hour
        if transaction.created_at
        else django_timezone.localtime(django_timezone.now()).hour
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
        "hour_of_day": django_timezone.localtime(transaction.created_at).hour if transaction.created_at else django_timezone.localtime(django_timezone.now()).hour,
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
        result = groq_result
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

    result = _apply_recipient_network_signal(result, transaction)
    tier = _risk_tier(float(result["risk_score"]))

    transaction.risk_score = result["risk_score"]
    transaction.risk_tier = tier
    transaction.risk_reason = result["reason"]
    transaction.network_report_count = result["network_report_count"]
    transaction.scored_at = datetime.now(timezone.utc)
    transaction.status = (
        Transaction.Status.FLAGGED if result["risk_score"] >= RISK_THRESHOLD else Transaction.Status.APPROVED
    )
    if transaction.status == Transaction.Status.FLAGGED:
        transaction.reflection_prompt = secrets.choice(REFLECTION_PROMPTS)
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
        detail=(
            f"[{source}] risk_score={result['risk_score']:.2f}; "
            f"tier={tier}; network_reports={result['network_report_count']}; "
            f"{result['reason']}"
        ),
    )

    if transaction.status == Transaction.Status.APPROVED:
        update_baseline_from_transaction(transaction)

    return transaction


def submit_reflection(transaction: Transaction, answer: str) -> Transaction:
    if transaction.status != Transaction.Status.FLAGGED:
        raise ValueError("Reflection is only required for a flagged transaction.")

    normalized_answer = " ".join((answer or "").split())
    if len(normalized_answer) < 10:
        raise ValueError("Please tell us a bit more before continuing.")

    lowered = normalized_answer.casefold()
    red_flags = [
        phrase for phrase in REFLECTION_RED_FLAG_PHRASES if phrase in lowered
    ]
    transaction.reflection_answer = normalized_answer
    transaction.reflection_red_flags = red_flags
    transaction.reflection_submitted_at = django_timezone.now()

    event_type = "reflection_completed"
    if red_flags:
        transaction.risk_score = max(float(transaction.risk_score or 0), 0.98)
        transaction.risk_tier = Transaction.RiskTier.CRITICAL
        transaction.cooldown_until = django_timezone.now() + timedelta(
            seconds=DEMO_COOLDOWN_SECONDS
        )
        escalation_reason = (
            "The reflection answer suggests someone may be directing this payment"
        )
        if escalation_reason.casefold() not in transaction.risk_reason.casefold():
            transaction.risk_reason = (
                f"{transaction.risk_reason}; {escalation_reason}"
                if transaction.risk_reason
                else escalation_reason
            )
        event_type = "reflection_escalated"
    elif transaction.risk_tier == Transaction.RiskTier.CRITICAL:
        transaction.cooldown_until = django_timezone.now() + timedelta(
            seconds=DEMO_COOLDOWN_SECONDS
        )

    transaction.save()
    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type=event_type,
        detail=(
            f'Prompt: "{transaction.reflection_prompt}" Answer: "{normalized_answer}" '
            f"Red flags: {', '.join(red_flags) if red_flags else 'none'}; "
            f"resulting_tier={transaction.risk_tier}"
        ),
    )
    return transaction


def report_recipient(
    transaction: Transaction, reported_by_user_id: str, reason: str, detail: str = ""
) -> tuple[RecipientReport, int, bool]:
    account_id = (transaction.recipient_account_id or "").strip()
    if not account_id:
        raise ValueError("This transaction has no beneficiary account to report.")

    report, created = RecipientReport.objects.get_or_create(
        recipient_account_id=account_id,
        reported_by_user_id=reported_by_user_id,
        defaults={
            "recipient_bank": transaction.recipient_bank,
            "recipient_name": transaction.recipient,
            "transaction": transaction,
            "reason": reason,
            "detail": detail,
        },
    )
    if not created:
        report.reason = reason
        report.detail = detail
        report.transaction = transaction
        report.save(update_fields=["reason", "detail", "transaction"])

    report_count = RecipientReport.objects.filter(
        recipient_account_id=account_id
    ).count()
    transaction.network_report_count = report_count
    transaction.save(update_fields=["network_report_count"])

    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type="recipient_reported",
        detail=(
            f"Beneficiary account {account_id} reported for {reason}. "
            f"Shared network report count is now {report_count}. {detail}"
        ).strip(),
    )
    return report, report_count, created


def request_security_review(transaction: Transaction) -> Transaction:
    if transaction.status != Transaction.Status.FLAGGED:
        raise ValueError("Only a flagged transaction can be sent for review.")
    if transaction.risk_tier != Transaction.RiskTier.CRITICAL:
        raise ValueError("Independent review is reserved for critical-risk transactions.")
    if not transaction.reflection_submitted_at:
        raise ValueError("Answer the reflection question before requesting review.")

    review, created = SecurityReview.objects.get_or_create(
        transaction=transaction,
        defaults={"requested_by_user_id": transaction.user_id},
    )
    if not created and review.status != SecurityReview.Status.PENDING:
        raise ValueError("This transaction already has a completed security review.")

    transaction.status = Transaction.Status.AWAITING_REVIEW
    transaction.save(update_fields=["status"])
    if created:
        LedgerEntry.objects.create(
            user_id=transaction.user_id,
            transaction=transaction,
            event_type="security_review_requested",
            detail=(
                "Critical-risk transfer moved to independent security review. "
                "The sender cannot release it from their own session."
            ),
        )
    return transaction


@db_transaction.atomic
def decide_security_review(
    transaction: Transaction, reviewer_user_id: str, decision: str, note: str = ""
) -> Transaction:
    transaction = Transaction.objects.select_for_update().get(pk=transaction.pk)
    if transaction.status != Transaction.Status.AWAITING_REVIEW:
        raise ValueError("This transaction is not awaiting security review.")
    if reviewer_user_id == transaction.user_id:
        raise ValueError("The sender cannot review their own transaction.")

    try:
        review = SecurityReview.objects.select_for_update().get(transaction=transaction)
    except SecurityReview.DoesNotExist as exc:
        raise ValueError("No security review request exists for this transaction.") from exc
    if review.status != SecurityReview.Status.PENDING:
        raise ValueError("This security review has already been completed.")

    if decision == "approve":
        if transaction.cooldown_until and transaction.cooldown_until > django_timezone.now():
            remaining = math.ceil(
                (transaction.cooldown_until - django_timezone.now()).total_seconds()
            )
            raise ValueError(
                f"The minimum safety pause is still active for {remaining} seconds."
            )
        review.status = SecurityReview.Status.APPROVED
        transaction.status = Transaction.Status.REVIEW_APPROVED
        event_type = "security_review_approved"
    elif decision == "block":
        review.status = SecurityReview.Status.BLOCKED
        transaction.status = Transaction.Status.BLOCKED
        event_type = "security_review_blocked"
    else:
        raise ValueError("Decision must be approve or block.")

    now = django_timezone.now()
    review.reviewer_note = (note or "").strip()
    review.reviewed_by_user_id = reviewer_user_id
    review.reviewed_at = now
    review.save(
        update_fields=["status", "reviewer_note", "reviewed_by_user_id", "reviewed_at"]
    )
    transaction.decided_at = now
    transaction.save(update_fields=["status", "decided_at"])
    LedgerEntry.objects.create(
        user_id=transaction.user_id,
        transaction=transaction,
        event_type=event_type,
        detail=(
            f"Independent reviewer {reviewer_user_id} chose to {decision}. "
            f"Reviewer note: {review.reviewer_note or 'No note supplied.'}"
        ),
    )
    return transaction


def apply_user_decision(transaction: Transaction, decision: str) -> Transaction:
    allowed_statuses = {Transaction.Status.FLAGGED, Transaction.Status.AWAITING_REVIEW}
    if transaction.status not in allowed_statuses:
        raise ValueError("Only flagged or held transactions can be decided on.")

    if decision == "confirm":
        if transaction.status == Transaction.Status.AWAITING_REVIEW:
            raise ValueError("A held transaction can only be released by an independent reviewer.")
        if not transaction.reflection_submitted_at:
            raise ValueError(
                "Answer the reflection question before continuing this transfer."
            )
        if transaction.risk_tier == Transaction.RiskTier.CRITICAL:
            raise ValueError(
                "Critical-risk transfers cannot be self-approved. Request security review instead."
            )

    was_awaiting_review = transaction.status == Transaction.Status.AWAITING_REVIEW

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

    if decision == "cancel" and was_awaiting_review:
        SecurityReview.objects.filter(transaction=transaction).update(
            status=SecurityReview.Status.CANCELLED,
            reviewer_note="Cancelled by the sender before review was completed.",
            reviewed_at=transaction.decided_at,
        )

    if (
        decision == "confirm"
        and transaction.network_report_count == 0
        and not transaction.reflection_red_flags
    ):
        update_baseline_from_transaction(transaction)

    return transaction
