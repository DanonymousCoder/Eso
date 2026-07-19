import logging
from pathlib import Path
from datetime import datetime, timezone

import joblib
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_PATH = Path(settings.BASE_DIR) / "transactions" / "risk_model.pkl"

# Feature weights for the heuristic model
WEIGHTS = {
    "amount_ratio": 0.35,
    "new_recipient": 0.25,
    "unusual_hour": 0.15,
    "new_device": 0.15,
    "amount_velocity": 0.10,
}


def _extract_features(transaction, baseline, recent_count=0):
    from django.utils import timezone as django_timezone
    if hasattr(transaction, "created_at") and transaction.created_at:
        hour = django_timezone.localtime(transaction.created_at).hour
    else:
        hour = django_timezone.localtime(django_timezone.now()).hour
    typical_min = float(baseline.typical_amount_min)
    typical_max = float(baseline.typical_amount_max)
    amount = float(transaction.amount)

    amount_range = max(typical_max - typical_min, 1)
    amount_mid = (typical_max + typical_min) / 2
    amount_ratio = min(abs(amount - amount_mid) / amount_range, 5.0) / 5.0

    is_new_recipient = 1.0 if transaction.recipient not in baseline.typical_recipients else 0.0

    typical_hours = baseline.typical_hours or list(range(7, 22))
    is_unusual_hour = 0.0 if hour in typical_hours else 1.0

    is_new_device = 1.0 if transaction.device_id and transaction.device_id not in baseline.known_devices else 0.0

    amount_velocity = min(recent_count / 10, 1.0)

    return {
        "amount_ratio": amount_ratio,
        "new_recipient": is_new_recipient,
        "unusual_hour": is_unusual_hour,
        "new_device": is_new_device,
        "amount_velocity": amount_velocity,
    }


def heuristic_risk_score(transaction, baseline, recent_count=0):
    features = _extract_features(transaction, baseline, recent_count)
    score = sum(WEIGHTS[k] * features[k] for k in WEIGHTS)
    score = min(max(score, 0.0), 1.0)
    return score


def _generate_reason(score, features, transaction=None, baseline=None):
    reasons = []
    if features["amount_ratio"] > 0.6:
        if transaction and baseline:
            amount = float(transaction.amount)
            lo = float(baseline.typical_amount_min)
            hi = float(baseline.typical_amount_max)
            reasons.append(
                f"Transfer of \u20a6{amount:,.0f} is well outside your typical range "
                f"(\u20a6{lo:,.0f}\u2013\u20a6{hi:,.0f})"
            )
        else:
            reasons.append("Transfer amount is well outside your typical range")
    if features["new_recipient"] > 0.5:
        if transaction:
            reasons.append(
                f"'{transaction.recipient}' has not appeared in your previous approved transfers"
            )
        else:
            reasons.append("Recipient is not in your known contacts")
    if features["unusual_hour"] > 0.5:
        from django.utils import timezone as django_timezone
        if transaction and transaction.created_at:
            local_dt = django_timezone.localtime(transaction.created_at)
        else:
            local_dt = django_timezone.localtime(django_timezone.now())
        hour = local_dt.hour
        minute = local_dt.minute
        period = "night" if hour < 6 or hour >= 22 else "early morning" if hour < 9 else "late evening"
        reasons.append(
            f"Transfer initiated at {hour:02d}:{minute:02d}, outside your usual active hours ({period})"
        )
    if features["new_device"] > 0.5:
        reasons.append("Request came from a browser or device not seen in your recent sessions")
    if features["amount_velocity"] > 0.5:
        reasons.append("You have made an unusually high number of transfers recently")
    if not reasons:
        if transaction:
            reasons.append(
                f"Transfer of \u20a6{float(transaction.amount):,.0f} to '{transaction.recipient}' "
                f"matches your usual pattern — recipient known, amount normal, timing typical"
            )
        else:
            reasons.append("This transfer matches your usual spending behaviour")
    return "; ".join(reasons)


class RiskModel:
    def __init__(self):
        self.model = None
        self._load()

    def _load(self):
        if MODEL_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
                logger.info("Loaded risk model from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load model: %s. Using heuristic fallback.", e)
                self.model = None

    def predict(self, transaction, baseline, recent_count=0):
        features = _extract_features(transaction, baseline, recent_count)

        if self.model is not None:
            try:
                import numpy as np

                X = np.array([[features[k] for k in WEIGHTS]])
                score = float(self.model.predict_proba(X)[0, 1])
                score = min(max(score, 0.0), 1.0)
            except Exception as e:
                logger.warning("Model prediction failed: %s. Falling back to heuristic.", e)
                score = heuristic_risk_score(transaction, baseline, recent_count)
        else:
            score = heuristic_risk_score(transaction, baseline, recent_count)

        reason = _generate_reason(score, features, transaction=transaction, baseline=baseline)
        return {"risk_score": round(score, 4), "reason": reason}

    def is_loaded(self):
        return self.model is not None


risk_model = RiskModel()
